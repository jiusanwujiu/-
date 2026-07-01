"""
砚识 — 工具链

提供可注册、可发现、可执行的标准工具框架。
"""

from .base import Tool, ToolResult, ToolPermission
from .registry import ToolRegistry, get_registry, reset_registry
from .files import FileReadTool, FileWriteTool, FileListTool
from .shell import ShellExecTool
from .web import WebFetchTool, WebCheckTool
from .memory_tools import MemoryQueryTool, MemoryDistillTool, MemoryStatsTool
from .rules_tools import RuleListTool, RuleToggleTool, RuleReloadTool

__all__ = [
    # 基础
    "Tool", "ToolResult", "ToolPermission",
    # 注册中心
    "ToolRegistry", "get_registry", "reset_registry",
    # 工具
    "FileReadTool", "FileWriteTool", "FileListTool",
    "ShellExecTool",
    "WebFetchTool", "WebCheckTool",
    "MemoryQueryTool", "MemoryDistillTool", "MemoryStatsTool",
    "RuleListTool", "RuleToggleTool", "RuleReloadTool",
]
