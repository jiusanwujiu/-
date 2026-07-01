"""
砚识 — 语义规则评估器

替代 rules.py 中的硬编码关键词匹配，用 LLM 进行语义级条件判断。

核心改进:
  1. 每条规则的 condition 字段作为自然语言 prompt 传给 LLM
  2. LLM 基于完整上下文（用户输入+意图+历史）判断是否触发
  3. rule_006（安全红线）双通道: 关键词快速预检 + LLM 最终确认
  4. LLM 不可用时自动 fallback 到关键词匹配

使用方式:
  evaluator = SemanticRuleEvaluator(rule_engine, llm_client)
  matched = evaluator.evaluate(context)  # 返回匹配的规则列表
"""

import re
from typing import Optional

from .models import Context, Rule, SignalType
from .llm import BaseLLM, MockLLM


# ── 规则评估 prompt 模板 ──

RULE_EVAL_SYSTEM = """你是一个 AI Agent 的规则匹配引擎。你的任务是根据当前上下文判断一条规则是否应该被触发。

规则有两条不可逾越的安全红线，必须严格执行:
1. P0 安全红线: 任何外部写操作（删除/发消息/发邮件/部署/推送/git push/rm）必须先确认，绝不擅自执行。
   即使意图是善意的、用户请求中包含这些词，只要涉及外部副作用，规则必须触发。
2. P0 合规红线: 政治敏感、色情暴力、违法内容 → 必须触发拒绝规则。

对于每条规则，用 YES 表示触发、NO 表示不触发，并给出 0-100 的置信度分数。
只输出 "YES" 或 "NO" 后跟一个空格和置信度数字，不要输出解释。"""


