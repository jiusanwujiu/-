"""
砚识 v0.8 — Agent 间通信系统（维度语法协议）

语法: [主体] 激活 [维度组合] [用引导 "元词"] 任务：<描述>

主体:
  我            — 自我反思（消息发给自身）
  智能体:标识   — 指定 Agent
  任意          — 自动路由到具备对应维度的 Agent
  所有          — 广播给所有 Agent

维度组合: 能力维度的名称（如"文件操作"、"数学计算"），可用 + 连接多个

引导 "元词": 四大信条（求真/有用/自知/渐进）作为任务执行的引导原则

能力发现:
  任意 WITH 维度:开   — 查找所有启用该维度的 Agent
"""

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Any
from datetime import datetime, timezone


# ═══════════════ 维度系统 ═══════════════

class DimensionState(str, Enum):
    ENABLED = "开"      # 维度已激活，可响应外部请求
    INTERNAL = "内"     # 维度仅内部使用
    LEARNING = "学"     # 维度正在学习中
    DISABLED = "关"     # 维度已关闭


@dataclass
class Dimension:
    """
    能力维度 — Agent 能力的细粒度描述。

    每个维度包含语义示例（帮助其他 Agent 理解该维度的能力边界），
    以及可选的 inference_profile（推理能力画像）。
    """
    name: str                              # 维度名称（如 "文件操作"、"数学计算"）
    description: str = ""                  # 维度描述
    state: DimensionState = DimensionState.ENABLED  # 开/内/学/关
    semantic_examples: list[str] = field(default_factory=list)  # 语义示例
    keywords: list[str] = field(default_factory=list)  # 路由关键词
    inference_profile: dict = field(default_factory=dict)  # 推理能力画像（可选）

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "examples": self.semantic_examples[:3],
            "keywords": self.keywords[:5],
        }

    def is_enabled(self) -> bool:
        return self.state == DimensionState.ENABLED

    def matches_query(self, query: str) -> bool:
        """检查维度是否匹配查询（通过关键词或语义示例）"""
        q_lower = query.lower()
        if any(kw.lower() in q_lower for kw in self.keywords):
            return True
        if any(ex.lower() in q_lower for ex in self.semantic_examples):
            return True
        if self.name.lower() in q_lower:
            return True
        return False


# ═══════════════ 元词（引导原则）══════════════

class MetaWord(str, Enum):
    """四大信条作为任务执行的引导元词"""
    TRUTH = "求真"      # 追求事实准确性，避免推测
    USEFUL = "有用"     # 确保输出对用户有实际价值
    SELF_KNOW = "自知"  # 明确自身能力边界，不确定时不强答
    GRADUAL = "渐进"    # 分步骤推进，每一步验证后再继续

    @classmethod
    def from_str(cls, s: str) -> Optional["MetaWord"]:
        for mw in cls:
            if mw.value == s or mw.value in s:
                return mw
        return None

    def to_guidance(self) -> str:
        """将元词翻译为执行引导"""
        guidance = {
            MetaWord.TRUTH: "基于事实和证据，不确定时明确标注",
            MetaWord.USEFUL: "聚焦实际价值，避免冗余信息",
            MetaWord.SELF_KNOW: "诚实评估自身能力，超出边界时建议委托",
            MetaWord.GRADUAL: "分步推进，逐步验证，每步确认后再继续",
        }
        return guidance.get(self, "")


# ═══════════════ 消息协议 ═══════════════

class MessageType(str, Enum):
    QUERY = "query"
    DELEGATE = "delegate"
    KNOWLEDGE = "knowledge"
    CONSENSUS = "consensus"
    BROADCAST = "broadcast"


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ParsedDirective:
    """
    解析后的结构化指令。

    从语法 "[主体] 激活 [维度] [用引导 "元词"] 任务：<描述>" 解析而来。
    """
    subject_type: str = ""         # "self" / "agent" / "any" / "all"
    target_agent_id: str = ""      # 当 subject_type="agent" 时的目标ID
    dimensions: list[str] = field(default_factory=list)  # 请求的能力维度
    meta_words: list[MetaWord] = field(default_factory=list)  # 引导元词
    task: str = ""                 # 任务描述
    raw: str = ""                  # 原始文本

    def to_guidance_text(self) -> str:
        """将元词转为可执行的引导文本"""
        if not self.meta_words:
            return ""
        return " | ".join(mw.to_guidance() for mw in self.meta_words)

    def is_discovery(self) -> bool:
        """是否为能力发现请求（任意 WITH 维度:开）"""
        return self.subject_type == "any" and not self.task and self.dimensions


