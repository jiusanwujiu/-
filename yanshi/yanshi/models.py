"""
砚识 — 核心数据模型

定义六层循环中流转的标准化数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SignalSource(str, Enum):
    USER_INPUT = "user_input"
    HEARTBEAT = "heartbeat"
    CRON = "cron"


class SignalType(str, Enum):
    CORRECTION = "correction"
    DECISION = "decision"
    PREFERENCE = "preference"
    COMMAND = "command"
    QUERY = "query"
    MAINTENANCE = "maintenance"


class RulePriority(int, Enum):
    """规则优先级：数字越小越优先"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


class EvolutionPhase(str, Enum):
    SIGNAL = "phase1_signal"
    VERIFY = "phase2_verify"
    PROMOTE = "phase3_promote"
    RETIRE = "phase4_retire"


class ADLViolation(str, Enum):
    COMPLEXITY = "为复杂而复杂"
    ABSTRACTION = "抽象成瘾"
    NOVELTY = "新颖崇拜"
    INFLATION = "自我膨胀"


# ── 六层循环数据对象 ──

@dataclass
class Signal:
    """感知层输出：规范化后的输入信号"""
    source: SignalSource
    type: SignalType
    content: str
    raw: Any = None
    timestamp: str = ""


@dataclass
class Context:
    """理解层输出：理解后的上下文"""
    signal: Signal
    intent: str = ""
    matched_rules: list[str] = field(default_factory=list)
    memory_hits: list[str] = field(default_factory=list)
    is_critical: bool = False
    confidence: float = 0.0
    tool_params: dict = field(default_factory=dict)


@dataclass
class Decision:
    """决策层输出：执行决策"""
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    matched_rules: list[str] = field(default_factory=list)
    vfm_score: int = 0
    adl_violations: list[ADLViolation] = field(default_factory=list)
    approved: bool = True
    reasoning: str = ""


@dataclass
class ActionResult:
    """执行层输出：执行结果"""
    success: bool
    output: str
    errors: list[str] = field(default_factory=list)
    wal_written: bool = False
    tool_used: str = ""


@dataclass
class Reflection:
    """反思层输出：反思结果"""
    corrections: list[str] = field(default_factory=list)
    learnings: list[str] = field(default_factory=list)
    patterns_detected: list[str] = field(default_factory=list)
    should_evolve: bool = False


@dataclass
class EvolutionResult:
    """进化层输出：进化操作"""
    phase: EvolutionPhase
    actions_taken: list[str] = field(default_factory=list)
    new_rules: list[dict] = field(default_factory=list)
    retired_rules: list[str] = field(default_factory=list)
    distilled: bool = False
    axiom_alignment: int = 0


@dataclass
class Rule:
    """单条可执行规则"""
    id: str
    priority: int
    condition: str
    action: str
    description: str
    trigger_count: int = 0
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "priority": self.priority,
            "condition": self.condition,
            "action": self.action,
            "description": self.description,
            "trigger_count": self.trigger_count,
            "enabled": self.enabled,
        }


# ── WAL 协议 ──

@dataclass
class WALEntry:
    """一条 WAL 条目"""
    type: SignalType
    data: dict[str, Any]
    timestamp: str = ""


# ── 心跳 ──

@dataclass
class HeartbeatTask:
    id: str
    name: str
    interval_minutes: int
    last_run: str = ""
    enabled: bool = True


# ── 共享工具函数 ──

def utc_now() -> str:
    """UTC 当前时间，格式 YYYY-MM-DDTHH:MM:SSZ"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_today() -> str:
    """UTC 当前日期，格式 YYYY-MM-DD"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
