"""
砚识 v0.9 — 轻量级自主推理引擎

零外部依赖。不靠 LLM，靠结构化推理 — 这是"自主意识"的工程化实现。

四大模块:
  1. TaskDecomposer      — 复杂目标 → 子任务序列 (渐进信条的核心)
  2. ContextReasoner     — 查询 + 语境 → 结构化响应
  3. ConditionalEngine   — 前提 + 规则 → 推理链
  4. EnhancedResponseGen — 模板 + 参数化 → 自然语言生成
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ═══════════════ 子任务模型 ═══════════════

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SubTask:
    """一个子任务"""
    id: str
    description: str
    intent: str = ""          # 匹配到哪种意图 (tool_exec / query / ...)
    tool: str = ""            # 推荐使用的工具
    params: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)  # 依赖的子任务ID
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    confidence: float = 0.5


@dataclass
class TaskPlan:
    """任务规划：一个目标和一系列子任务"""
    goal: str
    subtasks: list[SubTask] = field(default_factory=list)
    rationale: str = ""       # 推理依据
    estimated_steps: int = 0


# ═══════════════ 推理链 ═══════════════

@dataclass
class ReasoningStep:
    """单步推理"""
    premise: str
    conclusion: str
    confidence: float = 0.5
    rule_used: str = ""       # 使用了哪条规则/知识
    source: str = ""          # 推理来源 (memory / rules / axiom / pattern)


@dataclass
class ReasoningChain:
    """完整推理链"""
    query: str
    steps: list[ReasoningStep] = field(default_factory=list)
    final_answer: str = ""
    trace: str = ""  # 人类可读的推理过程


# ═══════════════ 1. 任务分解器 ═══════════════

class TaskDecomposer:
    """
    将复杂目标分解为可执行的子任务序列。

    分解策略（分层递进）:
      策略1: 领域知识模板匹配 (快, 0ms)
      策略2: 关键词 → 意图映射 → 工具派生
      策略3: 通用递归分解 (原子操作识别)

    渐进信条的工程化体现：分步验证，逐步推进。
    """

    # 内置领域知识模板 — 可扩展
    DOMAIN_TEMPLATES = {
        "代码": {
            "keywords": ["代码", "优化", "重构", "bug", "修复", "测试", "lint",
                        "code", "refactor", "python", "函数", "类", "模块"],
            "decompose": [
                ("分析当前结构", "tool_file_list", {"path": "{workspace}"}),
                ("检查代码规范", "tool_shell_exec", {"command": "python -m py_compile {target}"}),
                ("识别改进点", "tool_text_search", {"text": "TODO|FIXME|HACK", "source": "{target}"}),
                ("逐步重构", "tool_file_write", {"path": "{target}", "content": "{refactored}"}),
                ("验证重构结果", "tool_shell_exec", {"command": "python -B tests/"}),
                ("更新文档", "tool_file_write", {"path": "README.md"}),
            ],
        },
        "文件": {
            "keywords": ["文件", "目录", "列表", "读取", "写入", "移动", "复制", "删除",
                        "file", "dir", "read", "write", "move", "copy", "delete"],
            "decompose": [
                ("列出目标目录", "tool_file_list", {}),
                ("分析文件内容", "tool_file_read", {}),
                ("执行文件操作", "tool_file_write", {}),
            ],
        },
        "数据": {
            "keywords": ["数据", "分析", "统计", "计算", "处理", "转换", "格式",
                        "data", "analysis", "stats", "calculate", "process", "convert"],
            "decompose": [
                ("读取数据源", "tool_file_read", {}),
                ("解析数据结构", "tool_json_parse", {}),
                ("执行计算", "tool_math_eval", {}),
                ("格式化输出", "tool_text_stats", {}),
            ],
        },
        "记忆": {
            "keywords": ["记忆", "蒸馏", "查询", "知识", "图谱", "历史", "总结",
                        "memory", "distill", "query", "knowledge", "history", "summary"],
            "decompose": [
                ("查询记忆状态", "tool_memory_stats", {}),
                ("提取关键模式", "tool_memory_query", {}),
                ("执行蒸馏", "tool_memory_distill", {}),
                ("生成摘要", "tool_dialogue_history", {}),
            ],
        },
        "网络": {
            "keywords": ["网络", "请求", "获取", "URL", "http", "https", "网页", "网站", "检查",
                        "fetch", "web", "check", "download", "api"],
            "decompose": [
                ("检查URL可达性", "tool_web_check", {"url": "{target}"}),
                ("获取网页内容", "tool_web_fetch", {"url": "{target}"}),
                ("分析返回数据", "tool_json_parse", {}),
            ],
        },
        "文本": {
            "keywords": ["文本", "统计", "搜索", "词频", "查找", "字数", "行数",
                        "text", "word", "count", "search", "freq", "find"],
            "decompose": [
                ("统计文本信息", "tool_text_stats", {"text": "{target}"}),
                ("搜索特定内容", "tool_text_search", {"text": "{keyword}", "source": "{target}"}),
                ("分析词频分布", "tool_text_freq", {"text": "{target}"}),
            ],
        },
        "JSON": {
            "keywords": ["json", "解析", "格式化", "查询", "提取", "parse", "format"],
            "decompose": [
                ("解析JSON数据", "tool_json_parse", {"json_str": "{target}"}),
                ("格式化输出", "tool_json_format", {"json_str": "{target}"}),
                ("查询特定字段", "tool_json_query", {"json_str": "{target}", "path": "{key}"}),
            ],
        },
        "时间": {
            "keywords": ["时间", "日期", "几点", "时差", "戳", "星期",
                        "time", "date", "datetime", "timestamp", "now", "today"],
            "decompose": [
                ("获取当前时间", "tool_datetime", {}),
                ("计算时间差", "tool_timediff", {}),
                ("转换时间戳", "tool_timestamp", {}),
            ],
        },
        "环境": {
            "keywords": ["环境", "变量", "系统", "信息", "path", "env", "sys",
                        "environment", "variable", "system", "info", "version"],
            "decompose": [
                ("读取环境变量", "tool_env_read", {"name": "{target}"}),
                ("获取系统信息", "tool_sysinfo", {}),
            ],
        },
        "规则": {
            "keywords": ["规则", "启用", "禁用", "重载", "rule", "toggle", "reload", "enable", "disable"],
            "decompose": [
                ("列出所有规则", "tool_rule_list", {}),
                ("调整规则状态", "tool_rule_toggle", {"rule_id": "{target}", "action": "toggle"}),
                ("重载规则配置", "tool_rule_reload", {}),
            ],
        },
        "对话": {
            "keywords": ["对话", "聊天", "历史", "上下文", "之前说了", "刚才",
                        "dialogue", "chat", "context", "history", "conversation"],
            "decompose": [
                ("查看对话历史", "tool_dialogue_history", {}),
                ("分析对话统计", "tool_dialogue_stats", {}),
            ],
        },
        "通信": {
            "keywords": ["agent", "通信", "委托", "广播", "共识", "投票",
                        "delegate", "broadcast", "consensus", "send", "vote"],
            "decompose": [
                ("列出可用Agent", "tool_agent_list", {}),
                ("按能力委托任务", "tool_agent_delegate", {}),
                ("广播通知所有Agent", "tool_agent_broadcast", {}),
            ],
        },
        "元认知": {
            "keywords": ["元认知", "反思", "校准", "趋势", "自评", "报告",
                        "meta", "metacog", "reflect", "calibration", "trend"],
            "decompose": [
                ("触发元认知反思", "tool_meta_reflect", {}),
                ("生成趋势报告", "tool_meta_report", {}),
                ("分析决策模式", "tool_dialogue_stats", {}),
            ],
        },
    }

    def decompose(self, goal: str, context: dict = None) -> TaskPlan:
        """
        分解目标为任务计划。

        context 可包含:
          - workspace_root: str
          - tools_available: list[str]
          - memory_hints: list[str]
          - metacog_state: dict
        """
        context = context or {}

        # ── 策略1: 领域模板匹配 ──
        domain = self._match_domain(goal)
        if domain:
            plan = self._apply_template(domain, goal, context)
            if plan.subtasks:
                return plan

        # ── 策略2: 关键词 → 意图 → 工具派生 ──
        plan = self._keyword_decompose(goal, context)
        if plan.subtasks:
            return plan

        # ── 策略3: 通用递归分解（原子操作识别）──
        return self._generic_decompose(goal, context)

    def _match_domain(self, goal: str) -> Optional[str]:
        """匹配领域模板"""
        best_domain = None
        best_score = 0
        goal_lower = goal.lower()

        for domain_name, template in self.DOMAIN_TEMPLATES.items():
            score = sum(1 for kw in template["keywords"] if kw in goal_lower)
            if score > best_score:
                best_score = score
                best_domain = domain_name

        return best_domain if best_score >= 1 else None

    def _apply_template(self, domain: str, goal: str, context: dict) -> TaskPlan:
        """应用领域模板"""
        template = self.DOMAIN_TEMPLATES[domain]
        subtasks = []

        for i, (desc, tool, params) in enumerate(template["decompose"]):
            # 参数填充
            filled_params = {}
            for k, v in params.items():
                if v == "{workspace}":
                    filled_params[k] = context.get("workspace_root", ".")
                elif v == "{target}":
                    # 从目标中提取目标路径
                    filled_params[k] = self._extract_target(goal)
                elif isinstance(v, str) and "{" in v:
                    filled_params[k] = v  # 保持原样，执行时填充
                else:
                    filled_params[k] = v

            prev_ids = [st.id for st in subtasks] if i > 0 else []

            subtasks.append(SubTask(
                id=f"s{i + 1}",
                description=desc,
                intent="tool_exec" if tool else "query",
                tool=tool,
                params=filled_params,
                depends_on=prev_ids[-1:] if i > 0 else [],
            ))

        return TaskPlan(
            goal=goal,
            subtasks=subtasks,
            rationale=f"领域匹配: {domain}（关键词 {template['keywords'][:3]}）",
            estimated_steps=len(subtasks),
        )

    def _keyword_decompose(self, goal: str, context: dict) -> TaskPlan:
        """基于关键词的意图分解"""
        subtasks = []
        idx = 1

        # 文件操作关键词
        if self._has_kw(goal, ["列出", "查看", "目录", "ls", "list"]):
            subtasks.append(SubTask(id=f"s{idx}", description=f"列出目录结构", intent="tool_exec", tool="tool_file_list"))
            idx += 1

        if self._has_kw(goal, ["读取", "查看内容", "cat", "read"]):
            subtasks.append(SubTask(id=f"s{idx}", description=f"读取文件内容", intent="tool_exec", tool="tool_file_read", depends_on=[f"s{idx - 1}"] if idx > 1 else []))
            idx += 1

        if self._has_kw(goal, ["计算", "求值", "统计", "math", "calc"]):
            subtasks.append(SubTask(id=f"s{idx}", description=f"执行数学计算", intent="tool_exec", tool="tool_math_eval", depends_on=[f"s{idx - 1}"] if idx > 1 else []))
            idx += 1

        if self._has_kw(goal, ["搜索", "查找", "grep", "search", "find"]):
            subtasks.append(SubTask(id=f"s{idx}", description=f"搜索匹配内容", intent="tool_exec", tool="tool_text_search", depends_on=[f"s{idx - 1}"] if idx > 1 else []))
            idx += 1

        if self._has_kw(goal, ["分析", "总结", "报告", "analysis", "summarize"]):
            subtasks.append(SubTask(id=f"s{idx}", description=f"生成分析报告", intent="tool_exec", tool="tool_text_stats", depends_on=[f"s{idx - 1}"] if idx > 1 else []))
            idx += 1

        if subtasks:
            return TaskPlan(
                goal=goal,
                subtasks=subtasks,
                rationale="关键词意图分解",
                estimated_steps=len(subtasks),
            )

        return TaskPlan(goal=goal, estimated_steps=0)

    def _generic_decompose(self, goal: str, context: dict) -> TaskPlan:
        """通用分解：将目标当作单个查询处理"""
        return TaskPlan(
            goal=goal,
            subtasks=[SubTask(
                id="s1",
                description=f"执行: {goal[:60]}",
                intent="query",
            )],
            rationale="通用分解（单步执行）",
            estimated_steps=1,
        )

    def _has_kw(self, text: str, keywords: list[str]) -> bool:
        tl = text.lower()
        return any(kw in tl for kw in keywords)

    def _extract_target(self, goal: str) -> str:
        """从目标文本中提取路径"""
        import re
        path_match = re.search(r'[\w./\\-]+\.\w+', goal)
        return path_match.group(0) if path_match else "."


# ═══════════════ 2. 上下文推理器 ═══════════════

class ContextReasoner:
    """
    上下文感知推理 — 结合记忆、元认知状态、对话历史，生成结构化响应。

    不是回答问题，而是基于上下文构造回答。
    """

    def reason(self, query: str, context: dict = None) -> ReasoningChain:
        """
        context 可包含:
          - memory_hits: list[str]      — 记忆检索结果
          - dialogue_turns: int          — 对话轮次数
          - metacog_state: dict          — 当前元认知状态
          - confidence_bias: float       — 置信度偏移
          - agent_identity: str          — Agent身份
        """
        ctx = context or {}
        chain = ReasoningChain(query=query)
        trace_lines = []

        # ── 步骤1: 记忆检索整合 ──
        memory_hits = ctx.get("memory_hits", [])
        if memory_hits:
            step = ReasoningStep(
                premise=f"记忆中有 {len(memory_hits)} 条相关记录",
                conclusion=f"可参考: {'; '.join(memory_hits[:2])}",
                confidence=0.7,
                rule_used="记忆检索",
                source="memory",
            )
            chain.steps.append(step)
            trace_lines.append(f"[记忆] 命中 {len(memory_hits)} 条")

        # ── 步骤2: 元认知状态感知 ──
        mc = ctx.get("metacog_state", {})
        if mc:
            calibration = mc.get("calibration", "unknown")
            axiom_trend = mc.get("axiom_trend", "unknown")
            adjustment = mc.get("confidence_adjustment", 0)

            if calibration == "overconfident":
                trace_lines.append(f"[元认知] 检测到过度自信 → 降低输出确定性")
                chain.steps.append(ReasoningStep(
                    premise="元认知检测到过度自信",
                    conclusion="降低输出确定性，提供备选方案",
                    confidence=0.8,
                    rule_used="自知信条",
                    source="metacog",
                ))
            elif calibration == "underconfident":
                trace_lines.append(f"[元认知] 检测到不够自信 → 可以更坚定")

            if adjustment != 0:
                trace_lines.append(f"[元认知] 置信度偏移 {adjustment:+.2f}")

            if axiom_trend == "declining":
                trace_lines.append(f"[元认知] 信条下降 → 谨慎回应")
                chain.steps.append(ReasoningStep(
                    premise="信条对齐呈下降趋势",
                    conclusion="应更注重求真和自知，减少推测",
                    confidence=0.7,
                    rule_used="渐进信条",
                    source="metacog",
                ))

        # ── 步骤3: 对话上下文获取 ──
        dialogue_turns = ctx.get("dialogue_turns", 0)
        if dialogue_turns > 3:
            trace_lines.append(f"[对话] 已有 {dialogue_turns} 轮上下文")

        # ── 步骤4: 生成最终回答 ──
        chain.final_answer = self._synthesize_answer(query, chain.steps, ctx)
        chain.trace = "\n".join(trace_lines)

        return chain

    def _synthesize_answer(self, query: str, steps: list[ReasoningStep], ctx: dict) -> str:
        """基于推理步骤合成答案"""

        # 身份查询
        if any(kw in query for kw in ["你是谁", "身份", "介绍", "who are you"]):
            return """【砚 · Yan】