@dataclass
class AgentMessage:
    """Agent 间消息（兼容维度语法）"""
    id: str = ""
    msg_type: MessageType = MessageType.QUERY
    sender_id: str = ""
    target_id: str = ""
    content: str = ""
    data: Any = None
    parsed: ParsedDirective = None    # 解析后的结构化指令 (v0.7)
    priority: MessagePriority = MessagePriority.NORMAL
    requires_response: bool = True
    created_at: str = ""
    expires_at: str = ""
    reply_to: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).strftime("%H:%M:%S")

    @classmethod
    def from_directive(cls, directive: ParsedDirective, sender_id: str,
                       msg_type: MessageType = MessageType.QUERY) -> "AgentMessage":
        """从解析后的指令创建消息"""
        return cls(
            msg_type=msg_type,
            sender_id=sender_id,
            content=directive.task or directive.raw,
            parsed=directive,
            tags=directive.dimensions.copy(),
        )

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "type": self.msg_type.value,
            "sender": self.sender_id,
            "target": self.target_id,
            "content": self.content,
            "priority": self.priority.value,
            "requires_response": self.requires_response,
            "created_at": self.created_at,
            "tags": self.tags,
        }
        if self.parsed:
            d["directive"] = {
                "subject": self.parsed.subject_type,
                "dimensions": self.parsed.dimensions,
                "meta_words": [mw.value for mw in self.parsed.meta_words],
                "task": self.parsed.task,
                "guidance": self.parsed.to_guidance_text(),
            }
        return d


@dataclass
class AgentResponse:
    """Agent 回复消息"""
    id: str = ""
    in_reply_to: str = ""
    success: bool = False
    output: str = ""
    data: Any = None
    from_agent: str = ""
    confidence: float = 0.0
    duration_ms: float = 0.0
    meta_reflection: str = ""       # 元认知反思 (v0.7)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "reply_to": self.in_reply_to,
            "success": self.success,
            "output": self.output[:500],
            "from": self.from_agent,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
        }
        if self.meta_reflection:
            d["meta_reflection"] = self.meta_reflection
        return d


# ═══════════════ 指令解析器 ═══════════════

class DirectiveParser:
    """解析结构化语法: [主体] 激活 [维度] [用引导 "元词"] 任务：<描述>"""

    # 完整语法正则
    SYNTAX_RE = re.compile(
        r'(?:'
        r'(?P<subject>我|任意|所有|智能体:(?P<agent_id>\S+))'  # 主体
        r'\s*'
        r'(?P<activate>激活|请求|委托|通知)'                    # 动作词
        r'\s*'
        r'(?:(?P<dimensions>[\u4e00-\u9fff\w]+(?:\s*[+,，]\s*[\u4e00-\u9fff\w]+)*))?'  # 维度组合
        r'\s*'
        r'(?:用引导\s*["\u201c](?P<meta_word>[^"\u201d]+)["\u201d]\s*)?'  # 元词
        r'\s*'
        r'(?:任务[：:]\s*(?P<task>.+))?'                       # 任务
        r')',
        re.DOTALL,
    )

    # 能力发现语法: 任意 WITH 维度:开
    DISCOVERY_RE = re.compile(
        r'任意\s+WITH\s+(?P<dimension>[\u4e00-\u9fff\w]+)\s*:\s*开'
    )

    @classmethod
    def parse(cls, text: str) -> Optional[ParsedDirective]:
        """解析结构化指令，返回 ParsedDirective 或 None"""
        # 先尝试能力发现语法
        discovery = cls.DISCOVERY_RE.match(text.strip())
        if discovery:
            dim_name = discovery.group("dimension")
            return ParsedDirective(
                subject_type="any",
                dimensions=[dim_name],
                raw=text.strip(),
            )

        # 再尝试标准语法
        match = cls.SYNTAX_RE.match(text.strip())
        if not match:
            return None

        # 确定主体类型
        subject = match.group("subject")
        if subject == "我":
            subject_type = "self"
            agent_id = ""
        elif subject == "任意":
            subject_type = "any"
            agent_id = ""
        elif subject == "所有":
            subject_type = "all"
            agent_id = ""
        elif subject and subject.startswith("智能体:"):
            subject_type = "agent"
            agent_id = match.group("agent_id") or ""
        else:
            return None

        # 解析维度
        dims = []
        dims_str = match.group("dimensions") or ""
        if dims_str:
            dims = [d.strip() for d in re.split(r'[+,，]', dims_str) if d.strip()]

        # 解析元词
        meta_words = []
        mw_str = match.group("meta_word") or ""
        if mw_str:
            for mw_name in re.split(r'[,，\s]+', mw_str):
                mw = MetaWord.from_str(mw_name.strip())
                if mw:
                    meta_words.append(mw)

        # 解析任务
        task = (match.group("task") or "").strip()

        return ParsedDirective(
            subject_type=subject_type,
            target_agent_id=agent_id,
            dimensions=dims,
            meta_words=meta_words,
            task=task,
            raw=text.strip(),
        )


