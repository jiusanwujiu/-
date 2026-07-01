"""
砚识 v0.8 — Agent 通信系统测试（维度语法）

运行: cd D:/yanshi && .venv/Scripts/python tests/test_v06.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from yanshi.agcom import (
    AgentIdentity, AgentMessage, AgentResponse,
    AgentRegistry, CommunicationBus,
    MessageType, MessagePriority,
    Dimension, DimensionState, MetaWord,
    DirectiveParser, ParsedDirective,
)


passed = 0
failed = 0


def check(desc, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {desc}")
    else:
        failed += 1
        print(f"  [FAIL] {desc}")


# ── 维度系统 ──

def test_dimension():
    print("\n── 维度系统 ──")
    d = Dimension(name="文件操作", description="读写文件和目录",
                  state=DimensionState.ENABLED,
                  semantic_examples=["列出目录", "读取文件"],
                  keywords=["文件", "目录"])
    check("维度名称", d.name == "文件操作")
    check("维度启用", d.is_enabled())
    check("关键词匹配", d.matches_query("读取文件"))
    check("关键词不匹配", not d.matches_query("数学计算"))
    check("to_dict", d.to_dict()["name"] == "文件操作")


# ── 指令解析器 ──

def test_parser():
    print("\n── 指令解析器 ──")

    # 标准语法
    d = DirectiveParser.parse('智能体:advisor 激活 分析 用引导 "求真" 任务：评估架构风险')
    check("解析 agent 主体", d is not None and d.subject_type == "agent")
    check("解析 target_id", d.target_agent_id == "advisor")
    check("解析维度", "分析" in d.dimensions)
    check("解析元词", MetaWord.TRUTH in d.meta_words)
    check("解析任务", d.task == "评估架构风险")

    d2 = DirectiveParser.parse('任意 激活 文件操作+数学计算 任务：列出目录并计算')
    check("解析 any", d2.subject_type == "any")
    check("解析多维度", d2.dimensions == ["文件操作", "数学计算"])

    d3 = DirectiveParser.parse('我 激活 元认知 任务：反思')
    check("解析 self", d3.subject_type == "self")

    d4 = DirectiveParser.parse('所有 激活 知识共享 任务：共享发现')
    check("解析 all", d4.subject_type == "all")

    # 能力发现
    d5 = DirectiveParser.parse('任意 WITH 文件操作:开')
    check("解析发现", d5 is not None and d5.is_discovery())
    check("发现维度", d5.dimensions == ["文件操作"])

    # 非结构化文本
    d6 = DirectiveParser.parse('随便说点什么')
    check("非结构化解析失败", d6 is None)


# ── Agent 身份 ──

def test_identity():
    print("\n── Agent 身份 ──")
    ident = AgentIdentity(
        id="agent_alpha", name="Alpha", role="executor",
        dimensions=[
            Dimension(name="文件操作", state=DimensionState.ENABLED,
                      keywords=["file"]),
            Dimension(name="数学计算", state=DimensionState.ENABLED,
                      keywords=["math"]),
            Dimension(name="实验", state=DimensionState.LEARNING,
                      keywords=["experiment"]),
        ],
        knowledge_domains=["python"],
    )
    check("ID", ident.id == "agent_alpha")
    check("维度数", len(ident.dimensions) == 3)
    check("启用维度数", len(ident.enabled_dimensions()) == 2)
    check("has_dimension", ident.has_dimension("文件操作"))
    check("不启用维度", not ident.has_dimension("实验"))  # LEARNING state
    check("不存在维度", not ident.has_dimension("不存在"))
    check("维度匹配度", ident.match_dimensions(["文件操作", "数学计算"]) == 1.0)
    check("部分匹配", ident.match_dimensions(["文件操作", "不存在"]) == 0.5)
    check("向后兼容 matches_capability", ident.matches_capability("文件操作"))


# ── 注册中心: 维度发现 ──

def test_registry_dimensions():
    print("\n── 注册中心: 维度发现 ──")
    reg = AgentRegistry()
    reg.register(AgentIdentity(id="a1", name="A1",
        dimensions=[Dimension(name="文件操作", state=DimensionState.ENABLED, keywords=["file"])]))
    reg.register(AgentIdentity(id="a2", name="A2",
        dimensions=[Dimension(name="数学计算", state=DimensionState.ENABLED, keywords=["math"])]))
    reg.register(AgentIdentity(id="a3", name="A3",
        dimensions=[Dimension(name="文件操作", state=DimensionState.ENABLED, keywords=["file"]),
                   Dimension(name="分析", state=DimensionState.ENABLED, keywords=["analysis"])]))

    check("按维度发现 文件操作", len(reg.find_by_dimension("文件操作")) == 2)
    check("按维度发现 数学计算", len(reg.find_by_dimension("数学计算")) == 1)
    check("最佳匹配", reg.find_best_match(["文件操作", "分析"]).id == "a3")

    report = reg.discovery_report("文件操作")
    check("发现报告", "2 个 Agent" in report)


# ── 通信总线: parse_and_route ──

def test_bus_dimension_routing():
    print("\n── 通信总线: 维度路由 ──")
    reg = AgentRegistry()
    bus = CommunicationBus(reg)

    # 注册两个 agent
    def echo(msg): return AgentResponse(in_reply_to=msg.id, success=True, output=f"echo:{msg.content[:20]}", from_agent=msg.target_id)
    def math(msg): return AgentResponse(in_reply_to=msg.id, success=True, output="result:42", from_agent=msg.target_id)

    reg.register(AgentIdentity(id="echo1", name="Echo", dimensions=[Dimension(name="文件操作", state=DimensionState.ENABLED, keywords=["file"])]), echo)
    reg.register(AgentIdentity(id="math1", name="Math", dimensions=[Dimension(name="数学计算", state=DimensionState.ENABLED, keywords=["math"])]), math)

    # any 路由
    r = bus.parse_and_route('任意 激活 数学计算 任务：1+1?', "caller")
    check("any路由数学", r.success and "42" in r.output)

    r2 = bus.parse_and_route('任意 激活 文件操作 任务：列出目录', "caller")
    check("any路由文件", r2.success and "echo" in r2.output)

    # agent 指定路由
    r3 = bus.parse_and_route('智能体:echo1 激活 文件操作 任务：测试', "caller")
    check("指定agent路由", r3.success)

    # all 广播
    r4 = bus.parse_and_route('所有 激活 知识共享 任务：通知', "caller")
    check("all广播", r4.success)

    # 能力发现
    r5 = bus.parse_and_route('任意 WITH 文件操作:开', "caller")
    check("能力发现", r5.success and "echo1" in r5.output)


# ── 自我路由 ──

def test_self_routing():
    print("\n── 通信总线: 自我路由 ──")
    reg = AgentRegistry()
    bus = CommunicationBus(reg)

    def handler(msg):
        meta = msg.parsed.to_guidance_text() if msg.parsed and msg.parsed.meta_words else ""
        return AgentResponse(in_reply_to=msg.id, success=True,
                            output=f"反思完成: {msg.content[:30]}",
                            from_agent="self", meta_reflection=meta)

    reg.register(AgentIdentity(id="self", name="Self",
        dimensions=[Dimension(name="元认知", state=DimensionState.ENABLED, keywords=["meta"])]), handler)

    r = bus.parse_and_route('我 激活 元认知 用引导 "求真 渐进" 任务：反思今日决策', "self")
    check("自我路由", r.success and "反思完成" in r.output)
    check("元词引导", "基于事实" in (r.meta_reflection or "") or "分步" in (r.meta_reflection or ""))


# ── 向后兼容 ──

def test_backward_compat():
    print("\n── 向后兼容 ──")
    reg = AgentRegistry()
    bus = CommunicationBus(reg)

    def h(msg): return AgentResponse(in_reply_to=msg.id, success=True, output="ok", from_agent="x")
    reg.register(AgentIdentity(id="x", name="X",
        dimensions=[Dimension(name="测试", state=DimensionState.ENABLED, keywords=["test"])]), h)

    # 旧 API send
    msg = AgentMessage(msg_type=MessageType.QUERY, sender_id="caller", target_id="x", content="hello")
    r = bus.send(msg)
    check("旧API send", r is not None and r.success)

    # 旧 API route_by_capability
    r2 = bus.route_by_capability("测试", "query", "caller")
    check("旧API capability", r2.success)


# ── 引擎集成 ──

def test_engine_v07():
    print("\n── 引擎集成: v0.8 维度语法 ──")
    from yanshi.engine import YanshiEngine

    engine = YanshiEngine("D:/yanshi")

    identity = engine.agent_registry.get(engine.agent_id)
    check("引擎注册成功", identity is not None)
    check("维度已注册", len(identity.dimensions) > 10)

    # 维度发现
    for dim_name in ["文件操作", "数学计算", "文本处理", "元认知", "Agent通信"]:
        check(f"维度 {dim_name}", identity.has_dimension(dim_name))

    # parse_and_route 全部模式
    r1 = engine.agent_bus.parse_and_route('任意 WITH 文件操作:开', engine.agent_id)
    check("引擎发现", r1.success)

    r2 = engine.agent_bus.parse_and_route('任意 激活 文件操作 任务：列出 D:/yanshi', engine.agent_id)
    check("引擎any路由", r2 is not None)

    r3 = engine.agent_bus.parse_and_route('我 激活 元认知 用引导 "求真" 任务：反思', engine.agent_id)
    check("引擎自我路由", r3 is not None)

    # 验证工具列表
    for tn in ["agent_list", "agent_send", "agent_delegate", "agent_consensus", "agent_broadcast"]:
        check(f"工具 {tn}", engine.tools.get(tn) is not None)

    check("总工具", len(engine.tools) >= 29)


if __name__ == "__main__":
    print("=== 砚识 v0.8 Agent 通信系统测试 ===\n")

    test_dimension()
    test_parser()
    test_identity()
    test_registry_dimensions()
    test_bus_dimension_routing()
    test_self_routing()
    test_backward_compat()
    test_engine_v07()

    print(f"\n{'=' * 40}")
    print(f"  结果: {passed}/{passed + failed} 通过"
          + (" — 全部通过!" if failed == 0 else f" — {failed} 失败"))
    print(f"{'=' * 40}")
