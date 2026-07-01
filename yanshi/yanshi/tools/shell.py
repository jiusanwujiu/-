"""
砚识 — Shell 执行工具

ShellExecTool: 在沙箱中执行 Shell 命令（EXTERNAL）
需要 rule_006 安全确认后才能执行。
"""

import subprocess
from .base import Tool, ToolResult, ToolPermission


class ShellExecTool(Tool):
    def __init__(self, workspace_root: str = ".", timeout_seconds: int = 30,
                 danger_commands: list[str] = None):
        super().__init__(
            name="shell_exec",
            description="在沙箱中执行 Shell 命令。需要安全确认。",
            permission=ToolPermission.EXTERNAL,
            parameters={
                "command": {"type": "string", "description": "要执行的命令"},
                "timeout_seconds": {"type": "integer", "description": f"超时时间（秒），默认 {timeout_seconds}"},
            },
        )
        self.workspace_root = workspace_root
        self.default_timeout = timeout_seconds
        self.danger_commands = danger_commands or [
            "rm -rf /", "rm -rf ~", "dd if=", "mkfs", ":(){ :|:& };:",
            "> /dev/sda", "> /dev/hda",
            "chmod 777 /", "chmod -R 777 /",
            "del /F /S /Q C:", "format C:",
            "shutdown", "reboot", "halt",
            "curl", "wget",
        ]

    def execute(self, command: str, timeout_seconds: int = None) -> ToolResult:
        if timeout_seconds is None:
            timeout_seconds = self.default_timeout
        # 安全检查：使用配置的危险命令列表
        dangerous = self.danger_commands
        cmd_lower = command.lower()
        cmd_tokens = cmd_lower.replace(";", " ").replace("|", " ").replace("&", " ").split()
        for d in dangerous:
            if d.lower() in cmd_tokens or d.lower() in cmd_lower.split()[0:2]:
                return ToolResult(
                    success=False,
                    error=f"危险命令已拦截: {d}",
                )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=self.workspace_root,
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            return ToolResult(
                success=result.returncode == 0,
                output=output[:2000],
                data={
                    "exit_code": result.returncode,
                    "stdout_len": len(result.stdout),
                    "stderr_len": len(result.stderr),
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"命令超时 ({timeout_seconds}s): {command[:80]}",
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
