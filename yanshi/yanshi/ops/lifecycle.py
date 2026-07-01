"""
砚识 — 生命周期管理

管理引擎的启动、运行、停止全生命周期。
支持信号处理（SIGINT/SIGTERM）和优雅关闭。
"""

import signal
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class LifecycleState(str, Enum):
    INIT = "init"          # 初始化中
    STARTING = "starting"  # 启动中
    RUNNING = "running"    # 运行中
    PAUSED = "paused"      # 暂停
    STOPPING = "stopping"  # 停止中
    STOPPED = "stopped"    # 已停止
    ERROR = "error"        # 错误状态


class LifecycleManager:
    """
    生命周期管理器。

    生命周期: INIT → STARTING → RUNNING ↔ PAUSED → STOPPING → STOPPED

    用法:
      lm = LifecycleManager(workspace_root)
      lm.on_start(lambda: print("启动中..."))
      lm.on_stop(lambda: print("关闭中..."))
      lm.start()
      ...
      lm.stop()
    """

    def __init__(self, workspace_root: str = "."):
        self.workspace = Path(workspace_root)
        self.state = LifecycleState.INIT
        self._started_at: Optional[str] = None
        self._stopped_at: Optional[str] = None

        # 回调
        self._on_start_callbacks: list[Callable] = []
        self._on_stop_callbacks: list[Callable] = []
        self._on_pause_callbacks: list[Callable] = []
        self._on_resume_callbacks: list[Callable] = []

        # 状态文件
        self._state_file = self.workspace / "SESSION-STATE.md"

        # 注册信号处理
        self._register_signals()

    def _register_signals(self):
        """注册操作系统信号处理"""
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._signal_handler)
            except (ValueError, OSError):
                pass  # 非主线程时忽略

    def _signal_handler(self, signum, frame):
        """信号处理：优雅关闭"""
        sig_name = signal.Signals(signum).name
        print(f"\n[Lifecycle] 收到信号 {sig_name}，正在优雅关闭...")
        self.stop()

    # ── 回调注册 ──

    def on_start(self, fn: Callable):
        self._on_start_callbacks.append(fn)

    def on_stop(self, fn: Callable):
        self._on_stop_callbacks.append(fn)

    def on_pause(self, fn: Callable):
        self._on_pause_callbacks.append(fn)

    def on_resume(self, fn: Callable):
        self._on_resume_callbacks.append(fn)

    # ── 状态转换 ──

    def start(self) -> bool:
        """启动引擎"""
        if self.state not in (LifecycleState.INIT, LifecycleState.STOPPED):
            return False

        self.state = LifecycleState.STARTING
        self._started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            for cb in self._on_start_callbacks:
                cb()
            self.state = LifecycleState.RUNNING
            self._write_state()
            return True
        except Exception as e:
            self.state = LifecycleState.ERROR
            print(f"[Lifecycle] 启动失败: {e}")
            return False

    def stop(self) -> bool:
        """停止引擎"""
        if self.state in (LifecycleState.STOPPING, LifecycleState.STOPPED):
            return False

        self.state = LifecycleState.STOPPING
        self._stopped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for cb in self._on_stop_callbacks:
            try:
                cb()
            except Exception as e:
                print(f"[Lifecycle] 关闭回调异常: {e}")

        self.state = LifecycleState.STOPPED
        self._write_state()
        return True

    def pause(self) -> bool:
        """暂停引擎"""
        if self.state != LifecycleState.RUNNING:
            return False

        self.state = LifecycleState.PAUSED
        for cb in self._on_pause_callbacks:
            try:
                cb()
            except Exception:
                pass
        return True

    def resume(self) -> bool:
        """恢复引擎"""
        if self.state != LifecycleState.PAUSED:
            return False

        self.state = LifecycleState.RUNNING
        for cb in self._on_resume_callbacks:
            try:
                cb()
            except Exception:
                pass
        return True

    # ── 状态查询 ──

    def is_running(self) -> bool:
        return self.state == LifecycleState.RUNNING

    def is_stopped(self) -> bool:
        return self.state == LifecycleState.STOPPED

    def uptime_seconds(self) -> float:
        """运行时长（秒）"""
        if not self._started_at:
            return 0
        start = datetime.fromisoformat(self._started_at)
        now = datetime.now(timezone.utc)
        return (now - start).total_seconds()

    def status_report(self) -> dict:
        """生成状态报告"""
        return {
            "state": self.state.value,
            "started_at": self._started_at,
            "stopped_at": self._stopped_at,
            "uptime_seconds": self.uptime_seconds(),
        }

    def _write_state(self):
        """写入状态文件（WAL 协议兼容）"""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = f"| {now} | 生命周期 | {{\"state\": \"{self.state.value}\"}} |\n"
        try:
            with open(self._state_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass
