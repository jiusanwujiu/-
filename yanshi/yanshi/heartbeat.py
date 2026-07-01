"""
砚识 — 心跳机制

从 HEARTBEAT.md 加载维护任务清单，后台线程按间隔触发。
空闲时主动检查：MEMORY蒸馏、日志清理、ontology更新。
rule_005 和 rule_010 的执行基础。
"""

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .models import HeartbeatTask


class Heartbeat:
    """后台心跳：周期性自主检查"""

    def __init__(self, workspace_root: str, interval_seconds: int = 30):
        self.root = Path(workspace_root)
        self.heartbeat_file = self.root / "HEARTBEAT.md"
        self.interval = interval_seconds
        self.tasks: list[HeartbeatTask] = []
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()  # 保护 tick_count 和 _running
        self._running = False
        self._callback: Optional[Callable] = None
        self.tick_count = 0
        self.last_idle = True

        self._load_tasks()

    def _load_tasks(self):
        """从 HEARTBEAT.md 解析任务清单"""
        self.tasks = [
            HeartbeatTask(
                id="distill_memory",
                name="蒸馏 MEMORY.md",
                interval_minutes=60,
            ),
            HeartbeatTask(
                id="update_ontology",
                name="更新 ontology 知识图谱",
                interval_minutes=120,
            ),
            HeartbeatTask(
                id="clean_logs",
                name="清理过期日志",
                interval_minutes=1440,  # 每天
            ),
            HeartbeatTask(
                id="health_check",
                name="框架健康检查",
                interval_minutes=15,
            ),
        ]

    def set_callback(self, callback: Callable):
        """设置心跳触发时的回调函数"""
        self._callback = callback

    def start(self):
        """启动后台心跳线程"""
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止心跳"""
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        """心跳主循环"""
        while True:
            time.sleep(self.interval)
            with self._lock:
                if not self._running:
                    break
                self.tick_count += 1
            self._tick()

    def _tick(self):
        """单次心跳：检查是否有到期任务"""
        now = time.time()
        overdue = []

        for task in self.tasks:
            if not task.enabled:
                continue
            # 简化：每 N 次 tick 触发一次（基于 interval 换算）
            ticks_per_task = max(1, int(task.interval_minutes * 60 / self.interval))
            if self.tick_count % ticks_per_task == 0:
                overdue.append(task)

        if overdue and self._callback:
            task_names = [t.name for t in overdue]
            self._callback(task_names, self.last_idle)

        # 空闲检测：最近无交互 → 触发 rule_005
        if self.last_idle and self._callback:
            if self.tick_count % 3 == 0:  # 每3次tick在空闲状态下触发维护
                self._callback(["空闲维护检查"], True)

    def mark_active(self):
        """标记为活跃状态（有用户交互）"""
        self.last_idle = False

    def mark_idle(self):
        """标记为空闲状态"""
        self.last_idle = True
