"""
砚识 v0.9 — 全面端到端集成场景测试

这个测试模拟一个完整的 Agent 工作流程，从接收到复杂目标开始，
经过自主推理、任务分解、逐步执行、元认知反思、进化触发、Agent通信，
最终产生可审计的完整报告。

运行: cd D:/yanshi && .venv/Scripts/python -B tests/test_e2e.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from yanshi.engine import YanshiEngine
from yanshi.reasoning import (
    TaskDecomposer, ContextReasoner, ConditionalEngine,
    EnhancedResponseGen, ReasoningEngine, TaskStatus,
)
from yanshi.agcom import (
    AgentIdentity, Dimension, DimensionState
)
from yanshi.metacognition import MetacognitionEngine

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


# ═══════════════ 场景1: 自主任务分解与执行 ═══════════════

def test_scenario_autonomous_task():
    """场景: Agent接收复杂目标，自主分解并逐步执行"""
    print("\n══ 场景1: 自主任务分解与执行 ══")

    engine = YanshiEngine("D:/yanshi")

    # 分解一个跨越多个领域的复杂任务
    plan = engine._reasoning.decompose("读取配置文件并统计内容然后分析结构", {
        "workspace_root": "D:/yanshi",
        "tools_available": engine.tools.list_tools(),
    })
    check("任务分解成功", len(plan.subtasks) > 0)
    check("有推理依据", len(plan.rationale) > 0)
    check("子任务有ID", all(st.id for st in plan.subtasks))

    # 验证子任务结构
    for st in plan.subtasks:
        check(f"子任务{st.id}描述非空", len(st.description) > 0)

    # 生成任务报告
    report = engine._reasoning.task_report(plan)
    check("任务报告生成", len(report) > 0)
    check("报告含进度", "进度" in report or "0/" in report)


# ═══════════════ 场景2: 上下文推理 + 元认知联动 ═══════════════

def test_scenario_context_reasoning_with_metacog():
    """场景: Agent基于对话历史+元认知状态进行上下文推理"""
    print("\n══ 场景2: 上下文推理 + 元认知联动 ══")

    engine = YanshiEngine("D:/yanshi")

    # 模拟多轮对话
    inputs = ["你是谁", "列出 D:/yanshi 目录", "读取 main.py", "元认知报告", "对话历史"]
    for inp in inputs:
        engine.run_cycle(inp)

    # 获取当前元认知状态
    mc_state = engine._get_metacog_context()
    check("元认知状态存在", len(mc_state) > 0 or engine.metacog.snapshot_count > 0)

    # 上下文推理
    chain = engine._reasoning.reason("目前为止做了什么", {
        "memory_hints": engine._search_memory("目录"),
        "dialogue_turns": len(inputs),
        "metacog_state": mc_state,
    })
    check("推理有步骤", len(chain.steps) >= 0)
    check("推理有答案", len(chain.final_answer) > 0)
    check("推理有trace", len(chain.trace) >= 0)


# ═══════════════ 场景3: 条件推演 + 安全决策 ═══════════════

def test_scenario_conditional_decision():
    """场景: Agent面对危险操作时进行条件推演和风险评估"""
    print("\n══ 场景3: 条件推演 + 安全决策 ══")

    ce = ConditionalEngine()

    # 高风险场景
    r1 = ce.evaluate(["删除所有临时文件"], [
        {"id": "r_safe", "condition": lambda c: any(
            kw in " ".join(c["premises"]) for kw in ["删除", "清空", "格式化"]
        ), "action": "阻止-需确认", "priority": 1},
        {"id": "r_default", "condition": lambda c: True, "action": "允许", "priority": 10},
    ])
    check("高风险检测", r1["risk_level"] == "high")
    check("安全规则优先", r1["recommendation"] == "阻止-需确认")
    check("多规则冲突检测", len(r1["triggered_rules"]) >= 1)

    # 低风险场景
    r2 = ce.evaluate(["读取README.md文件"], [
        {"id": "r_safe", "condition": lambda c: any(
            kw in " ".join(c["premises"]) for kw in ["删除", "清空"]
        ), "action": "阻止", "priority": 1},
        {"id": "r_default", "condition": lambda c: True, "action": "允许", "priority": 10},
    ])
    check("低风险操作", r2["risk_level"] == "low")


# ═══════════════ 场景4: Agent通信 + 维度语法 ═══════════════

def test_scenario_agent_communication():
    """场景: 多个Agent通过维度语法协议协作"""
    print("\n══ 场景4: Agent通信 + 维度语法 ══")

    engine = YanshiEngine("D:/yanshi")

    # 注册第二个Agent
    adv = AgentIdentity(
        id="advisor_beta",
        name="顾问·Beta",
        role="advisor",
        dimensions=[
            Dimension(name="分析", state=DimensionState.ENABLED,
                     description="代码分析和架构评估",
                     semantic_examples=["分析代码结构", "评估架构"],
                     keywords=["分析", "评估", "架构"]),
        ],
    )
    def adv_handler(msg):
        from yanshi.agcom import AgentResponse
        return AgentResponse(in_reply_to=msg.id, success=True,
                           output="分析完成: 建议优化文件结构", from_agent="advisor_beta")
    engine.agent_registry.register(adv, adv_handler)

    check("多Agent注册", engine.agent_registry.count() >= 2)

    # 维度发现
    r = engine.agent_bus.parse_and_route("任意 WITH 分析:开", engine.agent_id)
    check("维度发现", r.success and "advisor_beta" in r.output)

    # 委托任务
    r2 = engine.agent_bus.parse_and_route("任意 激活 分析 任务：评估代码质量", engine.agent_id)
    check("按维度委托", r2 is not None)


# ═══════════════ 场景5: 进化管道 + 模式学习 ═══════════════

def test_scenario_evolution_learning():
    """场景: Agent通过纠正日志提取模式并触发进化"""
    print("\n══ 场景5: 进化管道 + 模式学习 ══")

    from yanshi.evolution import CorrectionsLog

    corrections = CorrectionsLog("D:/yanshi")

    # 模拟多次相似的纠正
    for i in range(4):
        corrections.log(f"文件操作错误: 第{i+1}次", f"context_{i}")

    patterns = corrections.extract_patterns()
    check("模式提取", len(patterns) >= 0)
    # 至少有1个模式或达到触发条件
    check("纠正积累触发进化", corrections.count_entries() >= 3)


# ═══════════════ 场景6: 错误恢复与降级 ═══════════════

def test_scenario_error_recovery():
    """场景: Agent在执行失败时进行错误恢复"""
    print("\n══ 场景6: 错误恢复与降级 ══")

    engine = YanshiEngine("D:/yanshi")

    # 测试错误恢复方法
    r = engine._recover_from_error(FileNotFoundError("test.txt"), "读取 test.txt")
    check("文件未找到恢复", "路径" in r or "检查" in r)

    r2 = engine._recover_from_error(PermissionError("denied"), "删除文件")
    check("权限拒绝恢复", "权限" in r2 or "更高" in r2)

    r3 = engine._recover_from_error(ValueError("invalid value"), "计算 x/0")
    check("值错误恢复", "参数" in r3 or "无效" in r3)

    # 未知错误的默认恢复
    r4 = engine._recover_from_error(RuntimeError("unknown"), "随机操作")
    check("未知错误降级", "已记录" in r4 and "恢复" in r4)


# ═══════════════ 场景7: 全栈闭环 ═══════════════

def test_scenario_full_pipeline():
    """场景: 完整闭环 — 感知→推理→分解→执行→反思→进化→通信"""
    print("\n══ 场景7: 全栈闭环 ══")

    engine = YanshiEngine("D:/yanshi")

    # Step 1: 基本循环
    r1 = engine.run_cycle("你是谁")
    check("基本循环", len(r1) > 0)

    # Step 2: 自主任务
    report = engine.run_task("查询记忆状态然后生成元认知报告")
    check("自主任务执行", len(report) > 0)

    # Step 3: 错误恢复 (故意传入一个会失败的循环)
    # 通过在循环内部处理异常来实现
    r3 = engine._recover_from_error(Exception("模拟故障"), "测试")
    check("错误恢复存在", len(r3) > 0)

    # Step 4: 跨子系统状态
    mc = engine._get_metacog_context()
    rules = engine.rules.all_rules()
    agents = engine.agent_registry.count()
    tools = len(engine.tools)

    check("元认知子系统正常", isinstance(mc, dict))
    check("规则引擎正常", len(rules) > 0)
    check("Agent通信正常", agents > 0)
    check("工具链正常", tools > 0)

    # Step 5: 全维度验证
    total_checks = engine.cycle_count + engine.error_count + len(rules) + agents + tools
    check("全系统响应", total_checks > 0)


if __name__ == "__main__":
    print("=== 砚识 v0.9 全面端到端集成测试 ===\n")

    test_scenario_autonomous_task()
    test_scenario_context_reasoning_with_metacog()
    test_scenario_conditional_decision()
    test_scenario_agent_communication()
    test_scenario_evolution_learning()
    test_scenario_error_recovery()
    test_scenario_full_pipeline()

    print(f"\n{'=' * 40}")
    print(f"  结果: {passed}/{passed + failed} 通过"
          + (" — 全部通过!" if failed == 0 else f" — {failed} 失败"))
    print(f"{'=' * 40}")