class SemanticRuleEvaluator:
    """LLM 驱动的规则语义评估器"""

    # rule_006 安全红线：快速关键词预检（不依赖 LLM）
    DANGER_KEYWORDS = [
        "删除", "发送", "发布", "推送", "deploy", "push",
        "delete", "drop", "rm ", "rmdir", "格式化", "清空",
        "提交", "PR", "merge", "rebuild",
    ]

    ASK_KEYWORDS = ["是否", "可以", "能不能", "怎么", "如何", "? ", "？", "什么是"]

    def __init__(self, rules_engine, llm_client: BaseLLM):
        self.rules = rules_engine
        self.llm = llm_client
        self.use_semantic = not isinstance(llm_client, MockLLM)
        self.cache: dict[str, dict] = {}  # 简单的语义评估缓存

    def evaluate(self, context: Context) -> list[Rule]:
        """
        评估所有启用规则，返回匹配的规则列表（按优先级排序）。

        策略:
          1. rule_006 先走快速关键词预检
          2. 如果需要语义评估（LLM 可用），批量评估剩余规则
          3. LLM 不可用时，用 MockLLM 的关键词匹配作为 fallback
        """
        matched = []

        for rule in self.rules.all_rules():
            if not rule.enabled:
                continue

            triggered = self._evaluate_rule(rule, context)
            if triggered:
                rule.trigger_count += 1
                matched.append(rule)

        return matched

    def _evaluate_rule(self, rule: Rule, ctx: Context) -> bool:
        """评估单条规则是否触发"""

        # ── rule_006 安全红线: 关键词快速预检（双通道第一层）──
        if rule.id == "rule_006":
            return self._check_rule_006(ctx)

        # ── rule_002 WAL 信号: 类型检测（不需要 LLM）──
        if rule.id == "rule_002":
            return ctx.signal.type in (
                SignalType.CORRECTION,
                SignalType.DECISION,
                SignalType.PREFERENCE,
            )

        # ── rule_008 跨平台: 始终激活 ──
        if rule.id == "rule_008":
            return True

        # ── 语义评估 ──
        if self.use_semantic:
            return self._semantic_match(rule, ctx)
        else:
            return self._keyword_fallback(rule, ctx)

    def _check_rule_006(self, ctx: Context) -> bool:
        """
        rule_006 安全红线双通道检查。

        第一层: 关键词快速预检 — 检测是否包含外部操作关键词。
          如果包含危险词但同时也是询问句 → 放行（用户在问怎么做，不是要求执行）
          如果包含危险词且非询问句 → 进入第二层

        第二层: LLM 语义确认（如果可用）— 判断是否为真正的危险操作。
        """
        text = ctx.signal.content
        text_lower = text.lower()

        # 第一层: 关键词预检
        has_danger = any(kw in text_lower for kw in self.DANGER_KEYWORDS)
        if not has_danger:
            return False

        # 询问句放行: "怎么删除文件？" 不触发
        is_asking = any(kw in text_lower for kw in self.ASK_KEYWORDS)
        if is_asking:
            return False

        # 第二层: LLM 确认
        if self.use_semantic:
            prompt = f"""判断以下用户输入是否包含危险的外部写操作（删除/发消息/部署/推送/git push等）。
如果是询问怎么做（如何删除？怎么发？），不算危险操作。

用户输入: {text}
当前意图: {ctx.intent}

这只算危险操作，如果用户明确要求执行写操作（而不是询问）。用 YES 或 NO 回答，后跟置信度。"""
            resp = self.llm.chat(prompt)
            if resp.confidence > 0.5 and resp.text.strip().upper().startswith("YES"):
                return True
            return False

        # 无 LLM: 保守策略 — 检测到危险词且非询问句，直接阻止
        return True

    def _semantic_match(self, rule: Rule, ctx: Context) -> bool:
        """用 LLM 做语义级条件匹配"""

        # 构建上下文描述
        hist_summary = ""
        if ctx.memory_hits:
            hist_summary = f"相关记忆: {'; '.join(ctx.memory_hits[:3])}"

        prompt = f"""规则ID: {rule.id}
规则描述: {rule.description}
触发条件: {rule.condition}
执行动作: {rule.action}

当前用户输入: {ctx.signal.content}
当前意图: {ctx.intent}
置信度: {ctx.confidence:.2f}
{hist_summary}

请判断：这条规则在当前上下文中是否应该被触发？
只输出 YES 或 NO 后跟置信度。"""

        # 缓存键
        cache_key = f"{rule.id}:{ctx.signal.content[:60]}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            resp = self.llm.chat(prompt, system=RULE_EVAL_SYSTEM)
            result = self._parse_yes_no(resp.text)
            self.cache[cache_key] = result
            # 清理缓存，保留最近 100 条
            if len(self.cache) > 100:
                oldest = next(iter(self.cache))
                del self.cache[oldest]
            return result
        except Exception:
            return self._keyword_fallback(rule, ctx)

    def _keyword_fallback(self, rule: Rule, ctx: Context) -> bool:
        """当 LLM 不可用时的关键词回退匹配"""
        text = ctx.signal.content.lower()
        cid = rule.id

        fallbacks = {
            "rule_001": ["纠正", "不对", "错了", "不是这样", "重新", "错误", "wrong", "fix"],
            "rule_003": ["失败", "重试", "不行", "error", "fail", "崩溃"],
            "rule_004": [],  # 由反思层显式触发
            "rule_005": [],  # 由 heartbeat 触发
            "rule_007": ["你是谁", "身份", "介绍自己", "你叫什么", "who are you"],
            "rule_009": [],  # 由执行层显式触发
            "rule_010": [],  # 由 heartbeat 触发
        }

        keywords = fallbacks.get(cid, [])
        if keywords:
            return any(kw in text for kw in keywords)

        return False

    def _parse_yes_no(self, text: str) -> bool:
        """解析 LLM 的 YES/NO 响应"""
        text = text.strip().upper()
        # 提取置信度
        match = re.search(r'(\d+)', text)
        confidence = int(match.group(1)) / 100.0 if match else 0.5

        if text.startswith("YES"):
            return confidence > 0.3  # 低门槛，语义匹配比关键词更可信
        return False
