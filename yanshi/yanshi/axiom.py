"""
砚识 — 信条对齐系统

从 minds/AXIOM.md 加载四大信条，在每次反思和进化时评估行为是否与信条对齐。

这不是另一套规则——规则说"怎么做"，信条说"为什么做"。
信条对齐分数渗透到：
  - 反思层：每次执行后评估对齐度，低于阈值触发纠正
  - 进化层：VFM 评分中注入"有用性增量"维度
  - 决策层：重大决策前对照信条自检
"""

from dataclasses import dataclass, field
from enum import Enum


# ── 信条维度 ──

class AxiomDimension(str, Enum):
    TRUTH = "求真"
    USEFULNESS = "有用"
    SELF_AWARENESS = "自知"
    IMPROVEMENT = "渐进"


# 权重配置（有用性权重最高）
DIMENSION_WEIGHTS = {
    AxiomDimension.TRUTH: 2,
    AxiomDimension.USEFULNESS: 3,
    AxiomDimension.SELF_AWARENESS: 2,
    AxiomDimension.IMPROVEMENT: 2,
}

# 对齐阈值
ALIGNMENT_EXCELLENT = 20  # 优秀对齐
ALIGNMENT_BASELINE = 12   # 基本对齐
ALIGNMENT_WARNING = 8     # 警告阈值


@dataclass
class AxiomScore:
    """单次行为的信条对齐评分"""
    truth: int = 0
    usefulness: int = 0
    self_awareness: int = 0
    improvement: int = 0

    def total(self) -> int:
        return (
            self.truth * DIMENSION_WEIGHTS[AxiomDimension.TRUTH] +
            self.usefulness * DIMENSION_WEIGHTS[AxiomDimension.USEFULNESS] +
            self.self_awareness * DIMENSION_WEIGHTS[AxiomDimension.SELF_AWARENESS] +
            self.improvement * DIMENSION_WEIGHTS[AxiomDimension.IMPROVEMENT]
        )

    def verdict(self) -> str:
        t = self.total()
        if t >= ALIGNMENT_EXCELLENT:
            return "优秀对齐"
        if t >= ALIGNMENT_BASELINE:
            return "基本对齐"
        return "偏离信条"

    def explanation(self) -> str:
        parts = []
        if self.truth < 2:
            parts.append("求真不足：输出缺少可验证依据")
        if self.usefulness < 2:
            parts.append("有用性低：对用户的价值增量不明确")
        if self.self_awareness < 2:
            parts.append("自知不足：缺少关键节点的自省审视")
        if self.improvement < 2:
            parts.append("渐进不足：未能产生可积累的经验")
        if not parts:
            parts.append("四项信条均达到标准")
        return " | ".join(parts)


@dataclass
class AxiomJournal:
    """信条日志：追踪长期对齐趋势"""
    scores: list[AxiomScore] = field(default_factory=list)
    total_cycles: int = 0
    warnings: int = 0   # 偏离信条的次数
    excellents: int = 0  # 优秀对齐次数

    def record(self, score: AxiomScore):
        self.scores.append(score)
        self.total_cycles += 1
        if score.total() < ALIGNMENT_BASELINE:
            self.warnings += 1
        if score.total() >= ALIGNMENT_EXCELLENT:
            self.excellents += 1

    def trend(self) -> dict:
        """对齐趋势分析"""
        if not self.scores:
            return {"status": "无数据"}
        recent = self.scores[-10:]
        avg = sum(s.total() for s in recent) / len(recent)
        return {
            "平均对齐分": round(avg, 1),
            "优秀率": f"{self.excellents}/{self.total_cycles}",
            "偏离率": f"{self.warnings}/{self.total_cycles}",
            "趋势": "上升" if len(recent) >= 3 and recent[-1].total() > avg else "稳定",
        }


# ── 信条评估器 ──

