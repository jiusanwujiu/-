"""
砚识 — 进化协议

ADL (Anti-Drift Lock): 防漂移锁定，防止四种退化倾向
VFM (Value-First Modification): 价值优先修改，≥8分门槛

双协议驱动四阶段进化管道:
  Phase1 信号检测 → Phase2 积累验证 → Phase3 规则提升 → Phase4 淘汰维护
"""

from dataclasses import dataclass, field

from .models import ADLViolation, EvolutionPhase, EvolutionResult, Rule


# ────────────────────────────────
# ADL — 防漂移审查器
# ────────────────────────────────

@dataclass
class ADLReview:
    """ADL 审查结果"""
    violations: list[ADLViolation] = field(default_factory=list)
    passed: bool = True
    explanation: str = ""


class ADLReviewer:
    """
    审查变更是否违反四条禁令：
    1. 禁止为复杂而复杂 — 功能必须有明确需求驱动
    2. 禁止抽象成瘾 — 新增抽象层必须消除≥2处重复
    3. 禁止新颖崇拜 — 新技术引入必须有可量化优势
    4. 禁止自我膨胀 — 代码/模块增长需有功能对应
    """

    def review(self, change: dict) -> ADLReview:
        result = ADLReview()

        # 检查1: 为复杂而复杂
        if change.get("complexity_added", 0) > 0 and not change.get("requirement_driven", False):
            result.violations.append(ADLViolation.COMPLEXITY)

        # 检查2: 抽象成瘾
        if change.get("new_abstractions", 0) > 0 and change.get("duplicates_eliminated", 0) < 2:
            result.violations.append(ADLViolation.ABSTRACTION)

        # 检查3: 新颖崇拜
        if change.get("new_tech_introduced", False) and not change.get("quantified_advantage", ""):
            result.violations.append(ADLViolation.NOVELTY)

        # 检查4: 自我膨胀
        growth_ratio = change.get("size_after", 1) / max(change.get("size_before", 1), 1)
        if growth_ratio > 1.5 and change.get("functionality_growth", 0) < growth_ratio * 0.5:
            result.violations.append(ADLViolation.INFLATION)

        result.passed = len(result.violations) == 0
        if not result.passed:
            names = [v.value for v in result.violations]
            result.explanation = f"ADL 审查未通过：{', '.join(names)}"
        else:
            result.explanation = "ADL 审查通过"

        return result


# ────────────────────────────────
# VFM — 价值优先评分器
# ────────────────────────────────

class VFMScorer:
    """
    Value-First Modification 评分器
    Score = 高频×3 + 降败×3 + 减负×2 + 省本×2
    阈值: ≥ 8 分 → 允许修改
    """

    THRESHOLD = 8

    def score(self, change: dict) -> int:
        hf = change.get("high_frequency", 0) * 3  # 0-2 scale: 0=rare, 1=occasional, 2=frequent
        fr = change.get("failure_reduction", 0) * 3
        br = change.get("burden_reduction", 0) * 2
        cs = change.get("cost_saving", 0) * 2
        return hf + fr + br + cs

    def evaluate(self, change: dict) -> bool:
        return self.score(change) >= self.THRESHOLD

    def breakdown(self, change: dict) -> str:
        hf = change.get("high_frequency", 0) * 3
        fr = change.get("failure_reduction", 0) * 3
        br = change.get("burden_reduction", 0) * 2
        cs = change.get("cost_saving", 0) * 2
        total = hf + fr + br + cs
        lines = [
            f"  高频使用: {hf}/6",
            f"  降低失败: {fr}/6",
            f"  降低负担: {br}/4",
            f"  节省成本: {cs}/4",
            f"  总分: {total}/20 (阈值: {self.THRESHOLD})",
            f"  结果: {'✅ 通过' if total >= self.THRESHOLD else '❌ 不通过'}",
        ]
        return "\n".join(lines)


# ────────────────────────────────
# CORRECTIONS.md 读写
# ────────────────────────────────

