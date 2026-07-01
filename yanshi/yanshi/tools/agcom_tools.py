"""
砚识 v0.8 — Agent 通信工具

agent_list:       列出所有已注册的 Agent
agent_send:       向指定 Agent 发送消息
agent_delegate:   按能力/领域委托任务
agent_consensus:  发起共识投票
agent_broadcast:  广播消息给所有 Agent
"""

from .base import Tool, ToolResult, ToolPermission


class AgentListTool(Tool):
    """列出所有已注册的 Agent"""

    def __init__(self, registry):
        self.reg = registry
        super().__init__(
            name="agent_list",
            description="列出所有已注册的 Agent 及其能力",
            permission=ToolPermission.READ,
            parameters={
                "role": {"type": "string", "description": "按角色筛选 (executor/advisor/coordinator)，可选"},
            },
        )

    def execute(self, **params) -> ToolResult:
        role = params.get("role", "")
        if role:
            agents = self.reg.find_by_role(role)
        else:
            agents = self.reg.list_all()

        if not agents:
            return ToolResult(success=True, output="当前没有注册的 Agent", data={"agents": [], "total": 0})

        lines = [f"已注册 Agent: {len(agents)} 个", ""]
        for a in agents:
            aid = a.get("id", "unknown") if isinstance(a, dict) else a.id
            name = a.get("name", "unknown") if isinstance(a, dict) else a.name
            role_val = a.get("role", "") if isinstance(a, dict) else a.role
            caps = a.get("capabilities", []) if isinstance(a, dict) else a.capabilities
            caps_str = ", ".join(caps)
            lines.append(f"  [{aid}] {name}")
            lines.append(f"    角色: {role_val} | 能力: {caps_str}")

        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={"agents": agents, "total": len(agents)},
        )


class AgentSendTool(Tool):
    """向指定 Agent 发送消息"""

    def __init__(self, bus, self_id: str):
        self.bus = bus
        self.self_id = self_id
        super().__init__(
            name="agent_send",
            description="向指定 Agent 发送消息（查询/委托）",
            permission=ToolPermission.READ,
            parameters={
                "target": {"type": "string", "description": "目标 Agent ID"},
                "content": {"type": "string", "description": "消息内容"},
                "type": {"type": "string", "description": "消息类型: query/delegate/knowledge (默认 query)"},
            },
        )

    def execute(self, **params) -> ToolResult:
        target = params.get("target", "")
        content = params.get("content", "")
        msg_type_str = params.get("type", "query")

        if not target:
            return ToolResult(success=False, output="未指定目标 Agent", error="no target")

        msg_type_map = {"query": "query", "delegate": "delegate", "knowledge": "knowledge"}
        from ..agcom import AgentMessage, MessageType

        msg_type = MessageType(msg_type_map.get(msg_type_str, "query"))

        msg = AgentMessage(
            msg_type=msg_type,
            sender_id=self.self_id,
            target_id=target,
            content=content,
        )

        response = self.bus.send(msg)

        if response:
            status = "成功" if response.success else "失败"
            output = f"[{status}] 来自 {response.from_agent}: {response.output[:300]}"
            return ToolResult(
                success=response.success,
                output=output,
                data=response.to_dict(),
            )
        else:
            return ToolResult(success=False, output=f"Agent '{target}' 无响应", error="no response")


class AgentDelegateTool(Tool):
    """按能力委托任务"""

    def __init__(self, bus, self_id: str):
        self.bus = bus
        self.self_id = self_id
        super().__init__(
            name="agent_delegate",
            description="按能力或知识域自动委托任务给合适的 Agent",
            permission=ToolPermission.READ,
            parameters={
                "capability": {"type": "string", "description": "所需能力（如 file_ops, math, web）"},
                "domain": {"type": "string", "description": "知识领域（如 python, 金融），与 capability 二选一"},
                "content": {"type": "string", "description": "任务内容"},
            },
        )

    def execute(self, **params) -> ToolResult:
        capability = params.get("capability", "")
        domain = params.get("domain", "")
        content = params.get("content", "")

        if not content:
            return ToolResult(success=False, output="未提供任务内容", error="no content")

        if capability:
            response = self.bus.route_by_capability(capability, content, self.self_id)
        elif domain:
            response = self.bus.route_by_domain(domain, content, self.self_id)
        else:
            return ToolResult(success=False, output="未指定能力或领域", error="no capability/domain")

        if response:
            status = "成功" if response.success else "失败"
            return ToolResult(
                success=response.success,
                output=f"[委托{status}] {response.from_agent}: {response.output[:300]}",
                data=response.to_dict(),
            )
        else:
            return ToolResult(success=False, output="委托失败", error="no response")


class AgentConsensusTool(Tool):
    """发起共识投票"""

    def __init__(self, bus, self_id: str):
        self.bus = bus
        self.self_id = self_id
        super().__init__(
            name="agent_consensus",
            description="发起共识提案，收集所有 Agent 的投票",
            permission=ToolPermission.WRITE,
            parameters={
                "proposal": {"type": "string", "description": "提案内容"},
                "options": {"type": "string", "description": "选项列表，用逗号分隔（如: 支持,反对,弃权）"},
            },
        )

    def execute(self, **params) -> ToolResult:
        proposal = params.get("proposal", "")
        options_str = params.get("options", "支持,反对,弃权")

        if not proposal:
            return ToolResult(success=False, output="未提供提案", error="no proposal")

        options = [o.strip() for o in options_str.split(",") if o.strip()]

        result = self.bus.propose_consensus(proposal, options, self.self_id)

        lines = [
            f"共识提案: {proposal[:80]}",
            f"结果: {result['winner']}",
            f"投票: {result['votes']}",
            f"投票人数: {result['total_votes']}/{len(self.bus.registry) - 1}",
            f"法定人数: {'达到' if result['quorum'] else '未达到'}",
        ]

        return ToolResult(
            success=result["quorum"],
            output="\n".join(lines),
            data=result,
        )


class AgentBroadcastTool(Tool):
    """广播消息"""

    def __init__(self, bus, self_id: str):
        self.bus = bus
        self.self_id = self_id
        super().__init__(
            name="agent_broadcast",
            description="向所有 Agent 广播消息",
            permission=ToolPermission.READ,
            parameters={
                "content": {"type": "string", "description": "广播内容"},
            },
        )

    def execute(self, **params) -> ToolResult:
        content = params.get("content", "")
        if not content:
            return ToolResult(success=False, output="未提供广播内容", error="no content")

        from ..agcom import AgentMessage, MessageType
        msg = AgentMessage(
            msg_type=MessageType.BROADCAST,
            sender_id=self.self_id,
            content=content,
            requires_response=False,
        )

        responses = self.bus.broadcast(msg)

        return ToolResult(
            success=True,
            output=f"广播已发送给 {len(responses)} 个 Agent。响应: {len([r for r in responses if r.success])} 成功",
            data={"responses_received": len(responses), "successful": len([r for r in responses if r.success])},
        )
