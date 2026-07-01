"""
砚识工具 — JSON 处理工具

提供 JSON 解析、验证和格式化能力。
权限级别: READ（仅处理传入的数据，无副作用）
"""

import json

from .base import Tool, ToolResult, ToolPermission


class JsonParseTool(Tool):
    """解析和验证 JSON 字符串"""

    def __init__(self):
        super().__init__(
            name="json_parse",
            description="解析 JSON 字符串，验证其有效性并返回结构化数据",
            permission=ToolPermission.READ,
            parameters={
                "json": {"type": "string", "description": "要解析的 JSON 字符串"},
            },
        )

    def execute(self, **params) -> ToolResult:
        json_str = params.get("json", "")
        if not json_str:
            return ToolResult(success=False, output="未提供 JSON 字符串", error="empty input")

        try:
            data = json.loads(json_str)
            return ToolResult(
                success=True,
                output=f"JSON 解析成功，顶层类型: {type(data).__name__}",
                data={
                    "parsed": data,
                    "type": type(data).__name__,
                    "keys": list(data.keys()) if isinstance(data, dict) else None,
                    "length": len(data) if isinstance(data, (dict, list)) else None,
                },
            )
        except json.JSONDecodeError as e:
            return ToolResult(
                success=False,
                output=f"JSON 解析失败: {e.msg} (第 {e.lineno} 行, 第 {e.colno} 列)",
                error=str(e),
            )


class JsonFormatTool(Tool):
    """美化 JSON 输出"""

    def __init__(self):
        super().__init__(
            name="json_format",
            description="将 JSON 字符串格式化（美化缩进）",
            permission=ToolPermission.READ,
            parameters={
                "json": {"type": "string", "description": "要格式化的 JSON 字符串"},
                "indent": {"type": "integer", "description": "缩进空格数，默认 2"},
                "sort_keys": {"type": "boolean", "description": "是否按 key 排序，默认 false"},
            },
        )

    def execute(self, **params) -> ToolResult:
        json_str = params.get("json", "")
        if not json_str:
            return ToolResult(success=False, output="未提供 JSON 字符串", error="empty input")

        indent = params.get("indent", 2)
        sort_keys = params.get("sort_keys", False)

        try:
            data = json.loads(json_str)
            formatted = json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False)
            return ToolResult(
                success=True,
                output=formatted,
                data={"line_count": formatted.count("\n") + 1},
            )
        except json.JSONDecodeError as e:
            return ToolResult(success=False, output=f"JSON 格式无效: {e.msg}", error=str(e))


class JsonQueryTool(Tool):
    """用点分路径查询 JSON 数据"""

    def __init__(self):
        super().__init__(
            name="json_query",
            description="使用点分路径（如 a.b.0.c）从 JSON 中提取值",
            permission=ToolPermission.READ,
            parameters={
                "json": {"type": "string", "description": "要查询的 JSON 字符串"},
                "path": {"type": "string", "description": "点分路径，如 a.b.0.c"},
            },
        )

    @staticmethod
    def _resolve_path(data, path: str):
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                if part not in current:
                    return None, f"键 '{part}' 不存在"
                current = current[part]
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    if idx < 0 or idx >= len(current):
                        return None, f"索引 {idx} 超出范围 (长度 {len(current)})"
                    current = current[idx]
                except ValueError:
                    return None, f"'{part}' 不是有效的列表索引"
            else:
                return None, f"无法从 {type(current).__name__} 类型中访问 '{part}'"
        return current, None

    def execute(self, **params) -> ToolResult:
        json_str = params.get("json", "")
        path = params.get("path", "")

        if not json_str:
            return ToolResult(success=False, output="未提供 JSON 字符串", error="empty input")
        if not path:
            return ToolResult(success=False, output="未提供查询路径", error="empty path")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return ToolResult(success=False, output=f"JSON 解析失败: {e.msg}", error=str(e))

        value, error = self._resolve_path(data, path)
        if error:
            return ToolResult(success=False, output=error, error=error)

        return ToolResult(
            success=True,
            output=str(value),
            data={"path": path, "value": value, "type": type(value).__name__},
        )