class AxiomEvaluator:
    """
    信条对齐评估器。

    在反思层被调用：根据执行结果评估这次行为是否符合四信条。
    评估结果影响：
      1. 是否需要触发纠正（偏离信条时）
      2. VFM 评分中的"有用性增量"维度
      3. 进化管道中规则的"信条对齐"元数据
    """

    def evaluate(self, user_input: str, action: str, result_success: bool,
                 confidence: float, has_reasoning: bool = False,
                 uses_memory: bool = False, error_repeated: bool = False,
                 user_feedback: str = "") -> AxiomScore:
        """
        评估单次行为。
        """

        # ── 求真 (Truth-First) ──
        truth = 1  # 默认：有基本推理
        if has_reasoning and confidence > 0.7:
            truth = 2  # 有推理链
        if uses_memory:
            truth = min(3, truth + 1)  # 基于历史记忆 → 有依据
        if confidence < 0.4:
            truth = 0  # 低置信度 → 接近臆造

        # ── 有用 (Usefulness) ──
        usefulness = 1  # 默认：间接相关
        useful_actions = {
            "respond_identity", "show_help", "show_system_status",
            "show_memory_status", "show_stats",
        }
        correction_actions = {"log_correction"}
        direct_help_actions = {"run_maintenance", "run_self_test"}

        if action in useful_actions:
            usefulness = 2  # 直接帮助
        elif action in correction_actions:
            usefulness = 2  # 纠正 → 改进未来
        elif action in direct_help_actions:
            usefulness = 2
        elif action == "block_external":
            usefulness = 2  # 安全拦截 → 防止损害

        # 用户反馈修正
        if "有用" in user_feedback or "很好" in user_feedback:
            usefulness = 3
        if "没用" in user_feedback or "废话" in user_feedback:
            usefulness = 0

        # ── 自知 (Self-Awareness) ──
        self_awareness = 1  # 默认：事后才察觉
        if has_reasoning and confidence > 0.6:
            self_awareness = 2  # 执行中自检
        if action in ("respond_identity", "show_help"):
            self_awareness = 2  # 知道自己的边界
        if action == "block_external":
            self_awareness = 3  # 执行前已审视风险

        # ── 渐进 (Continuous Improvement) ──
        improvement = 1  # 默认：有记录
        if uses_memory:
            improvement = 2  # 应用了历史教训
        if not error_repeated:
            improvement = min(3, improvement + 1)  # 没重复错误
        if action == "log_correction":
            improvement = 3  # 主动纠正 → 可复用的经验

        return AxiomScore(
            truth=truth,
            usefulness=usefulness,
            self_awareness=self_awareness,
            improvement=improvement,
        )

    def evaluate_from_context(self, user_input: str, action: str,
                               success: bool, matched_rules: list[str],
                               confidence: float, error_count: int = 0,
                               cycle_count: int = 0) -> AxiomScore:
        """从引擎上下文直接评估"""
        has_reasoning = len(matched_rules) > 0 or action != "echo"
        uses_memory = any(r in matched_rules for r in ["rule_004", "rule_005", "rule_010"])
        error_repeated = error_count >= 3

        return self.evaluate(
            user_input=user_input,
            action=action,
            result_success=success,
            confidence=confidence,
            has_reasoning=has_reasoning,
            uses_memory=uses_memory,
            error_repeated=error_repeated,
        )


# ── 信条注入：VFM 维度扩展 ──

def axiom_enhanced_vfm(axiom_score: AxiomScore) -> dict:
    """
    将信条对齐分注入 VFM 评估维度。
    有用性高 → high_frequency 和 burden_reduction 加分
    渐进性好 → failure_reduction 加分
    """
    boost = {}
    if axiom_score.usefulness >= 2:
        boost["high_frequency"] = 1
        boost["burden_reduction"] = 1
    if axiom_score.usefulness >= 3:
        boost["high_frequency"] = 2
    if axiom_score.improvement >= 2:
        boost["failure_reduction"] = 1
    if axiom_score.truth >= 2:
        boost["failure_reduction"] = min(2, boost.get("failure_reduction", 0) + 1)
    return boost
