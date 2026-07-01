"""
砚识工具 — 环境变量工具

提供环境变量只读查询和系统信息获取能力。
权限级别: READ（只读，不修改任何系统状态）
"""

import os
import platform
import sys

from .base import Tool, ToolResult, ToolPermission


class EnvReadTool(Tool):
    """读取环境变量（只读）"""

    SENSITIVE_KEYS = {
        "password", "passwd", "token", "secret", "key", "api_key", "credential",
        "private", "auth", "access_key", "access_token",
    }

    def __init__(self):
        super().__init__(
            name="env_read",
            description="读取指定的环境变量值（只读操作）",
            permission=ToolPermission.READ,
            parameters={
                "name": {"type": "string", "description": "环境变量名（留空则配合 all=true 列出全部）"},
                "all": {"type": "boolean", "description": "列出所有非敏感环境变量"},
            },
        )

    @classmethod
    def _is_sensitive(cls, key: str) -> bool:
        key_lower = key.lower()
        # 拆分+子串匹配，避免 "monkey" 误匹配 "key"
        parts = key_lower.replace("_", " ").replace("-", " ").split()
        return any(s in parts for s in cls.SENSITIVE_KEYS) or \
               any(s in key_lower.split("_") for s in cls.SENSITIVE_KEYS)

    def execute(self, **params) -> ToolResult:
        var_name = params.get("name", "")
        all_vars = params.get("all", False)

        if all_vars:
            result = {}
            sensitive_count = 0
            for k, v in os.environ.items():
                if self._is_sensitive(k):
                    sensitive_count += 1
                    result[k] = "***[敏感变量已隐藏]***"
                else:
                    result[k] = v
            return ToolResult(
                success=True,
                output=f"共 {len(result)} 个环境变量（{sensitive_count} 个敏感变量已隐藏）",
                data={"variables": result, "total": len(result), "sensitive_hidden": sensitive_count},
            )

        if not var_name:
            return ToolResult(success=False, output="请指定变量名或使用 all=true", error="empty input")

        if self._is_sensitive(var_name):
            return ToolResult(
                success=True,
                output="***[敏感变量已隐藏]***",
                data={"name": var_name, "sensitive": True},
            )

        value = os.environ.get(var_name)
        if value is None:
            return ToolResult(
                success=False,
                output=f"环境变量 '{var_name}' 未设置",
                error="not found",
            )

        return ToolResult(
            success=True,
            output=value,
            data={"name": var_name, "value": value, "length": len(value)},
        )


class SysInfoTool(Tool):
    """系统信息查询"""

    def __init__(self):
        super().__init__(
            name="sysinfo",
            description="获取当前系统信息（OS、Python 版本、架构等）",
            permission=ToolPermission.READ,
            parameters={},
        )

    def execute(self, **params) -> ToolResult:
        info = {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "python_implementation": platform.python_implementation(),
            "hostname": platform.node(),
            "cwd": os.getcwd(),
        }
        return ToolResult(
            success=True,
            output=f"{info['system']} {info['release']} | Python {info['python_version'].split()[0]} | {info['architecture']}",
            data=info,
        )
