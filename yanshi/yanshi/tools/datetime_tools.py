"""
砚识工具 — 日期时间工具

提供时间查询、格式化和计算能力。
权限级别: READ（仅读取，无副作用）
"""

import time
from datetime import datetime, timezone

from .base import Tool, ToolResult, ToolPermission


class DateTimeTool(Tool):
    """获取当前日期时间和格式化"""

    def __init__(self):
        super().__init__(
            name="datetime",
            description="获取当前日期时间，支持格式化输出",
            permission=ToolPermission.READ,
            parameters={
                "format": {"type": "string", "description": "日期格式字符串，默认 %Y-%m-%d %H:%M:%S"},
                "utc": {"type": "boolean", "description": "是否使用 UTC 时间，默认 false"},
            },
        )

    def execute(self, **params) -> ToolResult:
        format_str = params.get("format", "%Y-%m-%d %H:%M:%S")
        utc = params.get("utc", False)

        try:
            now = datetime.now(timezone.utc) if utc else datetime.now()
            formatted = now.strftime(format_str)
            return ToolResult(
                success=True,
                output=formatted,
                data={
                    "iso": now.isoformat(),
                    "timestamp": int(now.timestamp()),
                    "timezone": "UTC" if utc else "local",
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=str(e), error=str(e))


class TimeDiffTool(Tool):
    """计算两个时间之间的差异"""

    def __init__(self):
        super().__init__(
            name="timediff",
            description="计算两个时间戳之间的差异（秒/分钟/小时/天）",
            permission=ToolPermission.READ,
            parameters={
                "start": {"type": "string", "description": "起始时间 ISO 格式，默认当前时间"},
                "end": {"type": "string", "description": "结束时间 ISO 格式，默认当前时间"},
                "unit": {"type": "string", "description": "输出单位: seconds/minutes/hours/days"},
            },
        )

    def execute(self, **params) -> ToolResult:
        start_str = params.get("start", "")
        end_str = params.get("end", "")
        unit = params.get("unit", "seconds")

        try:
            start = datetime.fromisoformat(start_str) if start_str else datetime.now()
            end = datetime.fromisoformat(end_str) if end_str else datetime.now()
        except ValueError as e:
            return ToolResult(success=False, output=f"日期格式无效: {e}", error=str(e))

        diff = end - start
        total_seconds = abs(diff.total_seconds())

        conversions = {
            "seconds": total_seconds,
            "minutes": total_seconds / 60,
            "hours": total_seconds / 3600,
            "days": total_seconds / 86400,
        }
        result_value = conversions.get(unit, total_seconds)

        return ToolResult(
            success=True,
            output=f"{diff} ({result_value:.2f} {unit})",
            data={
                "difference": str(diff),
                "seconds": total_seconds,
                "minutes": total_seconds / 60,
                "hours": total_seconds / 3600,
                "days": total_seconds / 86400,
                "direction": "未来" if end > start else "过去",
            },
        )


class TimestampTool(Tool):
    """Unix 时间戳转换"""

    def __init__(self):
        super().__init__(
            name="timestamp",
            description="Unix 时间戳与可读日期互转",
            permission=ToolPermission.READ,
            parameters={
                "ts": {"type": "number", "description": "Unix 时间戳（秒）"},
                "datetime": {"type": "string", "description": "ISO 格式日期时间"},
            },
        )

    def execute(self, **params) -> ToolResult:
        ts = params.get("ts")
        dt_str = params.get("datetime")

        try:
            if ts is not None:
                dt = datetime.fromtimestamp(float(ts))
                return ToolResult(
                    success=True,
                    output=dt.strftime("%Y-%m-%d %H:%M:%S"),
                    data={
                        "datetime": dt.isoformat(),
                        "timestamp": float(ts),
                        "weekday": dt.strftime("%A"),
                        "week_number": dt.isocalendar()[1],
                    },
                )
            elif dt_str:
                dt = datetime.fromisoformat(dt_str)
                return ToolResult(
                    success=True,
                    output=str(int(dt.timestamp())),
                    data={
                        "datetime": dt.isoformat(),
                        "timestamp": int(dt.timestamp()),
                        "weekday": dt.strftime("%A"),
                    },
                )
            else:
                now_ts = int(time.time())
                return ToolResult(
                    success=True,
                    output=str(now_ts),
                    data={"timestamp": now_ts, "datetime": datetime.now().isoformat()},
                )
        except Exception as e:
            return ToolResult(success=False, output=str(e), error=str(e))
