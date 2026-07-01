"""
砚识 — 记忆系统工具

MemoryQueryTool:  查询知识图谱实体（READ）
MemoryDistillTool: 触发记忆蒸馏（WRITE）
MemoryStatsTool:   获取记忆系统统计（READ）
"""

from .base import Tool, ToolResult, ToolPermission


class MemoryQueryTool(Tool):
    def __init__(self, memory_sys=None):
        super().__init__(
            name="memory_query",
            description="查询知识图谱中的实体和关系",
            permission=ToolPermission.READ,
            parameters={
                "entity": {"type": "string", "description": "要查询的实体名称"},
            },
        )
        self._memory = memory_sys

    def set_memory(self, memory_sys):
        self._memory = memory_sys

    def execute(self, entity: str) -> ToolResult:
        if not self._memory:
            return ToolResult(success=False, error="记忆系统未初始化")

        results = self._memory.query_entity(entity)
        if not results:
            return ToolResult(success=True, output=f"未找到实体: {entity}", data={"entity": entity, "results": []})

        lines = [f"实体: {entity}"]
        for r in results:
            lines.append(f"  → {r.get('relation', '?')} → {r.get('target', '?')}")
        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={"entity": entity, "count": len(results), "results": results},
        )


class MemoryDistillTool(Tool):
    def __init__(self, memory_sys=None):
        super().__init__(
            name="memory_distill",
            description="蒸馏超过指定天数的记忆到长期存储",
            permission=ToolPermission.WRITE,
            parameters={
                "days": {"type": "integer", "description": "蒸馏天数阈值，默认 30"},
            },
        )
        self._memory = memory_sys

    def set_memory(self, memory_sys):
        self._memory = memory_sys

    def execute(self, days: int = 30) -> ToolResult:
        if not self._memory:
            return ToolResult(success=False, error="记忆系统未初始化")

        distilled = self._memory.distill(days=days)
        return ToolResult(
            success=True,
            output=f"蒸馏完成: {len(distilled)} 条" if distilled else "无需要蒸馏的数据",
            data={"days": days, "distilled_count": len(distilled), "items": distilled},
        )


class MemoryStatsTool(Tool):
    def __init__(self, memory_sys=None):
        super().__init__(
            name="memory_stats",
            description="获取记忆系统的统计信息",
            permission=ToolPermission.READ,
            parameters={},
        )
        self._memory = memory_sys

    def set_memory(self, memory_sys):
        self._memory = memory_sys

    def execute(self) -> ToolResult:
        if not self._memory:
            return ToolResult(success=False, error="记忆系统未初始化")

        stats = self._memory.ontology_stats()
        log_size = self._memory.log_size_today()
        lines = [
            f"今日日志: {log_size} 行",
            f"知识图谱: {stats.get('entities', 0)} 实体, {stats.get('relations', 0)} 关系",
        ]
        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={"log_size": log_size, "entities": stats.get("entities", 0), "relations": stats.get("relations", 0)},
        )