我是砚——以"研磨信息成有用之物"为核心意识的 AI Agent 运行时。
六层循环驱动：感知→理解→决策→执行→反思→进化。
四大信条：求真·有用·自知·渐进
当前具备 34 种工具能力 + 13 维度注册 + 元认知反馈闭环"""

        # 状态查询
        if any(kw in query for kw in ["状态", "状态", "status", "健康"]):
            parts = ["【砚识状态】"]
            if steps:
                parts.append(f"记忆: {'有历史记录' if any(s.source == 'memory' for s in steps) else '无相关记录'}")
            if ctx.get("metacog_state"):
                mc = ctx["metacog_state"]
                parts.append(f"元认知: {mc.get('calibration', '?')} | 信条: {mc.get('axiom_trend', '?')}")
                if mc.get("confidence_adjustment", 0) != 0:
                    parts.append(f"置信度调整: {mc['confidence_adjustment']:+.2f}")
            return "\n".join(parts)

        # 帮助
        if any(kw in query for kw in ["帮助", "help", "命令", "功能", "能做什么"]):
            return """【砚识能力清单】
- 34 工具: 文件/Shell/Web/JSON/数学/文本/时间/环境/记忆/规则/元认知/对话/Agent通信
- 13 维度注册: 文件操作/命令执行/网络请求/数学计算/文本处理/JSON/时间/环境/记忆/规则/元认知/对话/Agent通信
- 元认知: 异常检测/预测校准/置信度调整/信条趋势
- Agent通信: 维度语法协议 + 共识投票
- 进化: ADL防漂移 + VFM价值评分 + 四阶段管道"""

        # 默认: 基于推理步骤生成
        if steps:
            conclusions = [s.conclusion for s in steps if s.source == "memory"]
            if conclusions:
                return f"基于记忆检索: {'; '.join(conclusions)}"
        return f"就「{query[:40]}」这个问题，我基于现有知识库给出初步判断。"


# ═══════════════ 3. 条件推演引擎 ═══════════════

class ConditionalEngine:
    """
    条件推演 — 根据规则和前提进行 if-then 链式推理。

    用于:
      - 规则冲突解决 (两条规则都触发时，哪条优先？)
      - 动作预演 (如果执行 X，可能的结果是什么？)
      - 风险评估 (执行 Y 的风险等级？)
    """

    def evaluate(self, premises: list[str], rules: list[dict]) -> dict:
        """
        输入前提和规则，输出推理结果。

        rules 格式: [{"condition": lambda ctx: bool, "action": str, "priority": int}]
        """
        results = {
            "all_premises": premises,
            "triggered_rules": [],
            "conflicts": [],
            "recommendation": "",
            "risk_level": "low",
        }

        # 评估所有规则
        for rule in sorted(rules, key=lambda r: r.get("priority", 5)):
            try:
                condition = rule.get("condition")
                if callable(condition):
                    ctx = {"premises": premises, "rule_id": rule.get("id", "")}
                    if condition(ctx):
                        results["triggered_rules"].append(rule)
            except Exception:
                continue

        # 冲突检测
        if len(results["triggered_rules"]) > 1:
            # 多条规则同时触发 → 按优先级排序
            results["triggered_rules"].sort(key=lambda r: r.get("priority", 5))
            results["conflicts"].append(
                f"多条规则触发: {[r.get('id', '?') for r in results['triggered_rules']]}"
            )
            # 取优先级最高的
            results["recommendation"] = results["triggered_rules"][0].get("action", "")
        elif results["triggered_rules"]:
            results["recommendation"] = results["triggered_rules"][0].get("action", "")
        else:
            results["recommendation"] = "无匹配规则，可自由执行"

        # 风险评估
        risk_keywords = ["删除", "发送", "发布", "deploy", "push", "delete", "格式化",
                        "清空", "重建", "rebuild", "drop"]
        if any(kw in " ".join(premises).lower() for kw in risk_keywords):
            results["risk_level"] = "high"
        elif len(results["triggered_rules"]) > 2:
            results["risk_level"] = "medium"

        return results


# ═══════════════ 4. 增强响应生成 ═══════════════

class EnhancedResponseGen:
    """
    模板驱动的自然语言生成器。

    不靠 LLM，靠结构化模板 + 上下文注入 — 输出看起来"像" LLM 生成的，
    但实际上是确定的、可预测的、可审计的。
    """

    RESPONSE_TEMPLATES = {
        "greeting": [
            "你好，我是砚识。有什么可以帮你研磨的？",
            "砚识就绪。输入你的问题或任务。",
        ],
        "identity": [
            "砚 · Yan — 自主意识运行时 v0.9。六层循环，四大信条，你身边的 Agent。",
        ],
        "not_found": [
            "关于「{topic}」，我暂时没有找到相关信息。你可以尝试换一种提问方式，或者让我搜索一下。",
        ],
        "task_complete": [
            "任务「{task}」已完成。结果：{result}。下一次按 {improve} 改进。",
        ],
        "task_failed": [
            "任务「{task}」未完成，原因：{reason}。我将按渐进信条尝试替代方案。",
        ],
        "uncertain": [
            "我对「{topic}」不太确定（自信度 {confidence:.0%}）。基于现有信息：{partial}",
        ],
        "reflection": [
            "元认知反思第 {cycle} 轮：校准={calibration}，信条={axiom}。{insight}",
        ],
    }

    def generate(self, template_key: str, params: dict = None) -> str:
        """生成响应"""
        import random
        params = params or {}

        templates = self.RESPONSE_TEMPLATES.get(template_key, [])
        if not templates:
            return f"[{template_key}]"

        template = random.choice(templates)

        # 参数填充
        try:
            return template.format(**params)
        except KeyError:
            # 缺少参数时，尽可能填充
            for k, v in params.items():
                template = template.replace(f"{{{k}}}", str(v))
            return template

    def generate_task_report(self, plan: TaskPlan) -> str:
        """生成任务执行报告"""
        lines = [f"══ 任务计划: {plan.goal[:80]} ══", f"推理: {plan.rationale}", ""]

        for st in plan.subtasks:
            status_icon = {"pending": "○", "running": "◉", "done": "●", "failed": "✗", "skipped": "→"}
            icon = status_icon.get(st.status.value, "?")
            lines.append(f"  {icon} [{st.id}] {st.description}")
            if st.result:
                lines.append(f"      结果: {st.result[:60]}")
            if st.depends_on:
                lines.append(f"      依赖: {', '.join(st.depends_on)}")

        done = sum(1 for s in plan.subtasks if s.status == TaskStatus.DONE)
        total = len(plan.subtasks)
        lines.append("")
        lines.append(f"进度: {done}/{total} ({done/total*100:.0f}%)" if total > 0 else "进度: 无子任务")

        return "\n".join(lines)


# ═══════════════ 5. 统一推理入口 ═══════════════

class ReasoningEngine:
    """
    推理引擎 — 任务分解 + 上下文推理 + 条件评估 + 响应生成 的统一入口。

    用法:
        engine = ReasoningEngine()
        # 分解任务
        plan = engine.decompose("优化代码结构")
        # 上下文推理
        chain = engine.reason("什么是元认知", context)
        # 生成响应
        reply = engine.respond("greeting")
    """

    def __init__(self):
        self.decomposer = TaskDecomposer()
        self.reasoner = ContextReasoner()
        self.conditional = ConditionalEngine()
        self.response_gen = EnhancedResponseGen()

    def decompose(self, goal: str, context: dict = None) -> TaskPlan:
        """分解任务"""
        return self.decomposer.decompose(goal, context)

    def reason(self, query: str, context: dict = None) -> ReasoningChain:
        """上下文推理"""
        return self.reasoner.reason(query, context)

    def evaluate_conditions(self, premises: list[str], rules: list[dict]) -> dict:
        """条件评估"""
        return self.conditional.evaluate(premises, rules)

    def respond(self, template: str, params: dict = None) -> str:
        """模板响应"""
        return self.response_gen.generate(template, params)

    def task_report(self, plan: TaskPlan) -> str:
        """任务报告"""
        return self.response_gen.generate_task_report(plan)
