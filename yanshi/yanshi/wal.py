"""
砚识 — WAL 协议实现

Write-Ahead Logging: 关键信号先写入 SESSION-STATE.md，再执行后续动作。
rule_002 的直接实现。
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .models import WALEntry, SignalType

SIGNAL_LABELS: dict[SignalType, str] = {
    SignalType.CORRECTION: "纠正",
    SignalType.DECISION: "决策",
    SignalType.PREFERENCE: "偏好",
    SignalType.COMMAND: "指令",
    SignalType.QUERY: "查询",
    SignalType.MAINTENANCE: "维护",
}


class WALProtocol:
    """先写状态，再执行——保证关键信息不丢失"""

    def __init__(self, workspace_root: str):
        self.root = Path(workspace_root)
        self.session_file = self.root / "SESSION-STATE.md"
        self._ensure_file()

    def _ensure_file(self):
        if not self.session_file.exists():
            self.session_file.write_text(
                "# SESSION-STATE.md — WAL 协议工作记忆\n"
                f"## 当前会话\n- 开始时间: {self._now()}\n"
                f"- 状态: active\n\n"
                "## 信号记录\n\n",
                encoding="utf-8",
            )

    def _now(self) -> str:
        from .models import utc_now
        return utc_now()

    # ── 公共 API ──

    def write(self, entry: WALEntry) -> bool:
        """
        核心方法：先写后响。返回 True 表示写入成功。
        调用方应先调用此方法，再执行后续操作。
        """
        label = SIGNAL_LABELS.get(entry.type, entry.type.value)
        record = (
            f"| {self._now()} | {label} | "
            f"{json.dumps(entry.data, ensure_ascii=False)} |\n"
        )

        try:
            with open(self.session_file, "a", encoding="utf-8") as f:
                f.write(record)
            return True
        except IOError:
            return False

    def read_state(self) -> dict:
        """读取当前会话状态"""
        if not self.session_file.exists():
            return {"status": "no_session"}
        content = self.session_file.read_text(encoding="utf-8")
        return {"status": "active", "content": content, "lines": len(content.splitlines())}

    def get_recent_signals(self, n: int = 20) -> list[dict]:
        """获取最近的 n 条信号记录"""
        if not self.session_file.exists():
            return []
        lines = self.session_file.read_text(encoding="utf-8").splitlines()
        signals = [l for l in lines if l.startswith("| ")]
        return signals[-n:]

    def count_signal_type(self, label: str) -> int:
        """统计某类信号的出现次数（用于模式检测）"""
        if not self.session_file.exists():
            return 0
        content = self.session_file.read_text(encoding="utf-8")
        return content.count(f"| {label} |")


# ── 便捷工厂 ──

def wal_log_correction(wal: WALProtocol, user_input: str, context: str = "") -> bool:
    """记录用户纠正信号"""
    return wal.write(WALEntry(
        type=SignalType.CORRECTION,
        data={"input": user_input, "context": context},
        timestamp=wal._now(),
    ))


def wal_log_decision(wal: WALProtocol, action: str, reasoning: str) -> bool:
    """记录决策信号"""
    return wal.write(WALEntry(
        type=SignalType.DECISION,
        data={"action": action, "reasoning": reasoning},
        timestamp=wal._now(),
    ))
