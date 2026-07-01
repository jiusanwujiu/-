"""
砚识 v0.8 — 对话记忆管理器

三层对话记忆模型：
  Layer 1 — 即时窗口: 最近 N 轮完整对话（原文保留）
  Layer 2 — 会话摘要: 超出窗口的轮次压缩为主题摘要
  Layer 3 — 主题追踪: 跨会话的关键主题和未完成话题

核心思想: 像人类一样——刚说的话记得清楚，更早的只记得要点。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class DialogueTurn:
    """单轮对话记录"""
    turn_id: int
    role: str  # user / assistant
    content: str
    intent: str = ""
    action: str = ""
    tool_used: str = ""
    confidence: float = 0.0
    success: bool = True
    timestamp: str = ""
    axiom_score: int = 0

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "role": self.role,
            "content": self.content[:200],
            "intent": self.intent,
            "action": self.action,
            "tool": self.tool_used,
            "confidence": self.confidence,
            "success": self.success,
            "axiom": self.axiom_score,
        }

    def brief(self) -> str:
        """生成简短摘要"""
        parts = [f"#{self.turn_id}", self.role]
        if self.intent:
            parts.append(f"intent={self.intent}")
        if self.tool_used:
            parts.append(f"tool={self.tool_used}")
        if not self.success:
            parts.append("FAILED")
        parts.append(f"\"{self.content[:60]}\"")
        return " ".join(parts)


@dataclass
class TopicSummary:
    """主题摘要"""
    topic: str
    turn_range: tuple[int, int]  # (start_turn, end_turn)
    summary: str
    key_decisions: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "turns": f"#{self.turn_range[0]}-#{self.turn_range[1]}",
            "summary": self.summary,
            "decisions": self.key_decisions,
            "unresolved": self.unresolved,
        }


class DialogueMemory:
    """
    对话记忆管理器 — 滑动窗口 + 压缩摘要 + 主题追踪。

    用法:
        dm = DialogueMemory(window_size=5)
        dm.add_turn("user", "列出文件", intent="tool_exec", tool_used="file_list")
        dm.add_turn("assistant", "找到3个文件...", success=True)

        # 获取上下文（注入理解层）
        context = dm.get_context()  # 最近5轮 + 摘要

        # 超过窗口时自动压缩
        dm.add_turn(...)  # 第6轮 → 轮1-2被压缩为摘要
    """

    def __init__(self, window_size: int = 5, max_summaries: int = 10):
        self.window_size = window_size
        self.max_summaries = max_summaries

        self._turns: list[DialogueTurn] = []
        self._summaries: list[TopicSummary] = []
        self._current_topic: Optional[str] = None
        self._turn_counter: int = 0

        # 主题切换检测关键词
        self._topic_shift_markers = [
            "换个话题", "另外", "对了", "接下来", "现在",
            "说回", "回到", "刚才那个", "继续之前",
        ]

    @property
    def turn_count(self) -> int:
        return self._turn_counter

    @property
    def current_topic(self) -> Optional[str]:
        return self._current_topic

    def add_turn(
        self,
        role: str,
        content: str,
        intent: str = "",
        action: str = "",
        tool_used: str = "",
        confidence: float = 0.0,
        success: bool = True,
        axiom_score: int = 0,
    ) -> DialogueTurn:
        """添加一轮对话，返回 turn 记录"""
        self._turn_counter += 1
        turn = DialogueTurn(
            turn_id=self._turn_counter,
            role=role,
            content=content,
            intent=intent,
            action=action,
            tool_used=tool_used,
            confidence=confidence,
            success=success,
            axiom_score=axiom_score,
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        )
        self._turns.append(turn)

        # 检测主题切换
        if role == "user":
            self._detect_topic_shift(content)

        # 窗口溢出 → 压缩最旧的一轮
        if len(self._turns) > self.window_size * 2:  # user+assistant 各一轮
            self._compress_oldest()

        return turn

    def get_context(self, max_turns: int = None) -> dict:
        """
        获取当前对话上下文（注入理解层）。
        返回: {recent_turns, summaries, current_topic, unresolved}
        """
        n = max_turns or self.window_size * 2
        recent = self._turns[-n:] if self._turns else []

        return {
            "recent_turns": [t.to_dict() for t in recent],
            "recent_briefs": [t.brief() for t in recent],
            "summaries": [s.to_dict() for s in self._summaries[-self.max_summaries:]],
            "current_topic": self._current_topic,
            "unresolved": self._collect_unresolved(),
            "total_turns": self._turn_counter,
        }

    def get_context_text(self) -> str:
        """生成可读的上下文文本（给理解层/LLM用）"""
        lines = []
        ctx = self.get_context()

        if ctx["summaries"]:
            lines.append("── 之前的话题 ──")
            for s in ctx["summaries"][-3:]:
                lines.append(f"  [{s['topic']}] {s['summary']}")
            lines.append("")

        if ctx["recent_turns"]:
            lines.append("── 最近对话 ──")
            for t in ctx["recent_turns"]:
                role_label = "用户" if t["role"] == "user" else "砚识"
                marker = "" if t["success"] else " ⚠️"
                lines.append(f"  #{t['turn_id']} {role_label}: \"{t['content']}\"{marker}")
            lines.append("")

        if ctx["unresolved"]:
            lines.append("── 待解决 ──")
            for u in ctx["unresolved"]:
                lines.append(f"  • {u}")

        return "\n".join(lines) if lines else "(无对话历史)"

    def resolve_reference(self, text: str) -> Optional[str]:
        """
        指代消解：检测文本中的指代词，返回引用的上下文。
        如 "那个文件" → 返回最近提到的文件路径。
        """
        if not self._turns:
            return None

        # 检测指代词
        pronouns = {
            "那个": "last_entity",
            "这个": "last_entity",
            "刚才": "last_turn",
            "上面": "last_turn",
            "它": "last_entity",
            "这": "current_topic",
        }

        for pronoun, ref_type in pronouns.items():
            if pronoun in text:
                if ref_type == "last_turn" and len(self._turns) >= 2:
                    return self._turns[-2].content  # 上一轮用户输入
                elif ref_type == "last_entity":
                    # 在最近所有窗口轮次中找实体（路径、URL等）
                    for t in reversed(self._turns):
                        import re
                        # 路径
                        path = re.search(r'[A-Za-z]:[/\\][^\s]+', t.content)
                        if path:
                            return path.group(0)
                        # URL
                        url = re.search(r'https?://[^\s]+', t.content)
                        if url:
                            return url.group(0)
                    # 也搜索摘要
                    for s in reversed(self._summaries):
                        import re
                        path = re.search(r'[A-Za-z]:[/\\][^\s]+', s.summary)
                        if path:
                            return path.group(0)
                    return None
                elif ref_type == "current_topic":
                    return self._current_topic

        return None

    def stats(self) -> dict:
        """对话记忆统计"""
        user_turns = [t for t in self._turns if t.role == "user"]
        assistant_turns = [t for t in self._turns if t.role == "assistant"]
        failed = [t for t in self._turns if not t.success]
        tools_used = [t.tool_used for t in self._turns if t.tool_used]

        return {
            "total_turns": self._turn_counter,
            "in_window": len(self._turns),
            "user_turns": len(user_turns),
            "assistant_turns": len(assistant_turns),
            "failed_turns": len(failed),
            "summaries": len(self._summaries),
            "current_topic": self._current_topic,
            "unique_tools": len(set(tools_used)),
            "avg_confidence": round(
                sum(t.confidence for t in self._turns) / len(self._turns), 2
            ) if self._turns else 0,
        }

    def reset(self):
        """重置对话记忆（新会话）"""
        self._turns.clear()
        self._summaries.clear()
        self._current_topic = None
        self._turn_counter = 0

    def export(self) -> str:
        """导出完整对话历史（JSON）"""
        data = {
            "turns": [t.to_dict() for t in self._turns],
            "summaries": [s.to_dict() for s in self._summaries],
            "topic": self._current_topic,
            "total": self._turn_counter,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    # ── 内部方法 ──

    def _detect_topic_shift(self, text: str):
        """检测主题切换（仅对明确的切换标记触发）"""
        text_lower = text.lower().strip()

        # 仅明确的主题切换标记才触发
        explicit_markers = ["换个话题", "说回", "回到", "继续之前"]
        for marker in explicit_markers:
            if marker in text_lower:
                old_topic = self._current_topic
                self._current_topic = self._infer_topic(text)
                if old_topic and old_topic != self._current_topic:
                    self._try_summarize_window(reason="topic_shift")
                return

        # 自然主题推断（不触发摘要压缩）
        inferred = self._infer_topic(text)
        if self._current_topic is None:
            self._current_topic = inferred
        elif inferred != "通用" and inferred != self._current_topic:
            # 主题自然变化，更新但不强制压缩
            self._current_topic = inferred

    @staticmethod
    def _infer_topic(text: str) -> str:
        """从文本推断主题"""
        topic_keywords = {
            "文件操作": ["文件", "读取", "写入", "目录", "file", "path"],
            "系统运维": ["执行", "命令", "shell", "进程", "系统"],
            "网络请求": ["url", "http", "获取", "检查", "web"],
            "数据处理": ["json", "文本", "统计", "解析", "格式化"],
            "数学计算": ["计算", "换算", "数学", "sqrt", "加减"],
            "时间日期": ["时间", "日期", "时间戳", "几点"],
            "记忆管理": ["记忆", "蒸馏", "日志", "查询"],
            "规则系统": ["规则", "启用", "禁用", "重载"],
            "身份对话": ["你是谁", "身份", "介绍", "帮助"],
            "纠正反馈": ["纠正", "不对", "错了", "修正"],
        }

        text_lower = text.lower()
        best_topic = "通用"
        best_score = 0

        for topic, keywords in topic_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_topic = topic

        return best_topic

    def _compress_oldest(self):
        """压缩最旧的一轮到摘要"""
        if len(self._turns) < 2:
            return

        # 取最旧的一对 (user + assistant)
        turn_pair = self._turns[:2]
        user_turn = turn_pair[0] if turn_pair[0].role == "user" else None
        asst_turn = turn_pair[1] if len(turn_pair) > 1 else None

        # 生成摘要
        topic = self._infer_topic(user_turn.content) if user_turn else "未知"
        summary_parts = []
        if user_turn:
            summary_parts.append(f"用户: \"{user_turn.content[:80]}\"")
        if asst_turn:
            status = "成功" if asst_turn.success else "失败"
            summary_parts.append(f"砚识({status}): intent={asst_turn.intent}, action={asst_turn.action}")

        summary = TopicSummary(
            topic=topic,
            turn_range=(turn_pair[0].turn_id, turn_pair[-1].turn_id),
            summary=" | ".join(summary_parts),
            key_decisions=[asst_turn.action] if asst_turn and asst_turn.action else [],
            unresolved=[] if asst_turn and asst_turn.success else [f"#{user_turn.turn_id} 未完成"],
            created_at=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        )
        self._summaries.append(summary)

        # 从窗口移除已压缩的轮次
        self._turns = self._turns[2:]

    def _try_summarize_window(self, reason: str = "auto"):
        """尝试将当前窗口总结为一个摘要"""
        if len(self._turns) < 2:
            return

        # 找到最近的主题边界
        topic = self._current_topic or "通用"
        all_turns = self._turns
        turn_range = (all_turns[0].turn_id, all_turns[-1].turn_id)

        # 简单摘要
        user_inputs = [t.content[:60] for t in all_turns if t.role == "user"]
        actions = [t.action for t in all_turns if t.action]
        failures = [f"#{t.turn_id}" for t in all_turns if not t.success]

        summary = TopicSummary(
            topic=topic,
            turn_range=turn_range,
            summary=f"涉及 {len(user_inputs)} 个问题，执行了 {len(set(actions))} 种动作",
            key_decisions=list(set(actions))[:3],
            unresolved=failures,
            created_at=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        )
        self._summaries.append(summary)

    def _collect_unresolved(self) -> list[str]:
        """收集所有未解决的问题"""
        unresolved = []
        for s in self._summaries:
            unresolved.extend(s.unresolved)
        # 也检查最近窗口中的失败
        for t in self._turns[-4:]:
            if not t.success and t.role == "assistant":
                unresolved.append(f"#{t.turn_id} {t.intent} 失败")
        return unresolved[-5:]  # 最多5个
