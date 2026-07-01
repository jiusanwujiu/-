"""
砚识 — 文件操作工具

FileReadTool:  读取文件内容（READ）
FileWriteTool: 写入文件内容（WRITE）
FileListTool:  列出目录内容（READ）
"""

from pathlib import Path
from .base import Tool, ToolResult, ToolPermission


class FileReadTool(Tool):
    def __init__(self, max_lines: int = 500):
        self.default_max_lines = max_lines
        super().__init__(
            name="file_read",
            description="读取指定路径的文件内容",
            permission=ToolPermission.READ,
            parameters={
                "path": {"type": "string", "description": "文件路径（绝对路径）"},
                "max_lines": {"type": "integer", "description": f"最大读取行数，默认 {max_lines}"},
            },
        )

    def execute(self, path: str, max_lines: int = None) -> ToolResult:
        if max_lines is None:
            max_lines = self.default_max_lines
        p = Path(path)
        if not p.exists():
            return ToolResult(success=False, error=f"文件不存在: {path}")
        if p.is_dir():
            return ToolResult(success=False, error=f"路径是目录: {path}")

        try:
            content = p.read_text(encoding="utf-8")
            lines = content.splitlines()
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines])
                content += f"\n... (省略 {len(lines) - max_lines} 行，共 {len(lines)} 行)"
            return ToolResult(
                success=True,
                output=content,
                data={"path": str(p), "size": p.stat().st_size, "lines": len(lines)},
            )
        except UnicodeDecodeError:
            return ToolResult(success=True, output=f"[二进制文件: {p.stat().st_size} bytes]")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileWriteTool(Tool):
    def __init__(self):
        super().__init__(
            name="file_write",
            description="向指定路径写入内容（覆盖模式）",
            permission=ToolPermission.WRITE,
            parameters={
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "要写入的内容"},
            },
        )

    def execute(self, path: str, content: str) -> ToolResult:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            size = len(content.encode("utf-8"))
            return ToolResult(
                success=True,
                output=f"已写入 {p} ({size} bytes)",
                data={"path": str(p), "size": size},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileListTool(Tool):
    def __init__(self):
        super().__init__(
            name="file_list",
            description="列出指定目录的内容",
            permission=ToolPermission.READ,
            parameters={
                "path": {"type": "string", "description": "目录路径"},
            },
        )

    def execute(self, path: str) -> ToolResult:
        p = Path(path)
        if not p.exists():
            return ToolResult(success=False, error=f"路径不存在: {path}")
        if not p.is_dir():
            return ToolResult(success=False, error=f"不是目录: {path}")

        try:
            items = []
            for item in sorted(p.iterdir()):
                suffix = "/" if item.is_dir() else ""
                items.append(f"  {item.name}{suffix}")
            output = "\n".join(items) if items else "  (空目录)"
            return ToolResult(
                success=True,
                output=output,
                data={"path": str(p), "count": len(items)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