class CorrectionsLog:
    """用户纠正日志的读写和模式提取"""

    def __init__(self, workspace_root: str):
        from pathlib import Path
        self.file = Path(workspace_root) / "minds" / "CORRECTIONS.md"
        self._ensure_file()

    def _ensure_file(self):
        if not self.file.parent.exists():
            self.file.parent.mkdir(parents=True)
        if not self.file.exists():
            self.file.write_text(
                "# CORRECTIONS.md — 纠正与学习日志\n\n"
                "> 同一模式出现 ≥3 次 → 自动触发规则提升评估\n\n",
                encoding="utf-8",
            )

    def log(self, correction: str, context: str = ""):
        """追加一条纠正记录"""
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ctx_suffix = f" | 上下文: {context}" if context else ""
        entry = f"| {ts} | {correction}{ctx_suffix} |\n"
        with open(self.file, "a", encoding="utf-8") as f:
            f.write(entry)

    def count_entries(self) -> int:
        """返回纠正日志条目数量"""
        if not self.file.exists():
            return 0
        content = self.file.read_text(encoding="utf-8")
        return len([l for l in content.splitlines() if l.startswith("| ")])

    def extract_patterns(self) -> list[dict]:
        """
        从纠正日志中提取重复模式。

        返回: [{"pattern": "用户多次纠正文件操作", "count": 5, "examples": [...]}, ...]
        """
        if not self.file.exists():
            return []

        content = self.file.read_text(encoding="utf-8")
        entries = [l for l in content.splitlines() if l.startswith("| ")]

        if len(entries) < 3:
            return []

        # 简单关键词聚类
        clusters = self._cluster_by_keywords(entries)

        # 补充: n-gram 语义聚类（提取共现词对）
        semantic = self._cluster_by_ngrams(entries)
        # 合并两种聚类结果
        for key, val in semantic.items():
            if key not in clusters:
                clusters[key] = val
            else:
                clusters[key]["count"] += val["count"]
                clusters[key]["examples"].extend(val["examples"])

        return [v for v in clusters.values() if v["count"] >= 3]

    def _cluster_by_keywords(self, entries: list[str]) -> dict[str, dict]:
        """关键词聚类"""
        clusters: dict[str, dict] = {}
        keywords_map = {
            "文件操作": ["文件", "file", "删除", "读取", "保存", "写入"],
            "格式问题": ["格式", "format", "排版", "缩进", "空格"],
            "逻辑错误": ["逻辑", "原因", "为什么", "不应该"],
            "工具调用": ["工具", "tool", "命令", "command", "执行"],
            "回复风格": ["回复", "风格", "语气", "太长", "太短", "详细"],
            "记忆问题": ["记忆", "记住", "忘了", "memory", "之前"],
            "Agent通信": ["agent", "委托", "广播", "通信", "维度"],
            "元认知": ["元认知", "校准", "反思", "metacog", "异常"],
        }

        for entry in entries:
            entry_lower = entry.lower()
            for category, kws in keywords_map.items():
                if any(kw in entry_lower for kw in kws):
                    if category not in clusters:
                        clusters[category] = {"pattern": category, "count": 0, "examples": []}
                    clusters[category]["count"] += 1
                    if len(clusters[category]["examples"]) < 3:
                        clusters[category]["examples"].append(entry[:100])
        return clusters

    def _cluster_by_ngrams(self, entries: list[str]) -> dict[str, dict]:
        """双词共现聚类 — 提取语义上相关的模式"""
        import re
        clusters: dict[str, dict] = {}
        for entry in entries:
            words = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', entry)
            # 生成双词对
            for i in range(len(words) - 1):
                bigram = f"{words[i]}+{words[i + 1]}"
                if bigram not in clusters:
                    clusters[bigram] = {"pattern": bigram, "count": 0, "examples": []}
                clusters[bigram]["count"] += 1
                if len(clusters[bigram]["examples"]) < 3:
                    clusters[bigram]["examples"].append(entry[:100])
        return clusters

        return [v for v in clusters.values() if v["count"] >= 3]


# ────────────────────────────────
# 四阶段进化管道（数据驱动版）
# ────────────────────────────────

