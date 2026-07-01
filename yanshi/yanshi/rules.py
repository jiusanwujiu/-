"""
砚识 — 规则引擎

从 minds/rules.jsonl 加载10条规则，按优先级排序。
根据上下文匹配适用的规则并执行。
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from .models import Rule, Context, Decision, RulePriority, SignalType


class RuleEngine:
    """规则引擎：加载→匹配→执行"""

    def __init__(self, rules_path: str):
        self.rules_path = Path(rules_path)
        self.rules: list[Rule] = []
        self._semantic_evaluator = None  # 可选的语义评估器
        self._load()

    def _load(self):
        """从 JSONL 文件加载规则"""
        if not self.rules_path.exists():
            return
        loaded = []
        with open(self.rules_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    rule = Rule(
                        id=data["id"],
                        priority=data.get("priority", 5),
                        condition=data.get("condition", ""),
                        action=data.get("action", ""),
                        description=data.get("description", ""),
                        trigger_count=data.get("trigger_count", 0),
                        enabled=data.get("enabled", True),
                    )
                    setattr(rule, '_raw', data)  # 保存原始 JSON 供数据驱动评估
                    loaded.append(rule)
                except (json.JSONDecodeError, KeyError):
                    continue
        self.rules = sorted(loaded, key=lambda r: r.priority)

    def reload(self):
        """重新加载规则（热更新）"""
        self._load()

    def set_semantic_evaluator(self, evaluator):
        """
        设置语义规则评估器。
        设置后，match() 将优先使用 LLM 语义评估，
        _evaluate_condition 作为 fallback。
        """
        self._semantic_evaluator = evaluator

    def all_rules(self) -> list[Rule]:
        return self.rules

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        for r in self.rules:
            if r.id == rule_id:
                return r
        return None

    # ── 条件匹配 ──

    def match(self, context: Context) -> list[Rule]:
        """
        返回所有匹配当前上下文的规则，按优先级排序。

        如果设置了语义评估器，优先使用 LLM 语义匹配；
        否则回退到 _evaluate_condition 的硬编码关键词匹配。
        """
        if self._semantic_evaluator:
            return self._semantic_evaluator.evaluate(context)

        # fallback: 关键词硬匹配
        matched = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            if self._evaluate_condition(rule, context):
                rule.trigger_count += 1
                matched.append(rule)
        return matched

    def _evaluate_condition(self, rule: Rule, ctx: Context) -> bool:
        """数据驱动规则条件评估（v0.7.1: 从 rules.jsonl 字段驱动）

        每个规则可包含以下评估字段（均在 _load 时解析到 Rule 对象）:
          - trigger_keywords: 关键词列表 → 任意命中即触发
          - trigger_signal_types: 信号类型列表 → 匹配即触发
          - trigger_signal_source: 信号源 → 匹配即触发
          - trigger_confidence_max: 置信度低于此值触发
          - trigger_is_critical: 关键信号时触发
          - trigger_min_memory_hits: 记忆命中数≥此值时触发
          - trigger_always: 永远触发
          - trigger_if_query: 是否对QUERY类型也触发（默认否）
          - 以上字段全部为空时 → 回退到硬编码逻辑
        """
        sig = ctx.signal
        rule_data = getattr(rule, '_raw', {})  # _load 保存的原始JSON

        # ── 数据驱动评估 ──
        keywords = rule_data.get("trigger_keywords", [])
        signal_types = rule_data.get("trigger_signal_types", [])
        signal_source = rule_data.get("trigger_signal_source", "")
        confidence_max = rule_data.get("trigger_confidence_max")
        is_critical_req = rule_data.get("trigger_is_critical")
        min_memory_hits = rule_data.get("trigger_min_memory_hits")
        always_trigger = rule_data.get("trigger_always", False)
        skip_query = not rule_data.get("trigger_if_query", False)

        has_data_driven = bool(keywords or signal_types or signal_source or
                               always_trigger or confidence_max is not None or
                               is_critical_req is not None or min_memory_hits is not None)

        if has_data_driven:
            # 对QUERY信号跳过（除非明确允许）
            if skip_query and sig.type == SignalType.QUERY:
                return False

            # 永远触发
            if always_trigger:
                return True

            # 关键词匹配
            if keywords and self._keyword_match(sig.content, keywords):
                return True

            # 信号类型匹配
            if signal_types and sig.type.value in signal_types:
                return True

            # 信号源匹配
            if signal_source and sig.source.value == signal_source:
                return True

            # 置信度阈值
            if confidence_max is not None and ctx.confidence < confidence_max:
                return True

            # 关键信号 + 记忆命中
            if is_critical_req is not None:
                if is_critical_req and not (ctx.is_critical and len(ctx.memory_hits) >= (min_memory_hits or 1)):
                    return False

            return False

        # ── 硬编码回退（向后兼容无 trigger_* 字段的旧规则）──
        return self._evaluate_condition_legacy(rule, ctx)

    def _evaluate_condition_legacy(self, rule: Rule, ctx: Context) -> bool:
        """旧版硬编码条件评估（仅无 trigger_* 字段时使用）"""
        cid = rule.id
        sig = ctx.signal

        if cid == "rule_006":
            if sig.type == SignalType.QUERY:
                return False
            return self._keyword_match(sig.content,
                ["删除", "发送", "发布", "推送", "deploy", "push", "delete",
                 "send", "publish", "commit", "PR", "merge"])

        if cid == "rule_002":
            return sig.type in (SignalType.CORRECTION, SignalType.DECISION, SignalType.PREFERENCE)

        if cid == "rule_001":
            return self._keyword_match(sig.content,
                ["不对", "错了", "纠正", "不是这样", "重新", "错误", "wrong", "incorrect", "fix"])

        if cid == "rule_003":
            return ctx.confidence < 0.3 or self._keyword_match(sig.content,
                ["失败", "错误", "error", "fail", "不行"])

        if cid == "rule_004":
            return ctx.is_critical and len(ctx.memory_hits) >= 3

        if cid == "rule_005":
            return sig.source.value == "heartbeat"

        if cid == "rule_007":
            return self._keyword_match(sig.content,
                ["你是谁", "你的身份", "介绍自己", "你叫什么", "who are you", "identity"])

        if cid == "rule_008":
            return True

        if cid == "rule_009":
            return sig.type == SignalType.MAINTENANCE

        if cid == "rule_010":
            return sig.source.value == "heartbeat" and ctx.is_critical

        return False

    def _keyword_match(self, text: str, keywords: list[str]) -> bool:
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    # ── 执行 ──

    def execute(self, matched: list[Rule], context: Context) -> list[Decision]:
        """按优先级顺序执行匹配的规则，返回决策列表"""
        decisions = []
        for rule in matched:
            d = Decision(
                action=rule.action,
                matched_rules=[rule.id],
                params={"rule_id": rule.id, "condition": rule.condition},
                reasoning=f"[{rule.id}] {rule.description}",
            )
            decisions.append(d)
        return decisions

    # ── 规则管理 ──

    def add_rule(self, rule: Rule) -> bool:
        """添加新规则（进化管道 Phase3 调用）"""
        if self.get_rule(rule.id):
            return False
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)
        self._persist()
        return True

    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则（进化管道 Phase4 调用）"""
        r = self.get_rule(rule_id)
        if not r:
            return False
        r.enabled = False
        self._persist()
        return True

    def _persist(self):
        """将当前规则写回 JSONL"""
        lines = []
        for r in sorted(self.rules, key=lambda x: x.priority):
            lines.append(json.dumps(r.to_dict(), ensure_ascii=False))
        self.rules_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
