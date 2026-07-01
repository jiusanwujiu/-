"""
砚识 v0.8 — 元认知反思引擎

元认知 = 对自身认知过程的认知。
不只是反思"我做对了吗"，而是反思"我是怎么思考的？我的决策模式有什么问题？"

五个维度:
  1. 决策模式分析 — 哪类决策最频繁？哪类总是被阻止？
  2. 置信度校准 — 高置信但失败？低置信却成功？
  3. 信条对齐趋势 — 对齐分在上升还是下降？
  4. 工具使用效率 — 哪些工具高频？哪些高失败率？
  5. 自我评估 — 基于以上分析，生成元认知判断
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict


@dataclass
class MetaSnapshot:
    """单次元认知快照"""
    cycle: int
    timestamp: str
    # 决策模式
    dominant_action: str = ""
    blocked_rate: float = 0.0
    action_diversity: int = 0
    # 置信度校准
    avg_confidence: float = 0.0
    confidence_failure_gap: float = 0.0
    calibration: str = ""
    # 信条趋势
    axiom_trend: str = ""
    axiom_avg: float = 0.0
    # 工具效率
    top_tool: str = ""
    worst_tool: str = ""
    tool_failure_rate: float = 0.0
    # 自我评估
    self_assessment: str = ""
    insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    # ── v0.8: 异常检测 + 预测校准 ──
    anomaly_detected: bool = False       # 是否检测到行为异常
    anomaly_detail: str = ""             # 异常详情
    predicted_failure_rate: float = 0.0  # 预测下一周期失败率
    confidence_adjustment: float = 0.0   # 建议置信度调整量 (±0.15)

    def to_dict(self) -> dict:
        return {
            "cycle": self.cycle,
            "dominant_action": self.dominant_action,
            "blocked_rate": round(self.blocked_rate, 2),
            "action_diversity": self.action_diversity,
            "avg_confidence": round(self.avg_confidence, 2),
            "calibration": self.calibration,
            "confidence_gap": round(self.confidence_failure_gap, 2),
            "axiom_trend": self.axiom_trend,
            "axiom_avg": round(self.axiom_avg, 1),
            "top_tool": self.top_tool,
            "worst_tool": self.worst_tool,
            "tool_failure_rate": round(self.tool_failure_rate, 2),
            "self_assessment": self.self_assessment,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "anomaly": {
                "detected": self.anomaly_detected,
                "detail": self.anomaly_detail,
            },
            "predicted_failure_rate": round(self.predicted_failure_rate, 2),
            "confidence_adjustment": round(self.confidence_adjustment, 2),
        }


class MetacognitionEngine:
    """
    元认知反思引擎 — 分析引擎的决策历史，生成元认知判断。

    用法:
        meta = MetacognitionEngine()
        # 每轮调用 record
        meta.record(cycle=5, action="tool_exec", confidence=0.9,
                    success=True, axiom_score=18, tool="file_read")
        # 每 N 轮生成快照
        snapshot = meta.reflect(cycle=5, axiom_history=[18, 16, 20, 19, 18])
    """

    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self._records: list[dict] = []
        self._snapshots: list[MetaSnapshot] = []

        # 实时累计统计
        self._action_counts: dict[str, int] = defaultdict(int)
        self._action_blocked: dict[str, int] = defaultdict(int)
        self._tool_counts: dict[str, int] = defaultdict(int)
        self._tool_failures: dict[str, int] = defaultdict(int)
        self._confidence_success: list[tuple[float, bool]] = []
        self._axiom_scores: list[int] = []

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    def record(
        self,
        cycle: int,
        action: str,
        confidence: float,
        success: bool,
        axiom_score: int = 0,
        tool: str = "",
        approved: bool = True,
    ):
        """记录一轮循环的元数据"""
        entry = {
            "cycle": cycle,
            "action": action,
            "confidence": confidence,
            "success": success,
            "axiom": axiom_score,
            "tool": tool,
            "approved": approved,
            "ts": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        }
        self._records.append(entry)
        if len(self._records) > self.history_size:
            self._records.pop(0)

        # 更新累计统计
        self._action_counts[action] += 1
        if not approved:
            self._action_blocked[action] += 1
        if tool:
            self._tool_counts[tool] += 1
            if not success:
                self._tool_failures[tool] += 1
        self._confidence_success.append((confidence, success))
        if len(self._confidence_success) > self.history_size:
            self._confidence_success.pop(0)
        if axiom_score > 0:
            self._axiom_scores.append(axiom_score)
            if len(self._axiom_scores) > self.history_size:
                self._axiom_scores.pop(0)

    def reflect(
        self,
        cycle: int,
        axiom_history: list[int] = None,
    ) -> MetaSnapshot:
        """
        生成元认知快照 — 对自身决策模式的反思。
        建议每 5-10 轮调用一次。
        """
        snap = MetaSnapshot(
            cycle=cycle,
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        )

        if not self._records:
            snap.self_assessment = "无足够数据"
            return snap

        # ── 1. 决策模式分析 ──
        snap.dominant_action = max(self._action_counts, key=self._action_counts.get, default="")
        total_actions = sum(self._action_counts.values())
        total_blocked = sum(self._action_blocked.values())
        snap.blocked_rate = total_blocked / total_actions if total_actions > 0 else 0
        snap.action_diversity = len(self._action_counts)

        # ── 2. 置信度校准 ──
        if self._confidence_success:
            avg_conf = sum(c for c, _ in self._confidence_success) / len(self._confidence_success)
            snap.avg_confidence = avg_conf

            # 成功 vs 失败的置信度差
            success_confs = [c for c, s in self._confidence_success if s]
            failure_confs = [c for c, s in self._confidence_success if not s]

            if success_confs and failure_confs:
                avg_success_conf = sum(success_confs) / len(success_confs)
                avg_failure_conf = sum(failure_confs) / len(failure_confs)
                snap.confidence_failure_gap = avg_failure_conf - avg_success_conf

                success_rate = len(success_confs) / (len(success_confs) + len(failure_confs))

                if snap.confidence_failure_gap > 0.15:
                    # 失败时置信度高于成功时 → 过度自信
                    snap.calibration = "overconfident"
                elif avg_success_conf < 0.5 and success_rate > 0.6:
                    # 成功率高但成功时置信度低 → 不够自信
                    snap.calibration = "underconfident"
                else:
                    # 成功时置信度 >= 失败时 → 校准良好
                    snap.calibration = "well-calibrated"
            elif success_confs and not failure_confs:
                snap.calibration = "well-calibrated" if avg_conf < 0.9 else "potentially-overconfident"
            else:
                snap.calibration = "insufficient-data"

        # ── 3. 信条对齐趋势 ──
        scores = axiom_history or self._axiom_scores
        if len(scores) >= 3:
            snap.axiom_avg = sum(scores) / len(scores)
            recent = scores[-3:]
            older = scores[:-3][-3:] if len(scores) > 3 else scores[:1]

            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older) if older else recent_avg

            if recent_avg > older_avg + 1:
                snap.axiom_trend = "improving"
            elif recent_avg < older_avg - 1:
                snap.axiom_trend = "declining"
            else:
                snap.axiom_trend = "stable"
        elif scores:
            snap.axiom_avg = sum(scores) / len(scores)
            snap.axiom_trend = "insufficient-data"

        # ── 4. 工具使用效率 ──
        if self._tool_counts:
            snap.top_tool = max(self._tool_counts, key=self._tool_counts.get, default="")
            # 找失败率最高的工具
            worst_rate = 0
            for tool, count in self._tool_counts.items():
                if count >= 2:  # 至少用过2次
                    rate = self._tool_failures.get(tool, 0) / count
                    if rate > worst_rate:
                        worst_rate = rate
                        snap.worst_tool = tool
            total_tool_calls = sum(self._tool_counts.values())
            total_tool_failures = sum(self._tool_failures.values())
            snap.tool_failure_rate = total_tool_failures / total_tool_calls if total_tool_calls > 0 else 0

        # ── 5. 异常检测 (v0.8) ──
        snap.anomaly_detected, snap.anomaly_detail = self._detect_anomalies(snap)

        # ── 6. 预测校准 (v0.8) ──
        snap.predicted_failure_rate = self._predict_failure_rate()
        snap.confidence_adjustment = self._compute_confidence_adjustment(snap)

        # ── 7. 自我评估 + 洞察 ──
        snap.insights = self._generate_insights(snap)
        snap.recommendations = self._generate_recommendations(snap)
        snap.self_assessment = self._generate_self_assessment(snap)

        self._snapshots.append(snap)
        if len(self._snapshots) > 50:
            self._snapshots.pop(0)

        return snap

    def latest_snapshot(self) -> Optional[MetaSnapshot]:
        """获取最近的元认知快照"""
        return self._snapshots[-1] if self._snapshots else None

    def trend(self) -> dict:
        """元认知趋势（跨快照）"""
        if len(self._snapshots) < 2:
            return {"status": "insufficient-data"}

        recent = self._snapshots[-1]
        older = self._snapshots[-2]

        return {
            "calibration_change": f"{older.calibration} → {recent.calibration}",
            "axiom_trend": recent.axiom_trend,
            "blocked_rate_change": round(recent.blocked_rate - older.blocked_rate, 2),
            "confidence_change": round(recent.avg_confidence - older.avg_confidence, 2),
            "snapshots": len(self._snapshots),
        }

    def report_text(self) -> str:
        """生成文本报告"""
        snap = self.latest_snapshot()
        if not snap:
            return "无元认知数据"

        lines = [
            "┌─────────────────────────────────────┐",
            "│  砚 识 · 元 认 知 反 思             │",
            "├─────────────────────────────────────┤",
            f"│  周期: #{snap.cycle}                        │",
            f"│  主导动作: {snap.dominant_action:<24}│",
            f"│  动作多样性: {snap.action_diversity} 种{'':18}│",
            f"│  阻止率: {snap.blocked_rate:.0%}{'':24}│",
            f"│  平均置信: {snap.avg_confidence:.2f}{'':22}│",
            f"│  校准状态: {snap.calibration:<24}│",
            f"│  信条趋势: {snap.axiom_trend} (均{snap.axiom_avg:.0f}){'':14}│",
            f"│  最高频工具: {snap.top_tool:<22}│",
            f"│  工具失败率: {snap.tool_failure_rate:.0%}{'':22}│",
            "├─────────────────────────────────────┤",
            "│  自我评估:                          │",
        ]

        # 自我评估换行
        assessment = snap.self_assessment
        while assessment:
            lines.append(f"│  {assessment[:35]:<35}│")
            assessment = assessment[35:]

        if snap.insights:
            lines.append("├─────────────────────────────────────┤")
            lines.append("│  洞察:                              │")
            for ins in snap.insights[:3]:
                lines.append(f"│  • {ins[:33]:<33}│")

        if snap.recommendations:
            lines.append("├─────────────────────────────────────┤")
            lines.append("│  建议:                              │")
            for rec in snap.recommendations[:3]:
                lines.append(f"│  → {rec[:33]:<33}│")

        lines.append("└─────────────────────────────────────┘")
        return "\n".join(lines)

    # ── v0.8: 异常检测 + 预测校准 ──

    def _detect_anomalies(self, snap: MetaSnapshot) -> tuple[bool, str]:
        """检测行为异常 — 与基线偏离超过阈值"""
        if len(self._snapshots) < 2:
            return False, ""

        # 计算基线（历史快照的移动平均）
        baselines = self._compute_baselines()

        anomalies = []

        # 1. 失败率突变
        base_fail = baselines.get("avg_failure_rate", 0)
        if base_fail > 0 and snap.tool_failure_rate > base_fail * 2:
            anomalies.append(f"工具失败率突增: {snap.tool_failure_rate:.0%} (基线 {base_fail:.0%})")

        # 2. 阻止率突变
        base_blocked = baselines.get("avg_blocked_rate", 0)
        if base_blocked > 0 and snap.blocked_rate > base_blocked * 2:
            anomalies.append(f"阻止率突增: {snap.blocked_rate:.0%} (基线 {base_blocked:.0%})")

        # 3. 置信度突变
        base_conf = baselines.get("avg_confidence", 0)
        if base_conf > 0 and abs(snap.avg_confidence - base_conf) > 0.2:
            direction = "升高" if snap.avg_confidence > base_conf else "降低"
            anomalies.append(f"平均置信度{direction}: {snap.avg_confidence:.2f} (基线 {base_conf:.2f})")

        # 4. 信条分突降
        base_axiom = baselines.get("avg_axiom", 0)
        if base_axiom > 0 and snap.axiom_avg < base_axiom - 3:
            anomalies.append(f"信条分突降: {snap.axiom_avg:.1f} (基线 {base_axiom:.1f})")

        if anomalies:
            return True, " | ".join(anomalies)
        return False, ""

    def _compute_baselines(self) -> dict:
        """计算历史基线（最近 10 个快照的加权平均）"""
        if not self._snapshots:
            return {}

        snaps = self._snapshots[-10:]
        n = len(snaps)

        # 越近的权重越大 (linear decay 1.0 → 0.1)
        weights = [(i + 1) / n for i in range(n)]
        total_w = sum(weights)

        avg_fail = sum(s.tool_failure_rate * w for s, w in zip(snaps, weights)) / total_w if total_w > 0 else 0
        avg_blocked = sum(s.blocked_rate * w for s, w in zip(snaps, weights)) / total_w if total_w > 0 else 0
        avg_conf = sum(s.avg_confidence * w for s, w in zip(snaps, weights)) / total_w if total_w > 0 else 0
        avg_axiom = sum(s.axiom_avg * w for s, w in zip(snaps, weights)) / total_w if total_w > 0 else 0

        return {
            "avg_failure_rate": avg_fail,
            "avg_blocked_rate": avg_blocked,
            "avg_confidence": avg_conf,
            "avg_axiom": avg_axiom,
        }

    def _predict_failure_rate(self) -> float:
        """预测下一周期的失败率（基于最近趋势的线性外推）"""
        if len(self._snapshots) < 3:
            return 0.0

        recent = self._snapshots[-5:]
        rates = [s.tool_failure_rate for s in recent]

        # 简单线性回归：y = ax + b
        n = len(rates)
        x_mean = (n - 1) / 2
        y_mean = sum(rates) / n

        numerator = sum((i - x_mean) * (r - y_mean) for i, r in enumerate(rates))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return y_mean

        slope = numerator / denominator
        # 预测下一周期（x = n）
        predicted = slope * n + (y_mean - slope * x_mean)

        return max(0.0, min(1.0, predicted))

    def _compute_confidence_adjustment(self, snap: MetaSnapshot) -> float:
        """计算建议的置信度调整量（±0.15 范围内）"""
        adjustment = 0.0

        # 过度自信 → 降低置信度
        if "overconfident" in snap.calibration:
            adjustment = -0.08 - snap.confidence_failure_gap * 0.1
        elif snap.calibration == "underconfident":
            adjustment = 0.05

        # 信条下降 → 谨慎降低
        if snap.axiom_trend == "declining":
            adjustment -= 0.05

        # 异常检测到 → 降低
        if snap.anomaly_detected:
            adjustment -= 0.05

        # 限制范围
        return max(-0.15, min(0.15, adjustment))

    # ── 内部: 洞察/建议/自评生成 ──

    @staticmethod
    def _generate_insights(snap: MetaSnapshot) -> list[str]:
        insights = []

        # 置信度校准洞察
        if snap.calibration == "overconfident":
            insights.append(f"过度自信: 失败时置信度({snap.avg_confidence + snap.confidence_failure_gap:.2f})高于成功时({snap.avg_confidence:.2f})，需要降低高置信操作的信心")
        elif snap.calibration == "underconfident":
            insights.append(f"不够自信: 成功的操作置信度偏低，某些操作可以更果断")

        # 阻止率洞察
        if snap.blocked_rate > 0.3:
            insights.append(f"阻止率过高({snap.blocked_rate:.0%})，可能存在过度保守的规则")

        # 信条趋势洞察
        if snap.axiom_trend == "declining":
            insights.append("信条对齐分下降，近期行为偏离核心价值观")
        elif snap.axiom_trend == "improving":
            insights.append("信条对齐持续改善，行为与价值观趋于一致")

        # 工具失败率洞察
        if snap.tool_failure_rate > 0.3:
            insights.append(f"工具失败率高({snap.tool_failure_rate:.0%})，特别是 {snap.worst_tool}")
        elif snap.worst_tool and snap.tool_failure_rate > 0:
            insights.append(f"{snap.worst_tool} 存在失败记录，需关注参数提取质量")

        # 动作多样性洞察
        if snap.action_diversity <= 2:
            insights.append(f"动作多样性低({snap.action_diversity})，行为模式单一")

        return insights

    @staticmethod
    def _generate_recommendations(snap: MetaSnapshot) -> list[str]:
        recs = []

        if snap.calibration == "overconfident":
            recs.append("对 EXTERNAL 权限工具降低默认置信度 0.1")
        elif snap.calibration == "underconfident":
            recs.append("对 READ 权限工具提高默认置信度 0.05")

        if snap.blocked_rate > 0.3:
            recs.append("审查 rule_006 安全规则，是否过于严格")

        if snap.axiom_trend == "declining":
            recs.append("触发进化管道评估，检查是否有规则退化")

        if snap.tool_failure_rate > 0.3:
            recs.append(f"检查 {snap.worst_tool} 的参数提取逻辑")

        if snap.action_diversity <= 2:
            recs.append("扩展意图路由关键词覆盖，增加行为多样性")

        if not recs:
            recs.append("当前状态良好，无需调整")

        return recs

    @staticmethod
    def _generate_self_assessment(snap: MetaSnapshot) -> str:
        """生成自我评估文本"""
        parts = []

        # 整体状态
        if snap.calibration == "well-calibrated" and snap.axiom_trend in ("improving", "stable"):
            parts.append("决策质量良好，置信度校准准确，信条对齐稳定。")
        elif snap.calibration == "overconfident":
            parts.append("存在过度自信倾向，需要更谨慎地评估操作可行性。")
        elif snap.calibration == "underconfident":
            parts.append("置信度偏低，部分安全操作可以更果断执行。")

        # 信条状态
        if snap.axiom_trend == "improving":
            parts.append("信条对齐持续改善。")
        elif snap.axiom_trend == "declining":
            parts.append("信条对齐下降，需要关注行为偏差。")

        # 效率
        if snap.tool_failure_rate > 0.2:
            parts.append(f"工具执行效率有问题（失败率{snap.tool_failure_rate:.0%}）。")
        elif snap.tool_failure_rate < 0.1 and snap.top_tool:
            parts.append("工具执行效率良好。")

        return " ".join(parts) if parts else "数据不足，无法评估。"