class EvolutionPipeline:
    """
    数据驱动的四阶段进化管道。

    Phase1: 从 CORRECTIONS.md 提取模式信号
    Phase2: 交叉验证 — 模式在每日日志中的频率 + 规则实际触发次数
    Phase3: 基于真实数据做 ADL+VFM 评估，通过后生成新规则
    Phase4: 淘汰 trigger_count < 阈值的低价值规则 + MEMORY.md 蒸馏
    """

    # Phase4: 淘汰阈值 — 触发次数低于此值的规则标记为低价值
    RETIRE_THRESHOLD = 2  # 原型阶段设低门槛

    def __init__(self, adl: ADLReviewer, vfm: VFMScorer, rules_engine, workspace_root: str = ""):
        self.adl = adl
        self.vfm = vfm
        self.rules = rules_engine
        self.phase = EvolutionPhase.SIGNAL
        self.corrections = CorrectionsLog(workspace_root) if workspace_root else None

        # 进化状态
        self.candidates: list[dict] = []
        self.verified: list[dict] = []
        self.evolution_history: list[str] = []

    def run_cycle(self, memory_sys=None, axiom_score=None) -> EvolutionResult:
        """
        运行一次进化周期。
        memory_sys: MemorySystem 实例，用于读取日志数据做交叉验证。
        axiom_score: AxiomScore 实例，信条对齐分注入 VFM 评估。
        """
        result = EvolutionResult(phase=self.phase)

        # 信条注入：将 axiom_score 融合到候选信号中
        if axiom_score:
            result.axiom_alignment = axiom_score.total()
            # 信条偏离时，提高进化紧迫性
            if axiom_score.total() < 12:
                self.candidates.append({
                    "source": "axiom::低信条对齐",
                    "count": 1,
                    "axiom_total": axiom_score.total(),
                    "axiom_explanation": axiom_score.explanation(),
                    "type": "axiom_drift",
                })

        if self.phase == EvolutionPhase.SIGNAL:
            result = self._phase1_signal(result, memory_sys)

        elif self.phase == EvolutionPhase.VERIFY:
            result = self._phase2_verify(result, memory_sys)

        elif self.phase == EvolutionPhase.PROMOTE:
            result = self._phase3_promote(result)

        elif self.phase == EvolutionPhase.RETIRE:
            result = self._phase4_retire(result, memory_sys)

        if result.actions_taken:
            self.evolution_history.extend(result.actions_taken)

        return result

    # ── Phase1: 信号检测 ──

    def _phase1_signal(self, result: EvolutionResult, memory_sys) -> EvolutionResult:
        """从 CORRECTIONS.md + 规则触发数据中提取候选进化信号"""
        signals = []

        # 数据源1: CORRECTIONS.md 模式提取
        if self.corrections:
            patterns = self.corrections.extract_patterns()
            for p in patterns:
                signals.append({
                    "source": f"corrections::{p['pattern']}",
                    "count": p["count"],
                    "examples": p.get("examples", []),
                    "type": "pattern_from_corrections",
                })

        # 数据源2: 高频触发规则（trigger_count 高的问题域）
        for rule in self.rules.all_rules():
            if rule.trigger_count >= 5:
                signals.append({
                    "source": f"high_trigger::{rule.id}",
                    "count": rule.trigger_count,
                    "rule_id": rule.id,
                    "rule_desc": rule.description,
                    "type": "high_frequency_rule",
                })

        # 数据源3: 每日日志规模（数据积累指标）
        if memory_sys:
            log_size = memory_sys.log_size_today()
            if log_size > 50:
                signals.append({
                    "source": "log_accumulation",
                    "count": log_size,
                    "type": "data_ready",
                })

        if not signals:
            result.actions_taken.append("Phase1: 无足够进化信号")
            return result

        self.candidates = signals
        result.actions_taken.append(
            f"Phase1 信号检测: 发现 {len(signals)} 个候选信号 "
            + ", ".join(s["source"] for s in signals)
        )
        self.phase = EvolutionPhase.VERIFY
        return result

    # ── Phase2: 交叉验证 ──

    def _phase2_verify(self, result: EvolutionResult, memory_sys) -> EvolutionResult:
        """验证候选信号的可靠性"""

        if not self.candidates:
            self.phase = EvolutionPhase.SIGNAL
            result.actions_taken.append("Phase2: 无候选，回到Phase1")
            return result

        verified = []
        for c in self.candidates:
            score = 0
            reasons = []

            # 验证维度1: 信号来源可靠性
            if c["type"] == "pattern_from_corrections":
                score += 3
                reasons.append("来自用户纠正(高可靠)")
            elif c["type"] == "high_frequency_rule":
                score += 2
                reasons.append("来自高频规则触发")
            elif c["type"] == "data_ready":
                score += 1
                reasons.append("数据积累指标")

            # 验证维度2: 频次充足性
            if c["count"] >= 5:
                score += 2
                reasons.append(f"高频({c['count']}次)")
            elif c["count"] >= 3:
                score += 1
                reasons.append(f"中频({c['count']}次)")
            else:
                reasons.append(f"频次不足({c['count']}次)")

            # 验证维度3: 日志交叉验证
            if memory_sys:
                log_lines = memory_sys.log_size_today()
                if log_lines > 30:
                    score += 1
                    reasons.append(f"日志充足({log_lines}行)")

            c["verification_score"] = score
            c["verification_reasons"] = reasons

            if score >= 3:  # 验证门槛
                verified.append(c)
                result.actions_taken.append(
                    f"Phase2 验证通过: {c['source']} (得分={score}) — {', '.join(reasons)}"
                )
            else:
                result.actions_taken.append(
                    f"Phase2 验证未通过: {c['source']} (得分={score}) — 不足"
                )

        self.verified = verified
        self.candidates.clear()

        if self.verified:
            self.phase = EvolutionPhase.PROMOTE
        else:
            result.actions_taken.append("Phase2: 无信号通过验证，回到Phase1")
            self.phase = EvolutionPhase.SIGNAL

        return result

    # ── Phase3: 规则提升 ──

    def _phase3_promote(self, result: EvolutionResult) -> EvolutionResult:
        """ADL + VFM 评估，通过后生成新规则"""

        if not self.verified:
            self.phase = EvolutionPhase.SIGNAL
            return result

        promoted = 0
        for v in self.verified:
            # 基于真实数据计算 VFM 维度
            count = v.get("count", 1)
            verif_score = v.get("verification_score", 0)

            change = {
                "high_frequency": min(2, count // 3),      # 每3次触发=1分
                "failure_reduction": min(2, verif_score // 2),  # 验证得分/2
                "burden_reduction": 1 if v["type"] == "pattern_from_corrections" else 0,
                "cost_saving": 1 if count >= 5 else 0,
                "complexity_added": 0 if v["type"] == "high_frequency_rule" else 1,
                "requirement_driven": v["type"] in ("pattern_from_corrections", "high_frequency_rule"),
                "new_abstractions": 0,
                "duplicates_eliminated": 0,
                "new_tech_introduced": False,
                "size_before": len(self.rules.all_rules()),
                "size_after": len(self.rules.all_rules()) + 1,
                "functionality_growth": 0.3,
            }

            # ADL 审查
            adl_result = self.adl.review(change)
            if not adl_result.passed:
                result.actions_taken.append(
                    f"Phase3 ADL 阻止 [{v['source']}]: {adl_result.explanation}"
                )
                continue

            # VFM 评分
            vfm_total = self.vfm.score(change)
            if vfm_total < self.vfm.THRESHOLD:
                result.actions_taken.append(
                    f"Phase3 VFM 不达标 [{v['source']}]: {vfm_total}/{self.vfm.THRESHOLD}\n"
                    + self.vfm.breakdown(change)
                )
                continue

            # 生成新规则
            new_id = f"rule_evo_{promoted + 1:03d}"
            source_desc = v["source"].replace("::", " ")
            new_rule = Rule(
                id=new_id,
                priority=9,  # 低于原生的 P1-P8
                condition=f"语义匹配: {source_desc}",
                action=f"自动处理: {source_desc}",
                description=f"进化规则 v0.2: {source_desc} (触发{v['count']}次 验证分{verif_score})",
                trigger_count=0,
            )

            if self.rules.add_rule(new_rule):
                promoted += 1
                result.new_rules.append(new_rule.to_dict())
                result.actions_taken.append(
                    f"Phase3 规则提升: {new_id} — {new_rule.description}\n"
                    + f"  VFM={vfm_total}/{self.vfm.THRESHOLD} ADL=通过"
                )

        self.verified.clear()
        result.actions_taken.append(f"Phase3 完成: 提升 {promoted} 条新规则")
        self.phase = EvolutionPhase.RETIRE
        return result

    # ── Phase4: 淘汰维护 ──

    def _phase4_retire(self, result: EvolutionResult, memory_sys) -> EvolutionResult:
        """淘汰低价值规则 + MEMORY.md 蒸馏"""

        # 4a: 淘汰低触发规则
        retired = 0
        for rule in self.rules.all_rules():
            if rule.id.startswith("rule_evo_") and rule.trigger_count < self.RETIRE_THRESHOLD:
                if self.rules.disable_rule(rule.id):
                    retired += 1
                    result.retired_rules.append(rule.id)

        if retired > 0:
            result.actions_taken.append(
                f"Phase4 淘汰: {retired} 条低价值进化规则 (触发<{self.RETIRE_THRESHOLD}次)"
            )

        # 4b: MEMORY.md 蒸馏
        if memory_sys:
            distilled_items = memory_sys.distill(days=30)
            result.distilled = True
            result.actions_taken.append(f"Phase4 蒸馏: {'; '.join(distilled_items)}")

        # 4c: 知识图谱更新
        if memory_sys:
            memory_sys.add_entity("evolution_pipeline", "completed_cycle_on", memory_sys._today())
            memory_sys.add_entity("evolution_pipeline", "rules_count", str(len(self.rules.all_rules())))

        self.phase = EvolutionPhase.SIGNAL
        result.actions_taken.append("Phase4 完成 → 回到 Phase1")
        return result
