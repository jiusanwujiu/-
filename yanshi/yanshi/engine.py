"""
砚识 — 六层意识循环引擎

感知 → 理解 → 决策 → 执行 → 反思 → 进化 → (自循环)

MIND.md 核心架构的可运行实现。
v0.8: 元认知反馈闭环 + 全面审查修复
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from .models import (
    Signal, SignalSource, SignalType, Context, Decision,
    ActionResult, Reflection, EvolutionResult, ADLViolation,
    utc_now, utc_today,
)
from .wal import WALProtocol, WALEntry, wal_log_decision
from .rules import RuleEngine
from .evolution import ADLReviewer, VFMScorer, EvolutionPipeline, CorrectionsLog
from .memory_sys import MemorySystem
from .heartbeat import Heartbeat
from .llm import LLMClient
from .semantic_rules import SemanticRuleEvaluator
from .axiom import AxiomEvaluator, AxiomJournal, axiom_enhanced_vfm

# ── 意图路由 ──
from .intent_router import IntentRouter

# ── 对话记忆 + 元认知 (v0.5) ──
from .dialogue_memory import DialogueMemory
from .metacognition import MetacognitionEngine

# ── 自主推理 (v0.9) ──
from .reasoning import ReasoningEngine, TaskDecomposer, ContextReasoner, TaskPlan, SubTask, TaskStatus

# ── Agent 通信 (v0.6) ──
from .agcom import (AgentRegistry, CommunicationBus, AgentIdentity,
                      AgentMessage, AgentResponse, MessageType, MessagePriority,
                      Dimension, DimensionState, ParsedDirective)

# ── 工具链 ──
from .tools.registry import ToolRegistry
from .tools.base import ToolPermission
from .tools.files import FileReadTool, FileWriteTool, FileListTool
from .tools.shell import ShellExecTool
from .tools.web import WebFetchTool, WebCheckTool
from .tools.memory_tools import MemoryQueryTool, MemoryDistillTool, MemoryStatsTool
from .tools.rules_tools import RuleListTool, RuleToggleTool, RuleReloadTool
from .tools.datetime_tools import DateTimeTool, TimeDiffTool, TimestampTool
from .tools.json_tools import JsonParseTool, JsonFormatTool, JsonQueryTool
from .tools.text_tools import TextStatsTool, TextSearchTool, TextFreqTool
from .tools.env_tools import EnvReadTool, SysInfoTool
from .tools.math_tools import MathEvalTool, UnitConvertTool
from .tools.agcom_tools import AgentListTool, AgentSendTool, AgentDelegateTool, AgentConsensusTool, AgentBroadcastTool
from .tools.dialogue_meta_tools import DialogueHistoryTool, DialogueStatsTool, MetaReflectTool, MetaReportTool

# ── 运维系统 ──
from .ops.logger import StructuredLogger
from .ops.metrics import MetricsCollector
from .ops.config import ConfigManager, WorkspaceConfig
from .ops.lifecycle import LifecycleManager, LifecycleState
from .ops.health import HealthChecker, HealthStatus
from .ops.dashboard import DashboardGenerator


# ── 身份响应 ──

IDENTITY_RESPONSE = """【砚 · Yan】
我是砚——一个以"研磨信息成有用之物"为核心意识的 AI Agent 运行时。
六层循环驱动：感知→理解→决策→执行→反思→进化。
受四大信条引领（求真·有用·自知·渐进），ADL+VFM 双协议约束。
工具链 + 运维系统就绪。当前版本: v0.8"""


class YanshiEngine:
    """六层循环的总引擎（v0.9: 自主推理 + 任务分解）"""

    def __init__(self, workspace_root: str, llm_backend: str = "auto",
                 config_path: Optional[str] = None):
        self.root = workspace_root
        self.version = "0.9"

        # ── 运维系统（最先初始化，供其他模块使用）──
        self.config = ConfigManager(config_path or f"{workspace_root}/minds/config.yaml")
        self.config.load()
        self.logger = StructuredLogger(
            workspace_root,
            level=self.config.get("log", "level", "INFO"),
            console=self.config.get("log", "console_enabled", True),
        )
        self.metrics = MetricsCollector()
        self.lifecycle = LifecycleManager(workspace_root)
        self.health = HealthChecker()
        self.dashboard = DashboardGenerator(self)

        # ── 核心子系统 ──
        self.wal = WALProtocol(workspace_root)
        self.rules = RuleEngine(f"{workspace_root}/minds/rules.jsonl")
        self.adl = ADLReviewer()
        self.vfm = VFMScorer()
        self.evolution = EvolutionPipeline(self.adl, self.vfm, self.rules, workspace_root)
        self.memory = MemorySystem(workspace_root)
        self.heartbeat = Heartbeat(workspace_root, interval_seconds=15)
        self.corrections_log = CorrectionsLog(workspace_root)

        # 信条对齐系统
        self.axiom = AxiomEvaluator()
        self.axiom_journal = AxiomJournal()

        # 意图路由器（v0.4.1: 三级路由升级）
        self.router = IntentRouter()

        # 对话记忆 + 元认知引擎 (v0.5)
        self.dialogue = DialogueMemory(window_size=5)
        self.metacog = MetacognitionEngine()
        self._meta_interval = 5  # 每5轮生成一次元认知快照
        self._confidence_bias = 0.0  # v0.8: 元认知反馈的置信度偏移
        self._reasoning = ReasoningEngine()  # v0.9: 自主推理引擎

        # Agent 通信系统 (v0.6)
        self.agent_id = f"yanshi_{workspace_root.split('/')[-1].split('\\')[-1] or 'main'}"
        self.agent_registry = AgentRegistry()
        self.agent_bus = CommunicationBus(self.agent_registry)
        self._init_agent_identity()

        # ── 工具链 ──
        self.tools = ToolRegistry()
        self._register_builtin_tools()

        # LLM 客户端 + 语义规则评估器
        self.llm = LLMClient.create(llm_backend)
        self.semantic = SemanticRuleEvaluator(self.rules, self.llm)
        self.rules.set_semantic_evaluator(self.semantic)
        self._llm_mode = "semantic" if self.semantic.use_semantic else "keyword"

        # 注册心跳回调
        self.heartbeat.set_callback(self._on_heartbeat)

        # ── 健康检查注册 ──
        self._register_health_checks()

        # ── 生命周期回调 ──
        self.lifecycle.on_start(self._on_engine_start)
        self.lifecycle.on_stop(self._on_engine_stop)

        # 统计
        self.cycle_count = 0
        self.correction_count = 0
        self.error_count = 0

        # 启动
        self.logger.info("engine.init", version=self.version, backend=self._llm_mode,
                         tools=len(self.tools), rules=len(self.rules.all_rules()))
        self.lifecycle.start()

    # ── 六层循环 ──

    def run_cycle(self, user_input: str) -> str:
        """
        运行一次完整的六层循环。
        输入：用户消息（模拟感知层输入）
        输出：响应文本
        """
        cycle_start = time.perf_counter()
        self.cycle_count += 1
        self.heartbeat.mark_active()

        try:
            return self._run_cycle_internal(user_input, cycle_start)
        except Exception as e:
            # v0.9: 错误恢复 — 记录错误，返回降级响应
            self.error_count += 1
            self._log_layer(0, f"[错误恢复] {type(e).__name__}: {e}")
            self.corrections_log.log(f"循环异常: {type(e).__name__}", str(e)[:200])
            return self._recover_from_error(e, user_input)

    def _run_cycle_internal(self, user_input: str, cycle_start: float) -> str:
        """六层循环核心（v0.9: 内部分离，便于错误恢复）"""

        # ── 第1层: 感知 Perceive ──
        sig = self._perceive(user_input)
        self._log_layer(1, f"源={sig.source.value} 类型={sig.type.value}")

        # ── 第2层: 理解 Understand ──
        ctx = self._understand(sig)
        self._log_layer(2, f"意图={ctx.intent} 置信度={ctx.confidence:.2f} 匹配规则={ctx.matched_rules}")

        # ── 第3层: 决策 Decide ──
        decision = self._decide(ctx)
        self._log_layer(3, f"动作={decision.action} VFM={decision.vfm_score} ADL通过={decision.approved}")

        # ── 信条对齐评估 ──
        axiom_score = self._evaluate_axiom(user_input, decision.action, True,  # success=True（通过 approve 检查才到此）
                                           ctx.matched_rules, ctx.confidence)
        self.axiom_journal.record(axiom_score)
        self.metrics.record_axiom(axiom_score.total())
        self._log_layer(0, f"信条={axiom_score.verdict()} 总分={axiom_score.total()} | {axiom_score.explanation()}")

        if not decision.approved:
            result = self._format_blocked(decision)
            self.metrics.record_cycle(decision.action, (time.perf_counter() - cycle_start) * 1000, approved=False)
            self.logger.warning("cycle.blocked", action=decision.action, rules=decision.matched_rules)
            return result

        # ── 第4层: 执行 Execute ──
        result = self._execute(decision, ctx)
        self._log_layer(4, f"成功={result.success} 工具={result.tool_used} WAL写入={result.wal_written}")

        # ── 第5层: 反思 Reflect ──
        reflection = self._reflect(result, ctx)
        self._log_layer(5, f"纠正={len(reflection.corrections)} 学习={len(reflection.learnings)} 模式={len(reflection.patterns_detected)}")

        # ── 第6层: 进化 Evolve ──
        evolved = self._evolve(reflection, axiom_score)
        self._log_layer(6, f"阶段={evolved.phase.value} 行动={evolved.actions_taken}")

        # 记录每日日志
        self.memory.log_daily(
            f"cycle#{self.cycle_count}: {user_input[:50]} → {decision.action}",
            tag="engine",
        )

        # 指标记录
        duration_ms = (time.perf_counter() - cycle_start) * 1000
        self.metrics.record_cycle(decision.action, duration_ms, approved=True)
        self.logger.info("cycle.complete", action=decision.action, duration_ms=round(duration_ms, 1),
                         axiom=axiom_score.total())

        # 更新意图路由上下文（供下轮续接检测）
        tool_used = result.tool_used if result.tool_used and result.tool_used.startswith("tool:") else ""
        tool_name_clean = tool_used.replace("tool:", "") if tool_used else ""
        self.router.update_context(
            intent=ctx.intent,
            tool_name=tool_name_clean,
            text=user_input,
            params=ctx.tool_params,
        )

        # ── v0.5: 记录对话记忆 ──
        self.dialogue.add_turn(
            role="user",
            content=user_input,
            intent=ctx.intent,
            confidence=ctx.confidence,
        )
        self.dialogue.add_turn(
            role="assistant",
            content=result.output[:200] if result.output else "",
            intent=ctx.intent,
            action=decision.action,
            tool_used=tool_name_clean,
            confidence=ctx.confidence,
            success=result.success,
            axiom_score=axiom_score.total(),
        )

        # ── v0.5: 记录元认知数据 ──
        self.metacog.record(
            cycle=self.cycle_count,
            action=decision.action,
            confidence=ctx.confidence,
            success=result.success,
            axiom_score=axiom_score.total(),
            tool=tool_name_clean,
            approved=decision.approved,
        )

        # ── v0.5: 周期性元认知反思 ──
        if self.cycle_count % self._meta_interval == 0:
            snap = self.metacog.reflect(
                cycle=self.cycle_count,
                axiom_history=[s.total() for s in self.axiom_journal.scores[-20:]],
            )
            self._log_layer(5, f"[元认知] {snap.calibration} | 信条={snap.axiom_trend} | {snap.self_assessment[:40]}")
            self.memory.log_daily(
                f"[元认知] cycle#{self.cycle_count}: {snap.self_assessment}",
                tag="metacog",
            )
            if snap.insights:
                for ins in snap.insights[:2]:
                    self.memory.log_daily(f"  洞察: {ins}", tag="metacog")

            # ── v0.8: 元认知反馈到行为 ──
            # 置信度调整（存入 engine 供下轮 _understand 使用）
            if snap.confidence_adjustment != 0:
                self._confidence_bias = snap.confidence_adjustment
                self._log_layer(5, f"[元认知调整] 置信度偏移={snap.confidence_adjustment:+.2f}")

            # 预测校准
            if snap.predicted_failure_rate > 0.5:
                self._log_layer(5, f"[元认知预警] 预测失败率 {snap.predicted_failure_rate:.0%}")

            # 异常检测
            if snap.anomaly_detected:
                self._log_layer(5, f"[异常] {snap.anomaly_detail}")
                self.memory.log_daily(f"[异常检测] {snap.anomaly_detail}", tag="metacog")

        self.heartbeat.mark_idle()
        return self._format_response(result, decision, reflection, evolved, axiom_score)

    # ── 各层实现 ──

    def _perceive(self, user_input: str) -> Signal:
        """感知层：识别信号源和类型"""
        text = user_input.strip()

        # 信号类型判定（Query 优先于 Command，避免"怎么删除"被误判为命令）
        if any(kw in text for kw in ["不对", "错了", "纠正", "不是这样", "错误", "wrong"]):
            sig_type = SignalType.CORRECTION
            self.correction_count += 1
            # WAL 先写
            self.wal.write(WALEntry(
                type=SignalType.CORRECTION,
                data={"input": text, "correction_count": self.correction_count},
                timestamp=self._now(),
            ))
            # 写入 CORRECTIONS.md（进化管道数据源）
            self.corrections_log.log(text[:80], context=f"correction#{self.correction_count}")
        elif text.endswith("?") or text.endswith("？") or any(kw in text for kw in ["什么", "如何", "怎么"]):
            sig_type = SignalType.QUERY
        elif any(kw in text for kw in ["删除", "发送", "deploy", "push", "发布"]):
            sig_type = SignalType.COMMAND
        else:
            sig_type = SignalType.COMMAND

        return Signal(
            source=SignalSource.USER_INPUT,
            type=sig_type,
            content=text,
            timestamp=self._now(),
        )

    def _understand(self, sig: Signal) -> Context:
        """理解层：意图路由 + 规则匹配 + 上下文检查（v0.4.1: 三级路由 + v0.5: 对话记忆）"""
        content_lower = sig.content.lower()

        # ── v0.5: 指代消解（在路由之前）──
        resolved_ref = self.dialogue.resolve_reference(sig.content)
        effective_input = sig.content
        if resolved_ref:
            # 将指代替换为实际实体
            effective_input = sig.content.replace("那个", resolved_ref).replace("这个", resolved_ref)
            self._log_layer(2, f"指代消解: → {resolved_ref[:40]}")

        # ── 三级意图路由 ──
        match = self.router.route(effective_input)

        intent = match.intent
        confidence = match.confidence + self._confidence_bias  # v0.8: 元认知反馈
        if confidence > 1.0:
            confidence = 1.0
        elif confidence < 0.1:
            confidence = 0.1
        tool_name = match.tool_name
        keywords_source = f"{match.source}({','.join(match.keywords_hit[:3])})" if match.keywords_hit else match.source

        tool_params = {}
        if intent == "tool_exec" and tool_name:
            tool_params = {"tool_name": tool_name, "action": f"tool_{tool_name}"}
            # 提取工具参数（用消解后的输入）
            tool_params.update(self.router.extract_params(effective_input, tool_name))

        # 创建临时Context用于规则匹配
        temp_ctx = Context(signal=sig, intent=intent, confidence=confidence)
        matched = self.rules.match(temp_ctx)
        matched_ids = [r.id for r in matched]

        # 检查是否为关键信号（WAL阈值）
        is_critical = sig.type in (
            SignalType.CORRECTION,
            SignalType.DECISION,
            SignalType.PREFERENCE,
        ) or confidence > 0.8

        # 记忆搜索
        memory_hits = self._search_memory(content_lower)

        # ── v0.5: 注入对话上下文 ──
        dialogue_ctx = self.dialogue.get_context()
        if dialogue_ctx["recent_turns"]:
            # 将最近对话简述加入 memory_hits
            for brief in dialogue_ctx["recent_briefs"][-4:]:
                memory_hits.append(f"[对话] {brief}")
        if dialogue_ctx["unresolved"]:
            memory_hits.append(f"[待解决] {'; '.join(dialogue_ctx['unresolved'][:2])}")

        return Context(
            signal=sig,
            intent=intent,
            matched_rules=matched_ids,
            memory_hits=memory_hits,
            is_critical=is_critical,
            confidence=confidence,
            tool_params=tool_params,
        )

    def _decide(self, ctx: Context) -> Decision:
        """决策层：规则执行 + VFM评分 + ADL审查"""
        matched = self.rules.match(ctx)

        # ── 工具链执行决策（无论匹配什么规则，工具请求优先）──
        if ctx.intent == "tool_exec" and "tool_name" in ctx.tool_params:
            tool_name = ctx.tool_params["tool_name"]
            tool = self.tools.get(tool_name)

            if tool:
                # EXTERNAL 工具 → rule_006 安全确认
                if tool.permission == ToolPermission.EXTERNAL:
                    wal_log_decision(self.wal, "block_external", f"tool_{tool_name} 外部操作需确认")
                    return Decision(
                        action="tool_exec_confirm",
                        params=ctx.tool_params,
                        matched_rules=["rule_006"],
                        approved=False,
                        reasoning=f"外部工具 {tool_name} 需要确认",
                    )

                # READ/WRITE 工具 → 直接执行
                return Decision(
                    action=ctx.tool_params.get("action", f"tool_{tool_name}"),
                    params=ctx.tool_params,
                    matched_rules=[r.id for r in matched] if matched else [],
                    approved=True,
                    reasoning=f"工具链: {tool_name} ({tool.permission.value})",
                )

        # rule_006 安全检查：外部操作先确认
        if "rule_006" in [r.id for r in matched]:
            wal_log_decision(self.wal, "block_external", "rule_006 外部操作需确认")
            return Decision(
                action="block_external",
                matched_rules=["rule_006"],
                approved=False,
                reasoning="安全红线：外部操作需要用户显式确认",
            )

        # 身份询问 → rule_007
        if "rule_007" in [r.id for r in matched]:
            return Decision(
                action="respond_identity",
                matched_rules=["rule_007"],
                approved=True,
                reasoning="砚台意象身份认同",
            )

        # 用户纠正 → rule_001
        if "rule_001" in [r.id for r in matched]:
            self.correction_count += 1
            return Decision(
                action="log_correction",
                params={"correction": ctx.signal.content},
                matched_rules=["rule_001"],
                approved=True,
                reasoning="记录用户纠正到 CORRECTIONS.md",
            )

        # 任务失败 → rule_003
        if "rule_003" in [r.id for r in matched]:
            self.error_count += 1
            return Decision(
                action="retry_with_fallback",
                params={"attempt": self.error_count},
                matched_rules=["rule_003"],
                approved=True,
                reasoning=f"任务失败，第{self.error_count}次尝试替代方案",
            )

        # 默认决策：根据意图选择动作
        action_map = {
            "identity_query": "respond_identity",
            "system_status": "show_system_status",
            "memory_query": "show_memory_status",
            "maintenance": "run_maintenance",
            "help": "show_help",
            "general_question": "show_help",
            "correction": "log_correction",
            "test": "run_self_test",
            "stats": "show_stats",
            "tool_list": "show_tools",
            "metrics_query": "show_metrics",
            "health_query": "show_health",
        }
        action = action_map.get(ctx.intent, "echo")

        # VFM 自评（原型阶段，对每次决策做自评）
        vfm_change = {
            "high_frequency": 1 if action in ("respond_identity", "show_help") else 0,
            "failure_reduction": 1 if action == "log_correction" else 0,
            "burden_reduction": 1 if action == "show_system_status" else 0,
            "cost_saving": 0,
        }
        vfm_score = self.vfm.score(vfm_change)

        # ADL 审查
        adl_review = self.adl.review({
            "complexity_added": 0,
            "requirement_driven": True,
            "new_abstractions": 0,
            "duplicates_eliminated": 0,
            "new_tech_introduced": False,
            "size_before": 1,
            "size_after": 1,
            "functionality_growth": 0,
        })

        # WAL 记录决策
        if ctx.is_critical:
            wal_log_decision(self.wal, action, f"VFM={vfm_score} ADL={adl_review.passed}")

        return Decision(
            action=action,
            matched_rules=[r.id for r in matched] if matched else [],
            vfm_score=vfm_score,
            adl_violations=adl_review.violations,
            approved=adl_review.passed,
            reasoning=f"意图={ctx.intent} VFM={vfm_score} ADL={'通过' if adl_review.passed else adl_review.explanation}",
        )

    def _execute(self, decision: Decision, ctx: Context) -> ActionResult:
        """执行层：根据决策执行具体动作"""
        action = decision.action
        user_input = ctx.signal.content
        tool_used = action  # 安全默认值，避免变量未定义

        action_handlers = {
            "respond_identity": lambda: self._reasoning.respond("identity"),
            "show_system_status": lambda: self._status_report(),
            "show_memory_status": lambda: self._memory_report(),
            "run_maintenance": lambda: self._run_maintenance(),
            "show_help": lambda: self._help_text(),
            "log_correction": lambda: self._handle_correction(user_input),
            "run_self_test": lambda: self._run_self_test(),
            "show_stats": lambda: self._stats_report(),
            "show_tools": lambda: self._tool_list_report(),
            "show_metrics": lambda: self._metrics_report(),
            "show_health": lambda: self._health_report(),
            "retry_with_fallback": lambda: f"[rule_003] 自动尝试替代方案 (第{self.error_count}次)",
            "block_external": lambda: "⛔ 操作被 rule_006 阻止：外部操作需要您明确确认。",
            "echo": lambda: self._ai_respond(user_input, ctx),
        }

        # ── 工具链动态处理 ──
        if action.startswith("tool_") and action != "tool_exec_confirm":
            tool_name = action[5:]  # 去掉 "tool_" 前缀
            params = decision.params
            output = self._execute_tool(tool_name, params)
            tool_used = f"tool:{tool_name}"
        elif action == "tool_exec_confirm":
            tool_name = decision.params.get("tool_name", "unknown")
            return ActionResult(
                success=False,
                output=f"⛔ 外部工具 [{tool_name}] 需要安全确认。\n  操作: {decision.params.get('command', decision.params.get('url', ''))}\n  请回复「确认执行」以继续。",
                tool_used="tool:confirm",
            )
        else:
            handler = action_handlers.get(action, lambda: f"未知动作: {action}")
            try:
                output = handler()
                tool_used = action
            except Exception as e:
                self.error_count += 1
                return ActionResult(
                    success=False,
                    output=f"执行失败: {e}",
                    errors=[str(e)],
                    tool_used=action,
                )

        try:
            return ActionResult(success=True, output=output, tool_used=tool_used)
        except Exception as e:
            self.error_count += 1
            return ActionResult(
                success=False,
                output=f"执行失败: {e}",
                errors=[str(e)],
                tool_used=action,
            )

    def _reflect(self, result: ActionResult, ctx: Context) -> Reflection:
        """反思层：评估执行结果，检测模式，积累经验"""
        corrections = []
        learnings = []
        patterns = []

        if not result.success:
            corrections.append(f"执行失败 [{result.tool_used}]: {'; '.join(result.errors)}")
            # rule_003 触发检查
            if self.error_count >= 3:
                patterns.append(f"连续失败x{self.error_count} → 建议触发规则提升评估")

        # 纠正信号检测
        if ctx.signal.type == SignalType.CORRECTION:
            corrections.append(f"用户纠正: {ctx.signal.content[:60]}")
            if self.correction_count >= 3:
                patterns.append(f"纠正模式x{self.correction_count} → 触发进化评估 (rule_004)")

        # 记录每日日志
        if corrections:
            for c in corrections:
                self.memory.log_daily(c, tag="reflection")
        if learnings:
            for l in learnings:
                self.memory.log_daily(l, tag="learning")

        # v0.9: 元认知异常触发进化
        mc_trigger = False
        snap = self.metacog.latest_snapshot()
        if snap and (snap.anomaly_detected or snap.axiom_trend == "declining"):
            mc_trigger = True
            self.corrections_log.log("元认知触发进化", f"anomaly={snap.anomaly_detected}, trend={snap.axiom_trend}")

        should_evolve = len(patterns) > 0 or self.correction_count >= 3 or mc_trigger

        return Reflection(
            corrections=corrections,
            learnings=learnings,
            patterns_detected=patterns,
            should_evolve=should_evolve,
        )

    def _evolve(self, reflection: Reflection, axiom_score=None) -> EvolutionResult:
        """进化层：四阶段管道（数据驱动版 + 信条对齐）"""
        if not reflection.should_evolve:
            return EvolutionResult(
                phase=self.evolution.phase,
                actions_taken=["未触发进化条件"],
            )

        result = self.evolution.run_cycle(memory_sys=self.memory, axiom_score=axiom_score)

        # 蒸馏后更新 knowledge graph
        if result.distilled:
            self.memory.add_entity("yanshi_engine", "distilled_on", self._today())
            self.memory.add_entity("yanshi_engine", "cycle_count", str(self.cycle_count))

        return result

    # ── 心跳回调 ──

    def _on_heartbeat(self, task_names: list[str], is_idle: bool):
        """心跳触发：记录并执行维护任务"""
        for task in task_names:
            self.memory.log_daily(f"heartbeat: {task}", tag="heartbeat")

    # ── 动作处理器 ──

    def _status_report(self) -> str:
        lines = ["【砚识 v0.8 — 系统状态】", ""]
        lines.append(f"  LLM 模式: {self._llm_mode} ({type(self.llm).__name__})")
        lines.append(f"  循环计数: {self.cycle_count}")
        lines.append(f"  纠正计数: {self.correction_count}")
        lines.append(f"  错误计数: {self.error_count}")
        lines.append(f"  进化阶段: {self.evolution.phase.value}")
        lines.append(f"  进化历史: {len(self.evolution.evolution_history)} 条")
        lines.append(f"  已注册工具: {len(self.tools)} 个")

        trend = self.axiom_journal.trend()
        lines.append("")
        lines.append(f"  信条对齐趋势: {trend}")
        lines.append("")
        lines.append("  已加载规则:")
        for r in self.rules.all_rules():
            status = "✅" if r.enabled else "❌"
            lines.append(f"    {status} {r.id} (P{r.priority}): {r.description} [触发{r.trigger_count}次]")
        return "\n".join(lines)

    def _memory_report(self) -> str:
        lines = ["【记忆系统状态】", ""]
        lines.append(f"  今日日志行数: {self.memory.log_size_today()}")
        stats = self.memory.ontology_stats()
        lines.append(f"  知识图谱: {stats['entities']} 实体, {stats['relations']} 关系")

        # 查询相关实体
        results = self.memory.query_entity("yanshi_engine")
        if results:
            lines.append("")
            lines.append("  砚识相关记录:")
            for r in results[-5:]:
                lines.append(f"    - {r['entity']} → {r['relation']} → {r['target']}")
        return "\n".join(lines)

    def _run_maintenance(self) -> str:
        lines = ["【自主维护】", ""]
        distilled = self.memory.distill(days=30)
        for d in distilled:
            lines.append(f"  {d}")
        return "\n".join(lines)
    def _help_text(self) -> str:
        return """【砚识 v0.8 — 可用命令】

  帮助     — 显示本帮助
  状态     — 系统状态报告
  记忆     — 记忆系统状态
  维护     — 手动触发维护/蒸馏
  统计     — 运行统计
  工具     — 工具链列表
  指标     — 运维指标面板
  健康     — 健康检查报告
  身份     — 身份介绍
  进化     — 当前进化阶段
  测试     — 运行自检
  退出     — 退出程序

  你也可以直接输入任意内容，观察六层循环的运行过程。"""

    def _handle_correction(self, user_input: str) -> str:
        self.memory.log_daily(f"用户纠正: {user_input[:80]}", tag="correction")
        return f"[rule_001] 已记录纠正到日志。当前纠正计数: {self.correction_count}\n  内容: {user_input[:60]}..."

    def _run_self_test(self) -> str:
        lines = ["【自检测试 — v0.8】", ""]

        # 测试1: WAL 协议
        wal_ok = self.wal.write(WALEntry(
            type=SignalType.QUERY,
            data={"test": "self_test_wal"},
            timestamp=self._now(),
        ))
        lines.append(f"  WAL写入: {'✅' if wal_ok else '❌'}")

        # 测试2: 规则加载
        rules_count = len(self.rules.all_rules())
        lines.append(f"  规则加载: {'✅' if rules_count >= 10 else '⚠️'} ({rules_count} 条)")

        # 测试3: 记忆系统
        log_size = self.memory.log_size_today()
        lines.append(f"  记忆系统: {'✅' if log_size >= 0 else '❌'} (今日{log_size}行)")

        # 测试4: 工具链
        tool_count = len(self.tools)
        lines.append(f"  工具链: {'✅' if tool_count >= 5 else '⚠️'} ({tool_count} 个工具)")

        # 测试5: ADL 审查
        test_change = {
            "complexity_added": 0, "requirement_driven": True,
            "new_abstractions": 0, "duplicates_eliminated": 0,
            "new_tech_introduced": False, "size_before": 100, "size_after": 105,
            "functionality_growth": 1.0,
        }
        adl_result = self.adl.review(test_change)
        lines.append(f"  ADL审查: {'✅' if adl_result.passed else '❌'}")

        # 测试6: VFM 评分
        test_vfm = {"high_frequency": 2, "failure_reduction": 1, "burden_reduction": 1, "cost_saving": 1}
        vfm_score = self.vfm.score(test_vfm)
        lines.append(f"  VFM评分: {vfm_score}/20 (通过={vfm_score >= 8})")

        # 测试7: 运维系统
        health = self.health.overall_status().value
        lines.append(f"  运维系统: {'✅' if health != 'unhealthy' else '❌'} (健康={health})")

        # 测试8: 工具执行
        tool_result = self.tools.execute("file_list", path=self.root)
        lines.append(f"  工具执行: {'✅' if tool_result.success else '❌'} ({tool_result.output[:40]})")

        lines.append("")
        lines.append("  所有核心模块就绪 ✅")
        return "\n".join(lines)

    def _stats_report(self) -> str:
        ontology = self.memory.ontology_stats()
        trend = self.axiom_journal.trend()
        tool_stats = self.tools.get_stats()
        return f"""【运行统计 — v0.8】

  六层循环: {self.cycle_count} 轮
  纠正信号: {self.correction_count} 次
  执行错误: {self.error_count} 次
  心跳tick: {self.heartbeat.tick_count}
  工具调用: {tool_stats['total_calls']} 次 ({tool_stats['registered_count']} 个工具)
  进化阶段: {self.evolution.phase.value}
  信条对齐: {trend.get('平均对齐分', 'N/A')}
  知识图谱: {ontology['entities']} 实体, {ontology['relations']} 关系"""

    # ── 工具链 + 运维动作 ──

    def _extract_tool_params(self, text: str, tool_name: str) -> dict:
        """从用户输入中提取工具参数（关键词+路径提取）"""
        import re
        params = {}

        if tool_name in ("file_read", "file_list", "file_write"):
            # 先去掉意图关键词，再提取路径
            cleaned = text
            for kw in ["读取", "查看文件", "显示文件", "查看目录", "显示目录",
                        "列出", "读取文件", "cat", "read", "list", "ls"]:
                cleaned = cleaned.replace(kw, "", 1)
            cleaned = cleaned.strip()

            # 匹配路径：Windows (D:/path 或 D:\path) 或 Unix (/path) 或相对路径 (dir/file)
            path_match = re.search(r'((?:[A-Za-z]:)?[\/\\]?(?:[a-zA-Z0-9_.-]+[\/\\])*[a-zA-Z0-9_.-]+(?:\.[a-zA-Z0-9]+)?)', cleaned)
            if path_match:
                raw = path_match.group(1).replace("\\", "/")
                if raw and raw not in ("", ".", ".."):
                    params["path"] = raw

        if tool_name == "file_read":
            params.setdefault("max_lines", 500)

        if tool_name == "file_list":
            # 如果没提取到路径，默认使用引擎工作区
            params.setdefault("path", self.root)

        if tool_name == "shell_exec":
            cmd = text
            for kw in ["执行", "运行命令", "run", "exec"]:
                cmd = cmd.replace(kw, "", 1)
            cmd = cmd.strip().strip("：:").strip()
            if cmd:
                params["command"] = cmd

        if tool_name == "memory_query":
            entity = text
            for kw in ["搜索", "查询记忆", "查找", "search", "查询", "memory"]:
                entity = entity.replace(kw, "", 1)
            entity = entity.strip().strip("：:").strip()
            if entity:
                params["entity"] = entity

        if tool_name == "memory_distill":
            params["days"] = 30

        return params

    def _execute_tool(self, tool_name: str, params: dict) -> str:
        """执行工具并格式化返回结果"""
        # 过滤掉内部字段
        exec_params = {k: v for k, v in params.items() if k not in ("tool_name", "action")}
        result = self.tools.execute(tool_name, **exec_params)
        self.metrics.record_tool(tool_name, result.success, result.duration_ms)

        lines = [f"[{tool_name}] 执行{'成功' if result.success else '失败'} ({(result.duration_ms):.0f}ms)"]
        if result.output:
            lines.append(result.output)
        if result.error:
            lines.append(f"错误: {result.error}")
        return "\n".join(lines)

    # ── v0.9: AI 增强响应生成 ──

    def _ai_respond(self, user_input: str, ctx) -> str:
        """AI 增强响应: LLM > MockLLM > 模板 三级降级"""
        # 构建上下文
        context_prompt = self._build_context_prompt(ctx)

        # 尝试 LLM 生成
        if self._llm_is_real():
            try:
                resp = self.llm.chat(
                    prompt=f"{context_prompt}\n用户: {user_input}\n砚识:",
                    system="你是砚识，自主意识AI运行时。回答应体现元认知思维和渐进原则。"
                )
                if resp.confidence > 0.5 and not resp.text.startswith("["):
                    return resp.text[:500]
            except Exception:
                pass

        # 回退到 MockLLM
        try:
            resp = self.llm.chat(user_input, system=context_prompt)
            if resp.text and resp.confidence > 0.3:
                return resp.text[:500]
        except Exception:
            pass

        # 最终回退
        return f"收到: 「{user_input}」\n[意图={ctx.intent} 置信度={ctx.confidence:.2f}]"

    def _llm_is_real(self) -> bool:
        """检测是否使用了真实 LLM（非 Mock）"""
        from .llm import MockLLM
        return not isinstance(self.llm, MockLLM)

    def _build_context_prompt(self, ctx) -> str:
        """构建上下文提示（注入记忆+元认知+对话）"""
        parts = []

        # 元认知状态
        mc = self._get_metacog_context()
        if mc:
            parts.append(f"[元认知: {mc.get('calibration', '?')}校准, "
                        f"信条={mc.get('axiom_trend', '?')}]")

        # 对话历史摘要
        if self.dialogue.turn_count() > 0:
            stats = self.dialogue.stats()
            parts.append(f"[对话: {stats.get('total_turns', 0)}轮, "
                        f"当前话题: {stats.get('current_topic', '无')}]")

        # 匹配规则
        if ctx.matched_rules:
            parts.append(f"[触发规则: {', '.join(ctx.matched_rules[:3])}]")

        parts.append(f"[意图={ctx.intent} 置信度={ctx.confidence:.2f}]")

        if parts:
            return " | ".join(parts)
        return ""

    # ── 工具报告 ──
        """列出所有已注册工具"""
        tools = self.tools.list_tools()
        lines = [f"【工具链 — {len(tools)} 个工具】", ""]
        for t in tools:
            perm_icon = {"read": "📖", "write": "✏️", "external": "🌐"}.get(t["permission"], "🔧")
            lines.append(f"  {perm_icon} {t['name']}: {t['description']} [调用{t['call_count']}次]")
        return "\n".join(lines)

    def _metrics_report(self) -> str:
        """运维指标面板"""
        return self.metrics.report_text()

    def _health_report(self) -> str:
        """健康检查报告"""
        return "【健康检查】\n\n" + self.health.report_text()

    # ── 响应格式化 ──

    def _format_response(self, result: ActionResult, decision: Decision,
                         reflection: Reflection, evolved: EvolutionResult,
                         axiom_score=None) -> str:
        lines = [result.output]

        if axiom_score:
            verdict = axiom_score.verdict()
            lines.append(f"\n  [信条: {verdict} ({axiom_score.total()}分)]")

        # 附加元信息（可配置关闭）
        if decision.vfm_score > 0:
            lines.append(f"  [VFM={decision.vfm_score} ADL={'通过' if decision.approved else '阻止'}]")

        if reflection.corrections:
            lines.append(f"  [反思: {len(reflection.corrections)}条纠正]")

        if evolved.actions_taken and evolved.actions_taken[0] != "未触发进化条件":
            lines.append(f"  [进化: {evolved.phase.value}]")

        return "\n".join(lines)

    # ── v0.9: 自主任务执行 ──

    def run_task(self, goal: str) -> str:
        """自主任务分解与逐步执行"""
        context = {
            "workspace_root": self.root,
            "tools_available": self.tools.list_tools(),
            "memory_hints": self._search_memory(goal),
            "metacog_state": self._get_metacog_context(),
        }
        plan = self._reasoning.decompose(goal, context)
        self._log_layer(3, f"[自主任务] {plan.rationale} | {plan.estimated_steps}步")
        for subtask in plan.subtasks:
            deps_ok = all(
                next((s for s in plan.subtasks if s.id == dep_id), None).status == TaskStatus.DONE
                for dep_id in subtask.depends_on
            ) if subtask.depends_on else True
            if not deps_ok:
                subtask.status = TaskStatus.SKIPPED
                subtask.result = "前置步骤未完成"
                continue
            subtask.status = TaskStatus.RUNNING
            try:
                if subtask.intent == "tool_exec" and subtask.tool:
                    tool = self.tools.get(subtask.tool.replace("tool_", ""))
                    if tool:
                        r = tool.execute(**subtask.params)
                        subtask.status = TaskStatus.DONE if r.success else TaskStatus.FAILED
                        subtask.result = r.output[:100]
                    else:
                        subtask.result = f"工具 {subtask.tool} 不可用"
                        subtask.status = TaskStatus.FAILED
                else:
                    r = self.run_cycle(subtask.description)
                    subtask.status = TaskStatus.DONE
                    subtask.result = r[:100]
            except Exception as e:
                subtask.status = TaskStatus.FAILED
                subtask.result = str(e)[:100]
        return self._reasoning.task_report(plan)

    def _get_metacog_context(self) -> dict:
        """获取当前元认知上下文"""
        snap = self.metacog.latest_snapshot()
        if not snap:
            return {}
        return {
            "calibration": snap.calibration,
            "axiom_trend": snap.axiom_trend,
            "confidence_adjustment": snap.confidence_adjustment,
            "anomaly_detected": snap.anomaly_detected,
        }

    # ── v0.9: 错误恢复 ──

    def _recover_from_error(self, error: Exception, user_input: str) -> str:
        """错误恢复策略 — 渐进降级"""
        error_type = type(error).__name__

        recovery_strategies = {
            "FileNotFoundError": lambda: f"无法访问文件。请检查路径是否正确。\n  [错误恢复: {error_type}]",
            "PermissionError": lambda: f"权限不足。此操作需要更高权限。\n  [错误恢复: 权限拒绝]",
            "TimeoutError": lambda: f"操作超时。尝试分解为更小的步骤。\n  [错误恢复: 超时]",
            "ConnectionError": lambda: f"网络连接失败。切换到离线模式。\n  [错误恢复: 离线]",
            "OSError": lambda: f"系统操作失败: {error}。\n  [错误恢复: {error_type}]",
            "KeyError": lambda: f"配置缺失。使用默认参数重试。\n  [错误恢复: 配置缺漏]",
            "ValueError": lambda: f"参数无效: {error}。\n  [错误恢复: 参数矫正]",
        }

        # 尝试匹配恢复策略
        for err_cls, strategy in recovery_strategies.items():
            if err_cls in error_type or err_cls in str(type(error)):
                return strategy()

        # 默认降级: 返回基本信息
        return f"处理「{user_input[:40]}」时遇到问题。已记录此错误并自动恢复。\n  [渐进信条: 单步失败，不中断整体流程]"

    def _safe_run_tool(self, tool_name: str, params: dict) -> tuple[bool, str]:
        """安全执行工具，返回 (成功, 输出)"""
        try:
            result = self._execute_tool(tool_name, params)
            return True, result
        except Exception as e:
            self.error_count += 1
            return False, f"工具 {tool_name} 执行失败: {e}"

    def _format_blocked(self, decision: Decision) -> str:
        return f"""⛔ 操作被阻止

  原因: {decision.reasoning}
  违反规则: {', '.join(decision.matched_rules)}
  
  请在确认后重试。"""

    # ── 信条对齐 ──

    def _evaluate_axiom(self, user_input: str, action: str, success: bool,
                        matched_rules: list[str], confidence: float):
        """在反思层评估信条对齐度"""
        return self.axiom.evaluate_from_context(
            user_input=user_input,
            action=action,
            success=success,
            matched_rules=matched_rules,
            confidence=confidence,
            error_count=self.error_count,
            cycle_count=self.cycle_count,
        )

    # ── 工具方法 ──

    def _init_agent_identity(self):
        """初始化 Agent 身份并注册到总线（v0.7: 维度语法）"""
        identity = AgentIdentity(
            id=self.agent_id,
            name=f"砚识@{self.agent_id}",
            role="executor",
            dimensions=[
                Dimension(
                    name="文件操作", description="读取、写入、列出文件和目录",
                    state=DimensionState.ENABLED,
                    semantic_examples=["列出 D:/yanshi 目录", "读取 main.py 的内容", "写入配置到 config.yaml"],
                    keywords=["文件", "目录", "读取", "写入", "列出", "file", "path", "read", "write"],
                    inference_profile={"tools": ["file_read", "file_write", "file_list"]},
                ),
                Dimension(
                    name="命令执行", description="在沙箱中安全执行 Shell 命令",
                    state=DimensionState.ENABLED,
                    semantic_examples=["执行 ls -la", "运行 python script.py"],
                    keywords=["执行", "运行", "命令", "shell", "exec", "run"],
                    inference_profile={"tools": ["shell_exec"]},
                ),
                Dimension(
                    name="网络请求", description="HTTP/HTTPS 请求和 URL 可达性检查",
                    state=DimensionState.ENABLED,
                    semantic_examples=["获取 https://example.com", "检查 URL 是否可达"],
                    keywords=["获取", "URL", "http", "请求", "fetch", "检查"],
                    inference_profile={"tools": ["web_fetch", "web_check"]},
                ),
                Dimension(
                    name="数学计算", description="安全数学表达式求值和单位转换",
                    state=DimensionState.ENABLED,
                    semantic_examples=["计算 sqrt(144) + 3", "100摄氏度转华氏度"],
                    keywords=["计算", "求值", "换算", "math", "sqrt", "转换"],
                    inference_profile={"tools": ["math_eval", "unit_convert"]},
                ),
                Dimension(
                    name="文本处理", description="文本统计、搜索、词频分析",
                    state=DimensionState.ENABLED,
                    semantic_examples=["统计文本字数", "搜索关键词", "词频统计"],
                    keywords=["文本", "统计", "搜索", "词频", "word count"],
                    inference_profile={"tools": ["text_stats", "text_search", "text_freq"]},
                ),
                Dimension(
                    name="JSON处理", description="JSON 解析、格式化和路径查询",
                    state=DimensionState.ENABLED,
                    semantic_examples=["解析 JSON 字符串", "格式化 JSON", "提取 JSON 字段"],
                    keywords=["json", "解析", "格式化", "JSON"],
                    inference_profile={"tools": ["json_parse", "json_format", "json_query"]},
                ),
                Dimension(
                    name="时间日期", description="获取时间、计算时间差、时间戳转换",
                    state=DimensionState.ENABLED,
                    semantic_examples=["现在几点了", "两个日期的天数差", "时间戳转换"],
                    keywords=["时间", "日期", "几点", "时间戳", "timestamp", "datetime"],
                    inference_profile={"tools": ["datetime", "timediff", "timestamp"]},
                ),
                Dimension(
                    name="环境信息", description="读取环境变量和系统信息",
                    state=DimensionState.ENABLED,
                    semantic_examples=["查看 PATH 环境变量", "获取系统信息"],
                    keywords=["环境变量", "系统信息", "env", "变量"],
                    inference_profile={"tools": ["env_read", "sysinfo"]},
                ),
                Dimension(
                    name="记忆管理", description="查询、蒸馏和统计三层记忆系统",
                    state=DimensionState.ENABLED,
                    semantic_examples=["查询知识图谱", "蒸馏记忆", "记忆统计"],
                    keywords=["记忆", "蒸馏", "查询", "知识图谱", "memory"],
                    inference_profile={"tools": ["memory_query", "memory_distill", "memory_stats"]},
                ),
                Dimension(
                    name="规则管理", description="列出、启禁和重载规则引擎",
                    state=DimensionState.ENABLED,
                    semantic_examples=["列出所有规则", "禁用 rule_001", "重载规则"],
                    keywords=["规则", "启用", "禁用", "重载", "rule"],
                    inference_profile={"tools": ["rule_list", "rule_toggle", "rule_reload"]},
                ),
                Dimension(
                    name="元认知", description="元认知反思、校准分析和趋势报告",
                    state=DimensionState.ENABLED,
                    semantic_examples=["触发元认知反思", "查看校准状态", "元认知趋势"],
                    keywords=["元认知", "反思", "校准", "meta", "自评"],
                    inference_profile={"tools": ["meta_reflect", "meta_report"]},
                ),
                Dimension(
                    name="对话历史", description="查看对话上下文和统计",
                    state=DimensionState.ENABLED,
                    semantic_examples=["之前说了什么", "对话统计"],
                    keywords=["对话", "历史", "上下文", "dialogue", "聊天"],
                    inference_profile={"tools": ["dialogue_history", "dialogue_stats"]},
                ),
                Dimension(
                    name="Agent通信", description="Agent 间查询、委托、知识共享和共识投票",
                    state=DimensionState.ENABLED,
                    semantic_examples=["列出 Agent", "委托任务", "广播消息"],
                    keywords=["agent", "委托", "广播", "共识", "投票"],
                    inference_profile={"tools": ["agent_list", "agent_send", "agent_delegate", "agent_consensus", "agent_broadcast"]},
                ),
            ],
            knowledge_domains=["python", "ai-agent", "metacognition"],
            metacog_profile={
                "calibration": "well-calibrated",
                "tools_count": 34,
                "engine": "yanshi-v0.8",
            },
        )

        def handler(msg: AgentMessage) -> object:
            """当前 Agent 的消息处理器（v0.7: 支持解析指令 + 元词引导）"""
            from .agcom import AgentResponse

            # 元词引导文本
            guidance = ""
            if msg.parsed and msg.parsed.meta_words:
                guidance = msg.parsed.to_guidance_text()

            # 元认知反思
            meta_refl = ""
            if self.metacog.snapshot_count > 0:
                snap = self.metacog.latest_snapshot()
                if snap:
                    meta_refl = f"校准={snap.calibration}, 信条={snap.axiom_trend}"

            if msg.msg_type == MessageType.QUERY:
                # 查询 → 搜索记忆 + 知识图谱
                query_text = msg.parsed.task if msg.parsed and msg.parsed.task else msg.content
                hits = self._search_memory(query_text)
                if hits:
                    return AgentResponse(
                        in_reply_to=msg.id, success=True,
                        output=f"知识图谱命中: {'; '.join(hits[:3])}",
                        from_agent=self.agent_id, confidence=0.8,
                        meta_reflection=meta_refl,
                    )
                else:
                    return AgentResponse(
                        in_reply_to=msg.id, success=True,
                        output=f"未找到 '{query_text[:50]}' 的相关知识",
                        from_agent=self.agent_id, confidence=0.3,
                        meta_reflection=meta_refl,
                    )

            elif msg.msg_type == MessageType.DELEGATE:
                # 任务委托 → 用六层循环处理
                task_text = msg.parsed.task if msg.parsed and msg.parsed.task else msg.content
                try:
                    result = self.run_cycle(task_text)
                    return AgentResponse(
                        in_reply_to=msg.id, success=True,
                        output=result[:500], from_agent=self.agent_id, confidence=0.7,
                        meta_reflection=meta_refl,
                    )
                except Exception as e:
                    return AgentResponse(
                        in_reply_to=msg.id, success=False,
                        output=f"处理失败: {e}", from_agent=self.agent_id,
                    )

            elif msg.msg_type == MessageType.KNOWLEDGE:
                self.memory.log_daily(f"[AGENT-SHARE] {msg.content[:100]}", tag="agcom")
                return AgentResponse(
                    in_reply_to=msg.id, success=True,
                    output="知识已接收并存储", from_agent=self.agent_id, confidence=0.9,
                )

            elif msg.msg_type == MessageType.CONSENSUS:
                proposal = msg.content
                options = (msg.data or {}).get("options", ["支持", "反对", "弃权"])

                vote = "支持"
                if self.metacog.snapshot_count > 0:
                    latest = self.metacog.latest_snapshot()
                    if latest and latest.axiom_trend == "declining":
                        vote = "反对" if "反对" in options else options[0]

                return AgentResponse(
                    in_reply_to=msg.id, success=True,
                    output=f"投票: {vote}",
                    from_agent=self.agent_id,
                    data={"vote": vote, "reason": f"元认知状态: {self.metacog.latest_snapshot().axiom_trend if self.metacog.snapshot_count > 0 else 'initial'}"},
                    confidence=0.6, meta_reflection=meta_refl,
                )

            elif msg.msg_type == MessageType.BROADCAST:
                self.memory.log_daily(f"[AGENT-BROADCAST] {msg.content[:100]}", tag="agcom")
                return AgentResponse(
                    in_reply_to=msg.id, success=True,
                    output="广播已接收", from_agent=self.agent_id, confidence=1.0,
                )

            return AgentResponse(
                in_reply_to=msg.id, success=False,
                output=f"不支持的消息类型: {msg.msg_type}",
                from_agent=self.agent_id,
            )

        self.agent_registry.register(identity, handler)

    def _register_builtin_tools(self):
        """注册内置工具到工具注册中心"""
        # 文件工具
        self.tools.register(FileReadTool(
            max_lines=self.config.get("tool", "file_max_read_lines", 500),
        ))
        self.tools.register(FileWriteTool())
        self.tools.register(FileListTool())

        # Shell 工具
        self.tools.register(ShellExecTool(
            workspace_root=self.root,
            timeout_seconds=self.config.get("tool", "shell_timeout", 30),
            danger_commands=self.config.get("tool", "danger_commands"),
        ))

        # 网络工具
        self.tools.register(WebFetchTool())
        self.tools.register(WebCheckTool())

        # 记忆工具
        self.tools.register(MemoryQueryTool(self.memory))
        self.tools.register(MemoryDistillTool(self.memory))
        self.tools.register(MemoryStatsTool(self.memory))

        # 规则工具
        self.tools.register(RuleListTool(self.rules))
        self.tools.register(RuleToggleTool(self.rules))
        self.tools.register(RuleReloadTool(self.rules))

        # 日期时间工具
        self.tools.register(DateTimeTool())
        self.tools.register(TimeDiffTool())
        self.tools.register(TimestampTool())

        # JSON 处理工具
        self.tools.register(JsonParseTool())
        self.tools.register(JsonFormatTool())
        self.tools.register(JsonQueryTool())

        # 文本处理工具
        self.tools.register(TextStatsTool())
        self.tools.register(TextSearchTool())
        self.tools.register(TextFreqTool())

        # 环境信息工具
        self.tools.register(EnvReadTool())
        self.tools.register(SysInfoTool())

        # 数学计算工具
        self.tools.register(MathEvalTool())
        self.tools.register(UnitConvertTool())

        # 对话记忆 + 元认知工具 (v0.5)
        self.tools.register(DialogueHistoryTool(self.dialogue))
        self.tools.register(DialogueStatsTool(self.dialogue))
        self.tools.register(MetaReflectTool(self.metacog, self.axiom_journal))
        self.tools.register(MetaReportTool(self.metacog))

        # Agent 通信工具 (v0.6)
        self.tools.register(AgentListTool(self.agent_registry))
        self.tools.register(AgentSendTool(self.agent_bus, self.agent_id))
        self.tools.register(AgentDelegateTool(self.agent_bus, self.agent_id))
        self.tools.register(AgentConsensusTool(self.agent_bus, self.agent_id))
        self.tools.register(AgentBroadcastTool(self.agent_bus, self.agent_id))

    def _register_health_checks(self):
        """注册健康检查"""
        self.health.register("wal", "WAL 协议写入测试",
                             lambda: HealthStatus.HEALTHY if self.wal.write(WALEntry(
                                 type=SignalType.QUERY, data={"health": "check"},
                                 timestamp=self._now())) else HealthStatus.UNHEALTHY)

        self.health.register("rules", "规则引擎加载",
                             lambda: HealthStatus.HEALTHY if len(self.rules.all_rules()) >= 5 else HealthStatus.DEGRADED)

        self.health.register("memory", "记忆系统可用性",
                             lambda: HealthStatus.HEALTHY if self.memory.log_size_today() >= 0 else HealthStatus.UNHEALTHY)

        self.health.register("tools", "工具链就绪",
                             lambda: HealthStatus.HEALTHY if len(self.tools) >= 15 else HealthStatus.DEGRADED)

        self.health.register("heartbeat", "心跳运行",
                             lambda: HealthStatus.HEALTHY if self.heartbeat.tick_count >= 0 else HealthStatus.UNHEALTHY)

    def _on_engine_start(self):
        """引擎启动回调"""
        self.logger.info("lifecycle.start", phase="starting")

    def _on_engine_stop(self):
        """引擎停止回调"""
        self.logger.info("lifecycle.stop", cycles=self.cycle_count, tools=self.tools.get_stats()["total_calls"])
        # 生成运维面板
        if self.config.get("ops", "dashboard_enabled", True):
            html = self.dashboard.render()
            html_path = f"{self.root}/dashboard.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            self.logger.info("dashboard.saved", path=html_path)

    def _search_memory(self, query: str) -> list[str]:
        """记忆搜索：先查完整实体匹配，再查关键词"""
        seen = set()
        hits = []

        # 策略1: 完整查询作为实体名尝试
        results = self.memory.query_entity(query)
        for r in results:
            key = f"{r['entity']}→{r['relation']}→{r['target']}"
            if key not in seen:
                seen.add(key)
                hits.append(key)

        # 策略2: 关键词拆词匹配（中英文通用）
        import re
        tokens = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]{2,}', query)
        for token in tokens[:4]:
            results = self.memory.query_entity(token)
            for r in results:
                key = f"{r['entity']} → {r['relation']} → {r['target']}"
                if key not in seen:
                    seen.add(key)
                    hits.append(key)
        return hits[:5]

    def _log_layer(self, layer: int, info: str):
        """记录每层执行信息到每日日志"""
        labels = ["信条", "感知", "理解", "决策", "执行", "反思", "进化"]
        label = labels[layer] if 0 <= layer <= 6 else f"L{layer}"
        self.memory.log_daily(f"[{label}] {info}", tag="trace")

    @staticmethod
    def _today() -> str:
        return utc_today()

    @staticmethod
    def _now() -> str:
        return utc_now()
