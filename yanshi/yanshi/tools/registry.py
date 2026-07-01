"""
砚识 — 工具注册中心

全局工具注册、发现、执行框架。
支持装饰器注册和手动注册两种方式。
"""

from typing import Optional
from .base import Tool, ToolResult, ToolPermission


class ToolRegistry:
    """
    工具注册中心。

    用法:
      registry = ToolRegistry()
      registry.register(MyTool())
      result = registry.execute("tool_name", **kwargs)
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._stats: dict[str, int] = {}  # 工具调用统计

    def register(self, tool: Tool) -> None:
        """注册一个工具"""
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册")
        self._tools[tool.name] = tool
        self._stats[tool.name] = 0

    def unregister(self, name: str) -> bool:
        """注销一个工具"""
        if name in self._tools:
            del self._tools[name]
            self._stats.pop(name, None)
            return True
        return False

    def get(self, name: str) -> Optional[Tool]:
        """获取工具实例"""
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        """列出所有已注册工具（概要）"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "permission": t.permission.value,
                "call_count": self._stats.get(t.name, 0),
            }
            for t in sorted(self._tools.values(), key=lambda x: x.permission.value)
        ]

    def list_by_permission(self, permission: ToolPermission) -> list[Tool]:
        """按权限级别筛选工具"""
        return [t for t in self._tools.values() if t.permission == permission]

    def execute(self, name: str, **kwargs) -> ToolResult:
        """
        执行指定工具。

        返回 ToolResult，即使工具内部抛异常也会捕获并返回失败结果。
        """
        import time

        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"未找到工具: {name}",
                tool_name=name,
            )

        start = time.perf_counter()
        try:
            result = tool.execute(**kwargs)
            self._stats[name] += 1
            result.tool_name = name
            result.permission_used = tool.permission
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result
        except Exception as e:
            self._stats[name] += 1
            return ToolResult(
                success=False,
                error=str(e),
                tool_name=name,
                permission_used=tool.permission,
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def get_stats(self) -> dict:
        """获取工具调用统计"""
        return {
            "total_calls": sum(self._stats.values()),
            "tool_stats": dict(self._stats),
            "registered_count": len(self._tools),
        }

    def count(self) -> int:
        """已注册工具数量"""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# ── 全局注册中心 ──

_global_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """获取全局工具注册中心（懒加载单例）"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_registry():
    """重置全局注册中心（测试用）"""
    global _global_registry
    _global_registry = ToolRegistry()
