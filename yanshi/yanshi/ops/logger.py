"""
砚识 — 结构化日志系统

支持：
  - 四个级别: DEBUG, INFO, WARNING, ERROR
  - 结构化 JSON 格式（便于运维分析）
  - 控制台 + 文件双输出
  - 自动轮转（按文件大小）
"""

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    @property
    def priority(self) -> int:
        """数值优先级（数值越大越严重），用于级别过滤。"""
        return {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}[self.value]

    def __ge__(self, other: "LogLevel") -> bool:
        return self.priority >= other.priority if isinstance(other, LogLevel) else False

    @classmethod
    def from_str(cls, s: str) -> "LogLevel":
        s = s.upper()
        for level in cls:
            if level.value == s:
                return level
        return cls.INFO


class StructuredLogger:
    """
    结构化日志器。

    用法:
      logger = StructuredLogger(workspace_root, level="INFO")
      logger.info("engine.start", cycle=1, backend="mock")
      logger.warning("rule.match", rule_id="rule_006", blocked=True)
      logger.error("tool.execute", tool="file_read", error="file not found")
    """

    def __init__(self, workspace_root: str, level: str = "INFO",
                 console: bool = True, max_size_mb: int = 10):
        self.workspace = Path(workspace_root)
        self.level = LogLevel.from_str(level)
        self.console = console
        self.max_size = max_size_mb * 1024 * 1024  # 转换为字节

        # 日志目录
        self.log_dir = self.workspace / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 当前日志文件
        self._current_file = self.log_dir / "yanshi.log"
        self._entry_count = 0  # 当前会话写入条数

    def debug(self, event: str, **kwargs):
        self._log(LogLevel.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs):
        self._log(LogLevel.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs):
        self._log(LogLevel.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs):
        self._log(LogLevel.ERROR, event, **kwargs)

    def _log(self, level: LogLevel, event: str, **kwargs):
        """写入一条结构化日志"""
        if level.priority < self.level.priority:
            return

        now = datetime.now(timezone.utc)
        entry = {
            "ts": now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": level.value,
            "event": event,
        }
        entry.update(kwargs)

        line = json.dumps(entry, ensure_ascii=False)
        self._entry_count += 1

        # 控制台输出
        if self.console:
            prefix = {"DEBUG": "[D]", "INFO": "[I]", "WARNING": "[W]", "ERROR": "[E]"}[level.value]
            print(f"{prefix} {event} {json.dumps(kwargs, ensure_ascii=False) if kwargs else ''}")

        # 文件写入
        self._write_file(line)

        # 检查是否需要轮转
        if self._current_file.exists() and self._current_file.stat().st_size > self.max_size:
            self._rotate()

    def _write_file(self, line: str):
        """追加写入日志文件"""
        with open(self._current_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _rotate(self):
        """轮转日志文件"""
        for i in range(5, 0, -1):
            old = self.log_dir / f"yanshi.log.{i}"
            new = self.log_dir / f"yanshi.log.{i + 1}"
            if old.exists():
                old.rename(new)
        backup = self.log_dir / "yanshi.log.1"
        self._current_file.rename(backup)

    def flush(self):
        """手动刷新（文件已实时写入，此方法为兼容性保留）"""
        pass

    def get_recent(self, count: int = 50, level: Optional[str] = None) -> list[dict]:
        """读取最近的日志条目"""
        if not self._current_file.exists():
            return []

        entries = []
        with open(self._current_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if level and entry.get("level") != level.upper():
                        continue
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue

        return entries[-count:]

    def statistics(self) -> dict:
        """日志统计信息"""
        if not self._current_file.exists():
            return {"total_lines": 0, "by_level": {}, "file_size_mb": 0}

        by_level = {l.value: 0 for l in LogLevel}
        total = 0
        with open(self._current_file, "r", encoding="utf-8") as f:
            for line in f:
                total += 1
                try:
                    entry = json.loads(line.strip())
                    lv = entry.get("level", "")
                    if lv in by_level:
                        by_level[lv] += 1
                except json.JSONDecodeError:
                    pass

        return {
            "total_lines": total,
            "by_level": by_level,
            "file_size_mb": round(self._current_file.stat().st_size / 1024 / 1024, 2),
        }