# ═══════════════ Agent 身份 ═══════════════

@dataclass
class AgentIdentity:
    """Agent 身份标识（v0.7: 维度替代能力）"""
    id: str
    name: str
    role: str = ""                           # executor / advisor / coordinator
    dimensions: list[Dimension] = field(default_factory=list)  # 能力维度列表
    knowledge_domains: list[str] = field(default_factory=list)
    endpoint: str = ""
    metacog_profile: dict = field(default_factory=dict)
    version: str = "0.7"
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "dimensions": [d.to_dict() for d in self.dimensions if d.is_enabled()],
            "knowledge_domains": self.knowledge_domains,
            "version": self.version,
            "metacog": self.metacog_profile,
        }

    # ── 维度查询（v0.7: 替代旧的 capabilities 方法）──

    def get_dimension(self, name: str) -> Optional[Dimension]:
        """获取指定名称的维度"""
        for d in self.dimensions:
            if d.name == name or d.name.lower() == name.lower():
                return d
        return None

    def has_dimension(self, name: str, require_enabled: bool = True) -> bool:
        """检查是否具备某个维度"""
        d = self.get_dimension(name)
        if d is None:
            return False
        return not require_enabled or d.is_enabled()

    def enabled_dimensions(self) -> list[Dimension]:
        """所有已启用的维度"""
        return [d for d in self.dimensions if d.is_enabled()]

    def match_dimensions(self, dim_names: list[str]) -> float:
        """
        计算维度匹配度（0.0-1.0）。
        用于 any 路由时选择最佳 Agent。
        """
        if not dim_names:
            return 0.0
        enabled = {d.name for d in self.enabled_dimensions()}
        hits = sum(1 for dn in dim_names if dn in enabled)
        return hits / len(dim_names) if dim_names else 0.0

    def matches_capability(self, capability: str) -> bool:
        """向后兼容: 检查是否有匹配的能力维度"""
        return self.has_dimension(capability)

    # ── 维度注册 ──

    def register_dimension(self, dim: Dimension):
        """注册（或更新）一个维度"""
        existing = self.get_dimension(dim.name)
        if existing:
            idx = self.dimensions.index(existing)
            self.dimensions[idx] = dim
        else:
            self.dimensions.append(dim)

    @classmethod
    def dimension_report(cls, agents: list["AgentIdentity"]) -> str:
        """生成所有 Agent 的维度注册报告"""
        lines = ["══ 维度注册表 ══", ""]
        for agent in agents:
            lines.append(f"  [{agent.id}] {agent.name}")
            for dim in agent.dimensions:
                lines.append(f"    {dim.name} [{dim.state.value}] — {dim.description}")
                if dim.semantic_examples:
                    lines.append(f"      示例: {', '.join(dim.semantic_examples[:2])}")
            lines.append("")
        return "\n".join(lines)


# ═══════════════ Agent 注册中心（v0.7: 维度感知）══════════════

