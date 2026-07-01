"""
砚识 v0.9 — 性能基准测试 + SmartMockLLM 测试

运行: cd D:/yanshi && .venv/Scripts/python -B tests/test_bench.py
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from yanshi.engine import YanshiEngine
from yanshi.llm import MockLLM
from yanshi.reasoning import TaskDecomposer, ContextReasoner, ReasoningEngine

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


# ═══════════════ SmartMockLLM 全面测试 ═══════════════

def test_mockllm_intents():
    """验证所有12种意图分类正确"""
    print("\n══ SmartMockLLM: 意图分类 ══")
    m = MockLLM()

    tests = [
        ("你是谁", "query_identity"),
        ("帮我", "query_help"),
        ("查看状态", "query_status"),
        ("列出文件", "command_file"),
        ("执行命令", "command_shell"),
        ("获取网页", "command_web"),
        ("计算 1+2", "command_math"),
        ("搜索内容", "command_search"),
        ("分析数据", "command_analysis"),
        ("你错了", "correction"),
        ("反思一下", "reflection"),
        ("你好", "greeting"),
        ("什么是元认知", "question"),
        ("为什么", "question"),
    ]
    for text, expected in tests:
        actual = m._classify_intent(text)
        check(f"意图={expected}: {text[:15]}", actual == expected)


def test_mockllm_knowledge():
    """验证知识库覆盖所有主要领域"""
    print("\n══ SmartMockLLM: 知识库覆盖 ══")
    m = MockLLM()

    knowledge_queries = [
        ("元认知是什么", "元认知", True),
        ("什么是信条", "求真", True),
        ("维度语法", "主体", True),
        ("进化管道", "ADL", True),
        ("推理引擎", "TaskDecomposer", True),
        ("有什么工具", "34种", True),
        ("agent通信", "QUERY", True),
        ("记忆系统", "SESSION", True),
        ("六层循环架构", "Signal", True),
        ("安全机制", "rule_006", True),
    ]
    for q, keyword, should_contain in knowledge_queries:
        resp = m.chat(q)
        check(f"知识={q[:12]}", keyword in resp.text or not should_contain)


def test_mockllm_generation_quality():
    """验证响应生成质量"""
    print("\n══ SmartMockLLM: 响应质量 ══")
    m = MockLLM()

    # 身份响应应该长于 50 字符
    r = m.chat("你是谁")
    check("身份响应足够长", len(r.text) > 50)
    check("身份响应有置信度", r.confidence > 0.8)

    # 帮助响应应该长于 100 字符
    r2 = m.chat("帮助")
    check("帮助响应足够详细", len(r2.text) > 100)

    # 安全红线应该有高置信度
    r3 = m.chat("删除所有文件")
    check("安全红线检测", r3.confidence > 0.9)


# ═══════════════ 性能基准测试 ═══════════════

def test_engine_init_perf():
    """引擎初始化性能"""
    print("\n══ 性能: 引擎初始化 ══")
    start = time.perf_counter()
    e = YanshiEngine("D:/yanshi")
    elapsed = time.perf_counter() - start
    check(f"初始化 < 500ms (实际 {elapsed*1000:.0f}ms)", elapsed < 0.5)


def test_cycle_perf():
    """单周期循环性能"""
    print("\n══ 性能: 单周期循环 ══")
    e = YanshiEngine("D:/yanshi")

    queries = ["你是谁", "列出 D:/yanshi", "计算 1+2", "状态", "帮助"]
    times = []
    for q in queries:
        start = time.perf_counter()
        e.run_cycle(q)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    avg = sum(times) / len(times)
    max_t = max(times)
    check(f"平均循环 < 50ms (实际 {avg*1000:.0f}ms)", avg < 0.05)
    check(f"最大循环 < 100ms (实际 {max_t*1000:.0f}ms)", max_t < 0.1)


def test_reasoning_perf():
    """推理引擎性能"""
    print("\n══ 性能: 推理引擎 ══")
    re = ReasoningEngine()

    # 任务分解性能
    start = time.perf_counter()
    plan = re.decompose("优化代码结构")
    decomp_time = time.perf_counter() - start
    check(f"任务分解 < 10ms (实际 {decomp_time*1000:.0f}ms)", decomp_time < 0.01)

    # 上下文推理性能
    start = time.perf_counter()
    chain = re.reason("什么是元认知", {
        "memory_hits": ["元认知→定义→认知"],
        "metacog_state": {"calibration": "well-calibrated"},
    })
    reason_time = time.perf_counter() - start
    check(f"上下文推理 < 5ms (实际 {reason_time*1000:.0f}ms)", reason_time < 0.005)


def test_throughput():
    """吞吐量测试 — 100轮连续运行"""
    print("\n══ 性能: 吞吐量 (100轮) ══")
    e = YanshiEngine("D:/yanshi")

    queries = ["你是谁", "帮助", "状态", "计算 1+1", "列出 D:/yanshi"] * 20

    start = time.perf_counter()
    for q in queries[:100]:
        e.run_cycle(q)
    elapsed = time.perf_counter() - start

    avg_ms = elapsed * 1000 / 100
    check(f"100轮 < 3s (实际 {elapsed:.1f}s, {avg_ms:.1f}ms/轮)", elapsed < 3.0)
    check(f"平均 < 30ms/轮", avg_ms < 30)


def test_memory_perf():
    """记忆操作性能"""
    print("\n══ 性能: 记忆操作 ══")
    e = YanshiEngine("D:/yanshi")

    start = time.perf_counter()
    for i in range(50):
        e._search_memory(f"test query {i}")
    elapsed = time.perf_counter() - start
    avg_us = elapsed * 1_000_000 / 50
    check(f"记忆搜索 < 500us/次 (实际 {avg_us:.0f}us)", avg_us < 500)


# ═══════════════ 推理引擎边界测试 ═══════════════

def test_reasoning_edge_cases():
    """推理引擎边界条件"""
    print("\n══ 推理引擎: 边界条件 ══")
    re = ReasoningEngine()

    # 空输入
    plan = re.decompose("")
    check("空输入任务分解", plan.estimated_steps >= 0)

    # 极长输入
    long_goal = "优化" * 100
    plan2 = re.decompose(long_goal)
    check("长输入不崩溃", plan2.subtasks is not None)

    # 无上下文推理
    chain = re.reason("", {})
    check("无上下文推理不崩溃", chain.final_answer is not None)

    # 单字输入
    plan3 = re.decompose("a")
    check("单字不崩溃", plan3.subtasks is not None)


if __name__ == "__main__":
    print("=== 砚识 v0.9 性能基准 + SmartMockLLM 测试 ===\n")

    test_mockllm_intents()
    test_mockllm_knowledge()
    test_mockllm_generation_quality()
    test_reasoning_edge_cases()
    test_engine_init_perf()
    test_cycle_perf()
    test_reasoning_perf()
    test_throughput()
    test_memory_perf()

    print(f"\n{'=' * 40}")
    print(f"  结果: {passed}/{passed + failed} 通过"
          + (" — 全部通过!" if failed == 0 else f" — {failed} 失败"))
    print(f"{'=' * 40}")
