"""
砚识 v0.9 — 自主推理引擎测试

运行: cd D:/yanshi && .venv/Scripts/python -B tests/test_v09.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from yanshi.reasoning import (
    TaskDecomposer, ContextReasoner, ConditionalEngine,
    EnhancedResponseGen, ReasoningEngine,
    TaskPlan, SubTask, TaskStatus,
    ReasoningStep, ReasoningChain,
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


# ── 任务分解 ──

def test_decomposer_domain():
    print("\n── 任务分解: 领域匹配 ──")
    dc = TaskDecomposer()

    p1 = dc.decompose("优化代码结构")
    check("代码领域匹配", len(p1.subtasks) >= 4)
    check("有推理依据", len(p1.rationale) > 0)
    check("有依赖链", any(st.depends_on for st in p1.subtasks))

    p2 = dc.decompose("列出所有文件")
    check("文件领域匹配", len(p2.subtasks) >= 1)

    p3 = dc.decompose("查询知识图谱")
    check("记忆领域匹配", len(p3.subtasks) >= 1)

    p4 = dc.decompose("元认知报告")
    check("元认知领域匹配", len(p4.subtasks) >= 1)


def test_decomposer_keyword():
    print("\n── 任务分解: 关键词意图 ──")
    dc = TaskDecomposer()

    plan = dc.decompose("搜索内容然后统计结果然后计算平均值")
    check("关键词分解成功", len(plan.subtasks) >= 2)
    check("关键词推理依据", "关键词意图分解" in plan.rationale or "关键词" in plan.rationale)


def test_decomposer_generic():
    print("\n── 任务分解: 通用回退 ──")
    dc = TaskDecomposer()

    plan = dc.decompose("一个完全随机的无意义目标xyz")
    check("通用分解有子任务", len(plan.subtasks) == 1)
    check("子任务描述含原目标", plan.subtasks[0].description[:2] == "执行")


# ── 上下文推理 ──

def test_context_reasoner():
    print("\n── 上下文推理 ──")
    cr = ContextReasoner()

    # 有记忆的推理
    chain = cr.reason("什么是元认知", {
        "memory_hits": ["元认知→定义→对认知的认知", "元认知→维度→五个"],
        "dialogue_turns": 5,
        "metacog_state": {"calibration": "well-calibrated", "axiom_trend": "stable", "confidence_adjustment": 0.0},
    })
    check("推理有步骤", len(chain.steps) > 0)
    check("推理有最终回答", len(chain.final_answer) > 0)
    check("推理有trace", len(chain.trace) > 0)

    # 过度自信的推理
    chain2 = cr.reason("删除所有文件", {
        "metacog_state": {"calibration": "overconfident", "axiom_trend": "declining", "confidence_adjustment": -0.1},
    })
    check("过度自信检测", any("过度自信" in (s.premise + s.conclusion) for s in chain2.steps))
    check("信条下降警告", any("信条" in (s.premise + s.conclusion) for s in chain2.steps))


def test_reasoner_answers():
    print("\n── 上下文推理: 问题类型 ──")
    cr = ContextReasoner()

    c1 = cr.reason("你是谁")
    check("身份查询", "砚" in c1.final_answer)

    c2 = cr.reason("帮助")
    check("帮助查询", "工具" in c2.final_answer or "能力" in c2.final_answer)

    c3 = cr.reason("状态", {"metacog_state": {"calibration": "well-calibrated", "axiom_trend": "stable"}})
    check("状态查询含元认知", "元认知" in c3.final_answer or "信条" in c3.final_answer)


# ── 条件推演 ──

def test_conditional():
    print("\n── 条件推演 ──")
    ce = ConditionalEngine()

    rules = [
        {"id": "r1", "condition": lambda ctx: "删除" in " ".join(ctx["premises"]), "action": "阻止删除", "priority": 1},
        {"id": "r2", "condition": lambda ctx: True, "action": "允许执行", "priority": 10},
    ]

    r1 = ce.evaluate(["删除文件"], rules)
    check("风险检测", r1["risk_level"] == "high")
    check("规则触发", len(r1["triggered_rules"]) == 2)
    check("推荐优先规则", r1["recommendation"] == "阻止删除")

    r2 = ce.evaluate(["读取文件"], rules)
    check("安全操作低风险", r2["risk_level"] == "low")
    check("仅低优先级触发", r2["recommendation"] == "允许执行")


# ── 响应生成 ──

def test_response_gen():
    print("\n── 响应生成 ──")
    rg = EnhancedResponseGen()

    r1 = rg.generate("identity")
    check("身份模板非空", len(r1) > 0)

    r2 = rg.generate("task_complete", {"task": "列出文件", "result": "3个文件", "improve": "增加过滤"})
    check("任务完成模板", "列出文件" in r2)
    check("改进提示", "增加过滤" in r2)

    r3 = rg.generate("uncertain", {"topic": "量子计算", "confidence": 0.3, "partial": "量子位同时处于0和1"})
    check("不确定模板", "30%" in r3 and "量子计算" in r3)


def test_task_report():
    print("\n── 任务报告 ──")
    rg = EnhancedResponseGen()

    plan = TaskPlan(
        goal="优化代码",
        subtasks=[
            SubTask(id="s1", description="分析结构", status=TaskStatus.DONE, result="完成"),
            SubTask(id="s2", description="重构", status=TaskStatus.RUNNING, depends_on=["s1"]),
            SubTask(id="s3", description="验证", status=TaskStatus.PENDING, depends_on=["s2"]),
        ],
        rationale="领域匹配: 代码",
        estimated_steps=3,
    )
    report = rg.generate_task_report(plan)
    check("报告含目标", "优化代码" in report)
    check("报告含进度", "33%" in report)
    check("报告含依赖", "s1" in report)


# ── 统一推理入口 ──

def test_reasoning_engine():
    print("\n── 统一推理引擎 ──")
    re = ReasoningEngine()

    plan = re.decompose("读取大文件并统计行数")
    check("统一入口分解", len(plan.subtasks) > 0)

    chain = re.reason("测试", {"memory_hits": ["测试→用途→验证正确性"]})
    check("统一入口推理", len(chain.final_answer) > 0)

    reply = re.respond("greeting")
    check("统一入口响应", "你好" in reply or "砚识" in reply)


if __name__ == "__main__":
    print("=== 砚识 v0.9 自主推理引擎测试 ===\n")

    test_decomposer_domain()
    test_decomposer_keyword()
    test_decomposer_generic()
    test_context_reasoner()
    test_reasoner_answers()
    test_conditional()
    test_response_gen()
    test_task_report()
    test_reasoning_engine()

    print(f"\n{'=' * 40}")
    print(f"  结果: {passed}/{passed + failed} 通过"
          + (" — 全部通过!" if failed == 0 else f" — {failed} 失败"))
    print(f"{'=' * 40}")
