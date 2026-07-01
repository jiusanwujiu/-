"""
砚识 — 网络请求工具

WebFetchTool:  发送 HTTP GET 请求获取网页内容（EXTERNAL）
WebCheckTool:  检查 URL 可达性（EXTERNAL）
"""

import urllib.request
import urllib.error
from .base import Tool, ToolResult, ToolPermission


class WebFetchTool(Tool):
    def __init__(self):
        super().__init__(
            name="web_fetch",
            description="获取指定 URL 的内容（HTML/JSON/文本）",
            permission=ToolPermission.EXTERNAL,
            parameters={
                "url": {"type": "string", "description": "要请求的 URL"},
                "timeout_seconds": {"type": "integer", "description": "超时时间（秒），默认 10"},
            },
        )

    def execute(self, url: str, timeout_seconds: int = 10) -> ToolResult:
        if not url.startswith(("http://", "https://")):
            return ToolResult(success=False, error=f"无效 URL 协议: {url}")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Yanshi/0.8"})
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                status = resp.status
                content_type = resp.headers.get("Content-Type", "unknown")

            # 截断过长内容
            preview = content[:2000]
            if len(content) > 2000:
                preview += f"\n... (省略 {len(content) - 2000} 字符)"

            return ToolResult(
                success=True,
                output=preview,
                data={
                    "url": url,
                    "status": status,
                    "content_type": content_type,
                    "size": len(content),
                },
            )
        except urllib.error.HTTPError as e:
            return ToolResult(
                success=False,
                error=f"HTTP {e.code}: {e.reason}",
                data={"url": url, "status": e.code},
            )
        except urllib.error.URLError as e:
            return ToolResult(success=False, error=f"连接失败: {e.reason}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WebCheckTool(Tool):
    def __init__(self):
        super().__init__(
            name="web_check",
            description="检查 URL 是否可达（只返回状态码，不下载内容）",
            permission=ToolPermission.EXTERNAL,
            parameters={
                "url": {"type": "string", "description": "要检查的 URL"},
            },
        )

    def execute(self, url: str) -> ToolResult:
        if not url.startswith(("http://", "https://")):
            return ToolResult(success=False, error=f"无效 URL 协议: {url}")

        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Yanshi/0.8"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return ToolResult(
                    success=True,
                    output=f"可达: HTTP {resp.status}",
                    data={"url": url, "status": resp.status},
                )
        except urllib.error.HTTPError as e:
            return ToolResult(success=True, output=f"可达: HTTP {e.code}", data={"url": url, "status": e.code})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
