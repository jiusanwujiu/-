"""
砚识 — 工具链基础抽象

每个工具分为三层权限：
  READ — 只读操作，自动放行
  WRITE — 写操作，需要 ADL 审查
  EXTERNAL — 外部操作，需要 rule_006 确认
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ToolPermission(str, Enum):
    READ = "read"          # 只读：文件读取、查询、搜索
    WRITE = "write"        # 写操作：文件写入、规则修改
    EXTERNAL = "external"  # 外部：shell 执行、网络请求、部署


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str = ""
    data: Any = None
    error: str = ""
    tool_name: str = ""
    duration_ms: float = 0.0
    permission_used: ToolPermission = ToolPermission.READ

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output[:500],
            "error": self.error,
            "tool": self.tool_name,
            "duration_ms": self.duration_ms,
            "permission": self.permission_used.value,
        }


@dataclass
class Tool:
    """
    工具基类。

    每个工具需要提供：
      - name: 唯一标识
      - description: 用途说明（给 LLM 看的）
      - permission: 权限级别
      - parameters: 参数 schema
      - execute: 执行方法
    """
    name: str
    description: str
    permission: ToolPermission = ToolPermission.READ
    parameters: dict = field(default_factory=dict)

    def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError

    def to_schema(self) -> dict:
        """生成工具的 JSON Schema 描述（供 LLM function calling）"""
        return {
            "name": self.name,
            "description": self.description,
            "permission": self.permission.value,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": list(self.parameters.keys()),
            },
        }