class AgentRegistry:
    """Agent 注册中心 — 支持按维度发现 (v0.7)"""

    def __init__(self):
        self._agents: dict[str, AgentIdentity] = {}
        self._handlers: dict[str, Callable] = {}

    def register(self, identity: AgentIdentity, handler: Callable = None) -> bool:
        if identity.id in self._agents:
            return False
        self._agents[identity.id] = identity
        if handler:
            self._handlers[identity.id] = handler
        return True

    def unregister(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        self._agents.pop(agent_id, None)
        self._handlers.pop(agent_id, None)
        return True

    def get(self, agent_id: str) -> Optional[AgentIdentity]:
        return self._agents.get(agent_id)

    # ── 维度发现 (v0.7 新增) ──

    def find_by_dimension(self, dimension: str) -> list[AgentIdentity]:
        """查找所有启用指定维度的 Agent"""
        return [a for a in self._agents.values() if a.has_dimension(dimension)]

    def find_best_match(self, dimensions: list[str], exclude_id: str = "") -> Optional[AgentIdentity]:
        """在注册的所有 Agent 中找维度匹配度最高的"""
        best_agent = None
        best_score = 0.0
        for agent in self._agents.values():
            if agent.id == exclude_id:
                continue
            score = agent.match_dimensions(dimensions)
            if score > best_score:
                best_score = score
                best_agent = agent
        return best_agent if best_score > 0 else None

    def discovery_report(self, dimension: str) -> str:
        """生成维度发现报告（任意 WITH 维度:开）"""
        agents = self.find_by_dimension(dimension)
        if not agents:
            return f"─ 维度发现: 没有 Agent 注册了「{dimension}」维度"
        lines = [f"─ 维度发现: 「{dimension}」", f"  找到 {len(agents)} 个 Agent:", ""]
        for a in agents:
            dim = a.get_dimension(dimension)
            lines.append(f"  [{a.id}] {a.name}")
            if dim:
                lines.append(f"    描述: {dim.description}")
                if dim.inference_profile:
                    lines.append(f"    推理画像: {dim.inference_profile}")
                if dim.semantic_examples:
                    lines.append(f"    示例: {', '.join(dim.semantic_examples[:2])}")
            lines.append("")
        return "\n".join(lines)

    # ── 向后兼容方法 ──

    def find_by_capability(self, capability: str) -> list[AgentIdentity]:
        return self.find_by_dimension(capability)

    def find_by_domain(self, domain: str) -> list[AgentIdentity]:
        domain_lower = domain.lower()
        return [
            a for a in self._agents.values()
            if any(domain_lower in d.lower() for d in a.knowledge_domains)
        ]

    def find_by_role(self, role: str) -> list[AgentIdentity]:
        return [a for a in self._agents.values() if a.role == role]

    def list_all(self) -> list[dict]:
        return [a.to_dict() for a in self._agents.values()]

    def count(self) -> int:
        return len(self._agents)

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def __len__(self) -> int:
        return len(self._agents)


# ═══════════════ 通信总线（v0.7: 维度语法路由）══════════════

class CommunicationBus:
    """Agent 通信总线 — 支持维度语法路由 (v0.7)"""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._message_log: list[AgentMessage] = []
        self._response_log: list[AgentResponse] = []
        self._pending_consensus: dict[str, dict] = {}
        self._max_log = 500

    @property
    def message_count(self) -> int:
        return len(self._message_log)

    @property
    def response_count(self) -> int:
        return len(self._response_log)

    # ── 核心: 解析并路由 (v0.7) ──

    def parse_and_route(self, text: str, sender_id: str) -> AgentResponse:
        """
        解析结构化语法并自动路由。

        支持:
          我 激活 [维度] [用引导 "元词"] 任务：<描述>
          智能体:xxx 激活 [维度] 任务：<描述>
          任意 激活 [维度] 任务：<描述>
          所有 激活 [维度] 任务：<描述>
          任意 WITH 维度:开
        """
        directive = DirectiveParser.parse(text)

        # ── 能力发现 ──
        if directive and directive.is_discovery():
            report = self.registry.discovery_report(directive.dimensions[0])
            return AgentResponse(
                id=str(uuid.uuid4())[:8],
                in_reply_to="",
                success=True,
                output=report,
                from_agent="bus",
                data={"discovery": True, "dimension": directive.dimensions[0]},
            )

        # ── 未解析为结构化语法 → 回退到原始消息路由 ──
        if not directive:
            return AgentResponse(
                id=str(uuid.uuid4())[:8],
                in_reply_to="",
                success=False,
                output=f"无法解析指令: '{text[:50]}'。请使用语法: [主体] 激活 [维度] [用引导 \"元词\"] 任务：<描述>",
                from_agent="bus",
            )

        # ── 按主体类型路由 ──
        if directive.subject_type == "self":
            return self._route_to_self(directive, sender_id)
        elif directive.subject_type == "agent":
            return self._route_to_agent(directive, sender_id)
        elif directive.subject_type == "any":
            return self._route_any(directive, sender_id)
        elif directive.subject_type == "all":
            return self._route_all(directive, sender_id)
        else:
            return AgentResponse(
                id=str(uuid.uuid4())[:8],
                in_reply_to="",
                success=False,
                output=f"未知主体类型: {directive.subject_type}",
                from_agent="bus",
            )

    def _route_to_self(self, directive: ParsedDirective, sender_id: str) -> AgentResponse:
        """我 → 路由给自己"""
        if sender_id not in self.registry._handlers:
            return AgentResponse(success=False, output="自身未注册 handler", from_agent="bus")

        msg = AgentMessage.from_directive(directive, sender_id)
        msg.target_id = sender_id
        msg.tags.append("self-reflection")

        self._log_message(msg)
        try:
            handler = self.registry._handlers[sender_id]
            start = time.perf_counter()
            response = handler(msg)
            response.duration_ms = (time.perf_counter() - start) * 1000
            # 附上元词引导
            if directive.meta_words and response.meta_reflection:
                response.meta_reflection += f" | 元词引导: {directive.to_guidance_text()}"
            elif directive.meta_words:
                response.meta_reflection = directive.to_guidance_text()
            self._log_response(response)
            return response
        except Exception as e:
            resp = AgentResponse(success=False, output=f"自身处理失败: {e}", from_agent=sender_id)
            self._log_response(resp)
            return resp

    def _route_to_agent(self, directive: ParsedDirective, sender_id: str) -> AgentResponse:
        """智能体:xxx → 路由到指定 Agent"""
        target = directive.target_agent_id
        if target not in self.registry:
            return AgentResponse(success=False, output=f"Agent '{target}' 不存在", from_agent="bus")

        msg = AgentMessage.from_directive(directive, sender_id)
        msg.target_id = target
        return self.send(msg)

    def _route_any(self, directive: ParsedDirective, sender_id: str) -> AgentResponse:
        """任意 → 按维度自动选择最佳 Agent"""
        if not directive.dimensions:
            return AgentResponse(success=False, output="「任意」路由需要至少一个维度", from_agent="bus")

        # 按维度匹配度找最佳 Agent（优先其他 Agent，回退自己）
        best = self.registry.find_best_match(directive.dimensions, exclude_id=sender_id)
        if not best:
            # 没有其他 Agent → 检查自己是否满足维度
            self_identity = self.registry.get(sender_id)
            if self_identity and self_identity.match_dimensions(directive.dimensions) > 0:
                return self._route_to_self(directive, sender_id)
            dims_str = "+".join(directive.dimensions)
            return AgentResponse(
                success=False,
                output=f"没有 Agent 匹配维度: {dims_str}",
                from_agent="bus",
                data={"available_dimensions": self._all_dimensions()},
            )

        msg = AgentMessage.from_directive(directive, sender_id)
        msg.target_id = best.id
        msg.tags.append(f"auto-routed-by:{'+'.join(directive.dimensions)}")

        return self.send(msg)

    def _route_all(self, directive: ParsedDirective, sender_id: str) -> AgentResponse:
        """所有 → 广播给所有 Agent"""
        msg = AgentMessage.from_directive(directive, sender_id,
                                          msg_type=MessageType.BROADCAST)
        responses = self.broadcast(msg)

        success_count = sum(1 for r in responses if r.success)
        return AgentResponse(
            id=str(uuid.uuid4())[:8],
            in_reply_to="",
            success=success_count > 0,
            output=f"广播完成: {success_count}/{len(responses)} 个 Agent 成功响应",
            from_agent="bus",
            data={
                "total": len(responses),
                "successful": success_count,
                "responses": [r.to_dict() for r in responses[:5]],
            },
        )

    # ── 发送消息（向后兼容）──

    def send(self, msg: AgentMessage) -> Optional[AgentResponse]:
        self._log_message(msg)

        if msg.target_id and msg.target_id not in self.registry:
            return AgentResponse(
                in_reply_to=msg.id, success=False,
                output=f"Agent '{msg.target_id}' 不存在", from_agent="bus",
            )

        if msg.target_id in self.registry._handlers:
            handler = self.registry._handlers[msg.target_id]
            start = time.perf_counter()
            try:
                response = handler(msg)
                response.duration_ms = (time.perf_counter() - start) * 1000
                self._log_response(response)
                return response
            except Exception as e:
                resp = AgentResponse(
                    in_reply_to=msg.id, success=False,
                    output=f"处理失败: {e}", from_agent=msg.target_id,
                )
                self._log_response(resp)
                return resp
        return None

    def broadcast(self, msg: AgentMessage) -> list[AgentResponse]:
        self._log_message(msg)
        responses = []
        for agent_id in list(self.registry._agents.keys()):
            if agent_id == msg.sender_id:
                continue
            targeted = AgentMessage(
                msg_type=msg.msg_type, sender_id=msg.sender_id,
                target_id=agent_id, content=msg.content,
                data=msg.data, parsed=msg.parsed,
                priority=msg.priority, requires_response=msg.requires_response,
                tags=list(msg.tags), reply_to=msg.id,
            )
            response = self.send(targeted)
            if response:
                responses.append(response)
        return responses

    # ── 共识（向后兼容）──

    def propose_consensus(self, proposal: str, options: list[str],
                          proposer_id: str, timeout_seconds: float = 30) -> dict:
        proposal_id = str(uuid.uuid4())[:8]
        self._pending_consensus[proposal_id] = {
            "proposal": proposal, "options": options, "proposer": proposer_id,
            "votes": {}, "voters": set(),
            "timeout": time.time() + timeout_seconds, "status": "open",
        }
        broadcast_msg = AgentMessage(
            msg_type=MessageType.CONSENSUS, sender_id=proposer_id,
            content=proposal,
            data={"proposal_id": proposal_id, "options": options, "timeout": timeout_seconds},
            requires_response=True, tags=["consensus", proposal_id],
        )
        responses = self.broadcast(broadcast_msg)
        for resp in responses:
            if resp.success and resp.data and isinstance(resp.data, dict):
                vote = resp.data.get("vote", "弃权")
                if vote in options:
                    self._pending_consensus[proposal_id]["votes"][vote] = \
                        self._pending_consensus[proposal_id]["votes"].get(vote, 0) + 1
                    self._pending_consensus[proposal_id]["voters"].add(resp.from_agent)
        consensus = self._pending_consensus.pop(proposal_id, {})
        votes = consensus.get("votes", {})
        total_votes = sum(votes.values())
        total_agents = max(len(self.registry) - 1, 1)
        winner = max(votes, key=votes.get) if votes else "无"
        quorum = total_votes >= total_agents * 0.5
        return {
            "proposal_id": proposal_id, "winner": winner, "votes": votes,
            "total_votes": total_votes, "quorum": quorum,
            "voters": list(consensus.get("voters", [])),
        }

    # ── 向后兼容路由 ──

    def route_by_capability(self, capability: str, content: str, sender_id: str) -> Optional[AgentResponse]:
        candidates = self.registry.find_by_dimension(capability)
        if not candidates:
            return AgentResponse(success=False, output=f"没有 Agent 具备 '{capability}' 维度", from_agent="bus")
        target = candidates[0]
        msg = AgentMessage(msg_type=MessageType.QUERY, sender_id=sender_id,
                          target_id=target.id, content=content, tags=[capability])
        return self.send(msg)

    def route_by_domain(self, domain: str, content: str, sender_id: str) -> Optional[AgentResponse]:
        candidates = self.registry.find_by_domain(domain)
        if not candidates:
            return AgentResponse(success=False, output=f"没有 Agent 精通 '{domain}'", from_agent="bus")
        target = candidates[0]
        msg = AgentMessage(msg_type=MessageType.QUERY, sender_id=sender_id,
                          target_id=target.id, content=content, tags=[f"domain:{domain}"])
        return self.send(msg)

    # ── 统计 ──

    def stats(self) -> dict:
        msg_types = {}
        for m in self._message_log:
            t = m.msg_type.value
            msg_types[t] = msg_types.get(t, 0) + 1
        return {
            "agents_registered": len(self.registry),
            "messages_sent": len(self._message_log),
            "responses_received": len(self._response_log),
            "by_type": msg_types,
            "pending_consensus": len(self._pending_consensus),
        }

    # ── 内部 ──

    def _all_dimensions(self) -> list[str]:
        all_dims = set()
        for agent in self.registry._agents.values():
            for dim in agent.enabled_dimensions():
                all_dims.add(dim.name)
        return sorted(all_dims)

    def _log_message(self, msg: AgentMessage):
        self._message_log.append(msg)
        if len(self._message_log) > self._max_log:
            self._message_log = self._message_log[-self._max_log:]

    def _log_response(self, resp: AgentResponse):
        self._response_log.append(resp)
        if len(self._response_log) > self._max_log:
            self._response_log = self._response_log[-self._max_log:]
