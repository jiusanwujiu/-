"""
砚识 — 指标采集系统

追踪引擎运行指标：
  - 循环指标: 总次数、平均耗时、峰值耗时
  - 分层指标: 每层耗时分布
  - 信条指标: 对齐分趋势、偏离率
  - 工具指标: 调用次数、成功率、平均延迟
  - 系统指标: 内存使用、运行时长
"""

import time
from datetime import datetime, timezone
from typing import Optional


class MetricsCollector:
    """
    指标采集器。

    用法:
      metrics = MetricsCollector()
      metrics.record_cycle(duration_ms=150, layers={...})
      metrics.record_tool(tool_name="file_read", success=True, duration_ms=10)
      metrics.record_axiom(score=18)
    """

    def __init__(self):
        self.start_time = time.time()

        # 循环指标
        self.cycles_total: int = 0
        self.cycles_durations: list[float] = []
        self.cycles_by_action: dict[str, int] = {}

        # 分层耗时
        self.layer_durations: dict[str, list[float]] = {
            "perceive": [], "understand": [], "decide": [],
            "execute": [], "reflect": [], "evolve": [],
        }

        # 信条指标
        self.axiom_scores: list[int] = []
        self.axiom_deviations: int = 0

        # 工具指标
        self.tool_calls: dict[str, dict] = {}  # {name: {total, success, fail, durations}}

        # 规则触发
        self.rule_triggers: dict[str, int] = {}

        # 决策统计
        self.decisions_blocked: int = 0
        self.decisions_approved: int = 0

    def record_cycle(self, action: str, duration_ms: float,
                     layers: Optional[dict] = None, approved: bool = True):
        """记录一次循环"""
        self.cycles_total += 1
        self.cycles_durations.append(duration_ms)
        self.cycles_by_action[action] = self.cycles_by_action.get(action, 0) + 1

        if approved:
            self.decisions_approved += 1
        else:
            self.decisions_blocked += 1

        if layers:
            for layer_name, layer_ms in layers.items():
                if layer_name in self.layer_durations:
                    self.layer_durations[layer_name].append(layer_ms)

    def record_tool(self, tool_name: str, success: bool, duration_ms: float):
        """记录一次工具调用"""
        if tool_name not in self.tool_calls:
            self.tool_calls[tool_name] = {"total": 0, "success": 0, "fail": 0, "durations": []}

        stats = self.tool_calls[tool_name]
        stats["total"] += 1
        stats["success" if success else "fail"] += 1
        stats["durations"].append(duration_ms)

    def record_axiom(self, score: int):
        """记录信条对齐评分"""
        self.axiom_scores.append(score)
        if score < 12:
            self.axiom_deviations += 1

    def record_rule(self, rule_id: str):
        """记录规则触发"""
        self.rule_triggers[rule_id] = self.rule_triggers.get(rule_id, 0) + 1

    def snapshot(self) -> dict:
        """生成当前指标快照"""
        uptime = time.time() - self.start_time

        # 周期统计
        avg_cycle = sum(self.cycles_durations) / len(self.cycles_durations) if self.cycles_durations else 0
        peak_cycle = max(self.cycles_durations) if self.cycles_durations else 0

        # 信条统计
        avg_axiom = sum(self.axiom_scores) / len(self.axiom_scores) if self.axiom_scores else 0
        deviation_rate = self.axiom_deviations / len(self.axiom_scores) if self.axiom_scores else 0

        # 工具统计
        tool_stats = {}
        for name, stats in self.tool_calls.items():
            durations = stats["durations"]
            tool_stats[name] = {
                "total": stats["total"],
                "success": stats["success"],
                "fail": stats["fail"],
                "success_rate": round(stats["success"] / stats["total"] * 100, 1) if stats["total"] else 0,
                "avg_ms": round(sum(durations) / len(durations), 1) if durations else 0,
            }

        # 分层统计
        layer_stats = {}
        for name, durations in self.layer_durations.items():
            if durations:
                layer_stats[name] = {
                    "avg_ms": round(sum(durations) / len(durations), 1),
                    "max_ms": round(max(durations), 1),
                    "count": len(durations),
                }

        return {
            "uptime_seconds": round(uptime, 1),
            "cycles": {
                "total": self.cycles_total,
                "avg_ms": round(avg_cycle, 1),
                "peak_ms": round(peak_cycle, 1),
                "by_action": self.cycles_by_action,
                "approved": self.decisions_approved,
                "blocked": self.decisions_blocked,
            },
            "axiom": {
                "avg_score": round(avg_axiom, 1),
                "deviations": self.axiom_deviations,
                "deviation_rate": round(deviation_rate * 100, 1),
                "total_evaluations": len(self.axiom_scores),
            },
            "tools": tool_stats,
            "layers": layer_stats,
            "rules": self.rule_triggers,
        }

    def report_text(self) -> str:
        """生成文本格式的运行报告"""
        snap = self.snapshot()
        lines = [
            "┌─────────────────────────────────┐",
            "│  砚 识 · 运 行 指 标            │",
            "├─────────────────────────────────┤",
            f"│  运行时长: {snap['uptime_seconds']:.0f}s{' ' * (18 - len(f'{snap["uptime_seconds"]:.0f}s'))}│",
            f"│  循环次数: {snap['cycles']['total']} (均{snap['cycles']['avg_ms']:.0f}ms, 峰值{snap['cycles']['peak_ms']:.0f}ms){' ' * (6)}│",
            f"│  批准/阻止: {snap['cycles']['approved']}/{snap['cycles']['blocked']}{' ' * (18 - len(f'{snap['cycles']['approved']}/{snap['cycles']['blocked']}'))}│",
            f"│  信条均分: {snap['axiom']['avg_score']}/20 (偏离率{snap['axiom']['deviation_rate']}%){' ' * (8)}│",
            f"│  工具调用: {sum(t['total'] for t in snap['tools'].values())} 次{' ' * (18)}│",
            "└─────────────────────────────────┘",
        ]
        return "\n".join(lines)
