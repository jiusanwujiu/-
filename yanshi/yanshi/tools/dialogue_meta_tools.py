"""
砚识 v0.8 — 对话记忆 + 元认知工具

dialogue_history: 查看对话历史和上下文
dialogue_stats: 对话统计
meta_reflect: 触发元认知反思
meta_report: 生成元认知报告
"""

from .base import Tool, ToolResult, ToolPermission


class DialogueHistoryTool(Tool):
    """查看对话历史和上下文"""

    def __init__(self, dialogue_memory):
        self.dm = dialogue_memory
        super().__init__(
            name="dialogue_history",
            description="查看对话历史、当前上下文和未解决问题",
            permission=ToolPermission.READ,
            parameters={
                "format": {"type": "string", "description": "输出格式: text(默认) 或 json"},
            },
        )

    def execute(self, **params) -> ToolResult:
        fmt = params.get("format", "text")
        if fmt == "json":
            import json
            ctx = self.dm.get_context()
            return ToolResult(
                success=True,
                output=json.dumps(ctx, ensure_ascii=False, indent=2),
                data=ctx,
            )
        else:
            text = self.dm.get_context_text()
            return ToolResult(success=True, output=text, data={"total_turns": self.dm.turn_count})


class DialogueStatsTool(Tool):
    """对话统计"""

    def __init__(self, dialogue_memory):
        self.dm = dialogue_memory
        super().__init__(
            name="dialogue_stats",
            description="获取对话记忆统计（轮次、主题、摘要数等）",
            permission=ToolPermission.READ,
            parameters={},
        )

    def execute(self, **params) -> ToolResult:
        stats = self.dm.stats()
        lines = [
            f"总轮次: {stats['total_turns']}",
            f"窗口内: {stats['in_window']}",
            f"用户轮次: {stats['user_turns']}",
            f"助手轮次: {stats['assistant_turns']}",
            f"失败轮次: {stats['failed_turns']}",
            f"摘要数: {stats['summaries']}",
            f"当前主题: {stats['current_topic']}",
            f"使用工具数: {stats['unique_tools']}",
            f"平均置信度: {stats['avg_confidence']}",
        ]
        return ToolResult(
            success=True,
            output="\n".join(lines),
            data=stats,
        )


class MetaReflectTool(Tool):
    """触发元认知反思"""

    def __init__(self, metacog_engine, axiom_journal=None):
        self.meta = metacog_engine
        self.journal = axiom_journal
        super().__init__(
            name="meta_reflect",
            description="触发元认知反思，分析决策模式、置信度校准和信条趋势",
            permission=ToolPermission.READ,
            parameters={
                "cycle": {"type": "integer", "description": "指定周期号（默认当前）"},
            },
        )

    def execute(self, **params) -> ToolResult:
        cycle = params.get("cycle", 0) or self.meta._records[-1]["cycle"] if self.meta._records else 0

        axiom_history = []
        if self.journal and hasattr(self.journal, '_scores'):
            axiom_history = [s.total() for s in self.journal._scores[-20:]]

        snap = self.meta.reflect(cycle=cycle, axiom_history=axiom_history)
        return ToolResult(
            success=True,
            output=self.meta.report_text(),
            data=snap.to_dict(),
        )


class MetaReportTool(Tool):
    """生成元认知趋势报告"""

    def __init__(self, metacog_engine):
        self.meta = metacog_engine
        super().__init__(
            name="meta_report",
            description="生成元认知趋势报告（跨快照分析）",
            permission=ToolPermission.READ,
            parameters={},
        )

    def execute(self, **params) -> ToolResult:
        snap = self.meta.latest_snapshot()
        if not snap:
            return ToolResult(success=True, output="尚无元认知快照，请先运行 meta_reflect", data={})

        trend = self.meta.trend()
        lines = [
            f"快照数: {self.meta.snapshot_count}",
            f"最新周期: #{snap.cycle}",
            f"校准状态: {snap.calibration}",
            f"信条趋势: {snap.axiom_trend} (均{snap.axiom_avg:.1f})",
            f"阻止率: {snap.blocked_rate:.0%}",
            f"平均置信: {snap.avg_confidence:.2f}",
            f"工具失败率: {snap.tool_failure_rate:.0%}",
            f"主导动作: {snap.dominant_action}",
            f"动作多样性: {snap.action_diversity}",
        ]

        if snap.insights:
            lines.append("\n洞察:")
            for ins in snap.insights:
                lines.append(f"  • {ins}")

        if snap.recommendations:
            lines.append("\n建议:")
            for rec in snap.recommendations:
                lines.append(f"  → {rec}")

        if trend.get("status") != "insufficient-data":
            lines.append(f"\n趋势: {trend}")

        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={"snapshot": snap.to_dict(), "trend": trend},
        )
