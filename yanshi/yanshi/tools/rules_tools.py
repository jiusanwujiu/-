"""
砚识 — 规则管理工具

RuleListTool:   列出所有规则（READ）
RuleToggleTool: 启用/禁用规则（WRITE）
RuleReloadTool: 重新加载规则（READ）
"""

from .base import Tool, ToolResult, ToolPermission


class RuleListTool(Tool):
    def __init__(self, rules_engine=None):
        super().__init__(
            name="rule_list",
            description="列出所有已加载的规则及其状态",
            permission=ToolPermission.READ,
            parameters={},
        )
        self._rules = rules_engine

    def set_rules(self, rules_engine):
        self._rules = rules_engine

    def execute(self) -> ToolResult:
        if not self._rules:
            return ToolResult(success=False, error="规则引擎未初始化")

        rules = self._rules.all_rules()
        lines = [f"已加载 {len(rules)} 条规则:"]
        for r in rules:
            status = "+" if r.enabled else "x"
            evo = " [evo]" if r.id.startswith("rule_evo_") else ""
            lines.append(f"  [{status}] {r.id} (P{r.priority}): {r.description} [触发{r.trigger_count}次]{evo}")

        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={
                "total": len(rules),
                "enabled": sum(1 for r in rules if r.enabled),
                "disabled": sum(1 for r in rules if not r.enabled),
            },
        )


class RuleToggleTool(Tool):
    def __init__(self, rules_engine=None):
        super().__init__(
            name="rule_toggle",
            description="启用或禁用指定规则",
            permission=ToolPermission.WRITE,
            parameters={
                "rule_id": {"type": "string", "description": "规则 ID"},
                "enabled": {"type": "boolean", "description": "true=启用, false=禁用"},
            },
        )
        self._rules = rules_engine

    def set_rules(self, rules_engine):
        self._rules = rules_engine

    def execute(self, rule_id: str, enabled: bool) -> ToolResult:
        if not self._rules:
            return ToolResult(success=False, error="规则引擎未初始化")

        rule = self._rules.get_rule(rule_id)
        if not rule:
            return ToolResult(success=False, error=f"规则不存在: {rule_id}")

        if enabled:
            rule.enabled = True
            self._rules._persist()
            return ToolResult(success=True, output=f"已启用规则: {rule_id}")
        else:
            self._rules.disable_rule(rule_id)
            return ToolResult(success=True, output=f"已禁用规则: {rule_id}")


class RuleReloadTool(Tool):
    def __init__(self, rules_engine=None):
        super().__init__(
            name="rule_reload",
            description="从文件重新加载规则（热更新）",
            permission=ToolPermission.READ,
            parameters={},
        )
        self._rules = rules_engine

    def set_rules(self, rules_engine):
        self._rules = rules_engine

    def execute(self) -> ToolResult:
        if not self._rules:
            return ToolResult(success=False, error="规则引擎未初始化")

        before = len(self._rules.all_rules())
        self._rules.reload()
        after = len(self._rules.all_rules())
        return ToolResult(
            success=True,
            output=f"规则已重新加载: {before} → {after}",
            data={"before": before, "after": after},
        )
