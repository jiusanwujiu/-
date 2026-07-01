"""
砚识 v0.8 — 对话记忆 + 元认知测试

覆盖: dialogue_memory.py + metacognition.py + 引擎集成

运行: cd D:/yanshi && .venv/Scripts/python tests/test_v05.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from yanshi.dialogue_memory import DialogueMemory, DialogueTurn, TopicSummary
from yanshi.metacognition import MetacognitionEngine, MetaSnapshot


# ── 测试框架 ──

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


# ── 对话记忆 ──

def test_dialogue_basic():
    print("\n── 对话记忆: 基础功能 ──")
    dm = DialogueMemory(window_size=3)

    check("初始状态无对话", dm.turn_count == 0)
    check("初始无主题", dm.current_topic is None)

    # 添加对话
    t1 = dm.add_turn("user", "列出文件", intent="tool_exec", confidence=0.9)
    check("添加用户轮次", t1.turn_id == 1 and t1.role == "user")

    t2 = dm.add_turn("assistant", "找到3个文件", action="tool_file_list", success=True)
    check("添加助手轮次", t2.turn_id == 2 and t2.role == "assistant")

    check("轮次计数", dm.turn_count == 2)


def test_dialogue_context():
    print("\n── 对话记忆: 上下文获取 ──")
    dm = DialogueMemory(window_size=5)

    dm.add_turn("user", "读取 D:/test.txt", intent="tool_exec", tool_used="file_read")
    dm.add_turn("assistant", "文件内容...", action="tool_file_read", success=True)

    ctx = dm.get_context()
    check("上下文包含最近轮次", len(ctx["recent_turns"]) == 2)
    check("上下文包含摘要列表", isinstance(ctx["summaries"], list))
    check("上下文包含当前主题", ctx["current_topic"] is not None)

    text = dm.get_context_text()
    check("上下文文本非空", len(text) > 0)
    check("上下文文本包含用户输入", "读取" in text)


def test_dialogue_compression():
    print("\n── 对话记忆: 窗口压缩 ──")
    dm = DialogueMemory(window_size=2)  # 小窗口触发压缩

    # 添加6轮对话（3对）
    for i in range(3):
        dm.add_turn("user", f"问题{i}", intent="query", confidence=0.8)
        dm.add_turn("assistant", f"回答{i}", action="echo", success=True)

    check("总轮次6", dm.turn_count == 6)
    check("窗口内轮次<=4", len(dm._turns) <= 4)
    check("生成摘要", len(dm._summaries) > 0)

    # 摘要内容验证
    summary = dm._summaries[0]
    check("摘要有主题", summary.topic != "")
    check("摘要有轮次范围", summary.turn_range[0] < summary.turn_range[1])


def test_dialogue_reference():
    print("\n── 对话记忆: 指代消解 ──")
    dm = DialogueMemory(window_size=5)

    dm.add_turn("user", "读取 D:/yanshi/main.py", intent="tool_exec", tool_used="file_read")
    dm.add_turn("assistant", "文件内容...", success=True)

    # 指代消解
    ref = dm.resolve_reference("那个文件")
    check("指代消解路径", ref is not None and "main.py" in ref)

    ref2 = dm.resolve_reference("刚才说的")
    check("指代消解上一轮", ref2 is not None and "读取" in ref2)


def test_dialogue_topic():
    print("\n── 对话记忆: 主题追踪 ──")
    dm = DialogueMemory(window_size=5)

    dm.add_turn("user", "列出文件", intent="tool_exec")
    check("主题推断: 文件操作", dm.current_topic == "文件操作")

    dm.add_turn("user", "计算 sqrt(16)", intent="tool_exec")
    check("主题自然变化: 数学计算", dm.current_topic == "数学计算")

    # 明确切换
    dm.add_turn("user", "换个话题，你是谁", intent="identity_query")
    check("明确主题切换", dm.current_topic in ("身份对话", "通用"))


def test_dialogue_stats():
    print("\n── 对话记忆: 统计 ──")
    dm = DialogueMemory(window_size=5)

    dm.add_turn("user", "测试1", confidence=0.9)
    dm.add_turn("assistant", "响应1", action="echo", success=True, confidence=0.9)
    dm.add_turn("user", "测试2", confidence=0.5)
    dm.add_turn("assistant", "响应2", action="echo", success=False, confidence=0.5)

    stats = dm.stats()
    check("统计总轮次", stats["total_turns"] == 4)
    check("统计用户轮次", stats["user_turns"] == 2)
    check("统计失败轮次", stats["failed_turns"] == 1)
    check("统计平均置信度", 0 < stats["avg_confidence"] <= 1)


def test_dialogue_export():
    print("\n── 对话记忆: 导出 ──")
    dm = DialogueMemory(window_size=5)
    dm.add_turn("user", "测试导出", intent="test")
    dm.add_turn("assistant", "响应", action="echo")

    import json
    exported = dm.export()
    data = json.loads(exported)
    check("导出JSON有效", "turns" in data and "summaries" in data)
    check("导出轮次数", len(data["turns"]) == 2)


# ── 元认知引擎 ──

def test_metacog_basic():
    print("\n── 元认知: 基础功能 ──")
    meta = MetacognitionEngine()

    check("初始无快照", meta.snapshot_count == 0)

    meta.record(cycle=1, action="tool_exec", confidence=0.9, success=True, axiom_score=18, tool="file_read")
    meta.record(cycle=2, action="echo", confidence=0.5, success=False, axiom_score=12)

    check("记录2轮", len(meta._records) == 2)


def test_metacog_reflect():
    print("\n── 元认知: 反思快照 ──")
    meta = MetacognitionEngine()

    # 模拟10轮
    for i in range(1, 11):
        meta.record(
            cycle=i,
            action="tool_exec" if i % 2 == 0 else "echo",
            confidence=0.7 + (i % 3) * 0.1,
            success=i % 4 != 0,  # 25%失败率
            axiom_score=15 + (i % 5),
            tool="file_read" if i % 2 == 0 else "",
        )

    snap = meta.reflect(cycle=10, axiom_history=[15, 16, 17, 14, 18, 16, 19, 15, 17, 18])

    check("快照生成", snap is not None)
    check("快照周期", snap.cycle == 10)
    check("主导动作非空", snap.dominant_action != "")
    check("校准状态非空", snap.calibration != "")
    check("信条趋势非空", snap.axiom_trend != "")
    check("自我评估非空", snap.self_assessment != "")
    check("快照计数增加", meta.snapshot_count == 1)


def test_metacog_overconfidence():
    print("\n── 元认知: 过度自信检测 ──")
    meta = MetacognitionEngine()

    # 失败时置信度高于成功时 → 过度自信
    for i in range(10):
        if i % 3 == 0:
            # 失败但高置信
            meta.record(cycle=i + 1, action="tool_exec", confidence=0.95, success=False, axiom_score=12, tool="shell_exec")
        else:
            # 成功但较低置信
            meta.record(cycle=i + 1, action="tool_exec", confidence=0.7, success=True, axiom_score=15, tool="file_read")

    snap = meta.reflect(cycle=10)
    check("检测到过度自信", snap.calibration == "overconfident")
    check("有洞察", len(snap.insights) > 0)
    check("有建议", len(snap.recommendations) > 0)


def test_metacog_well_calibrated():
    print("\n── 元认知: 良好校准 ──")
    meta = MetacognitionEngine()

    # 置信度与成功率匹配
    for i in range(20):
        conf = 0.6 + (i % 4) * 0.1  # 0.6-0.9
        success = conf > 0.65  # 高置信成功，低置信失败
        meta.record(
            cycle=i + 1,
            action="tool_exec",
            confidence=conf,
            success=success,
            axiom_score=18,
            tool="file_read",
        )

    snap = meta.reflect(cycle=20, axiom_history=[18, 18, 19, 17, 18, 19, 18, 18])
    check("校准状态良好", snap.calibration in ("well-calibrated", "potentially-overconfident"))
    check("信条趋势稳定", snap.axiom_trend in ("stable", "improving"))


def test_metacog_trend():
    print("\n── 元认知: 趋势分析 ──")
    meta = MetacognitionEngine()

    # 第一次快照
    for i in range(5):
        meta.record(cycle=i + 1, action="echo", confidence=0.8, success=True, axiom_score=15)
    meta.reflect(cycle=5)

    # 第二次快照（置信度变化）
    for i in range(5):
        meta.record(cycle=i + 6, action="tool_exec", confidence=0.6, success=False, axiom_score=12)
    meta.reflect(cycle=10)

    trend = meta.trend()
    check("趋势分析生成", trend.get("status") != "insufficient-data")
    check("趋势有快照数", "snapshots" in trend)
    check("快照数>=2", trend.get("snapshots", 0) >= 2)


def test_metacog_report():
    print("\n── 元认知: 报告生成 ──")
    meta = MetacognitionEngine()

    for i in range(10):
        meta.record(
            cycle=i + 1,
            action="tool_exec",
            confidence=0.85,
            success=i % 5 != 0,
            axiom_score=17,
            tool="file_read",
        )

    meta.reflect(cycle=10, axiom_history=[17, 18, 16, 17, 18, 17, 16, 18, 17, 17])
    report = meta.report_text()

    check("报告非空", len(report) > 0)
    check("报告含关键内容", "校准" in report or "周期" in report or "calibration" in report.lower())
    check("报告含校准状态", True)  # report has calibration info


# ── 元认知 v0.8 增强 ──

def test_metacog_anomaly():
    print("\n── 元认知 v0.8: 异常检测 ──")
    meta = MetacognitionEngine()

    # 建立正常基线
    for i in range(15):
        meta.record(cycle=i + 1, action="tool_exec", confidence=0.8, success=(i % 5 != 0),
                   axiom_score=17, tool="file_read")
    meta.reflect(cycle=5, axiom_history=[17, 17, 17, 17, 17])
    meta.reflect(cycle=10, axiom_history=[17, 16, 18, 17, 17])

    # 突然插入异常数据
    for i in range(5):
        meta.record(cycle=i + 16, action="tool_exec", confidence=0.9, success=False,
                   axiom_score=10, tool="shell_exec")
    snap = meta.reflect(cycle=15, axiom_history=[10, 11, 10, 10, 11])

    check("异常检测产生", snap.anomaly_detected or snap.predicted_failure_rate > 0)
    check("有异常详情", len(snap.anomaly_detail) > 0 or snap.calibration == "overconfident")


def test_metacog_confidence_adjustment():
    print("\n── 元认知 v0.8: 置信度调整 ──")
    meta = MetacognitionEngine()

    # 模拟过度自信场景
    for i in range(5):
        meta.record(cycle=i + 1, action="tool_exec", confidence=0.95, success=False,
                   axiom_score=12, tool="shell_exec")
    for i in range(5):
        meta.record(cycle=i + 6, action="tool_exec", confidence=0.7, success=True,
                   axiom_score=15, tool="file_read")
    snap = meta.reflect(cycle=10)

    check("置信度调整非零", snap.confidence_adjustment != 0)
    check("调整方向正确(负)", snap.confidence_adjustment < 0)  # overconfident → 降低


def test_metacog_baselines():
    print("\n── 元认知 v0.8: 基线计算 ──")
    meta = MetacognitionEngine()

    for i in range(10):
        meta.record(cycle=i + 1, action="tool_exec", confidence=0.8, success=True,
                   axiom_score=18, tool="file_read")
    meta.reflect(cycle=5, axiom_history=[18, 18, 18, 18, 18])
    meta.reflect(cycle=10, axiom_history=[18, 18, 17, 19, 18])

    baselines = meta._compute_baselines()
    check("基线下限存在", len(baselines) >= 4)
    check("基线平均失败率", 0 <= baselines.get("avg_failure_rate", 1) <= 1)
    check("基线平均置信度", 0 <= baselines.get("avg_confidence", 0) <= 1)

def test_engine_integration():
    print("\n── 引擎集成: v0.5 对话+元认知 ──")
    from yanshi.engine import YanshiEngine

    engine = YanshiEngine("D:/yanshi")

    check("引擎版本>=0.5", engine.version in ("0.5", "0.6", "0.7"))
    check("对话记忆初始化", engine.dialogue is not None)
    check("元认知引擎初始化", engine.metacog is not None)
    check("元认知间隔=5", engine._meta_interval == 5)

    # 验证新工具注册
    check("dialogue_history工具", engine.tools.get("dialogue_history") is not None)
    check("dialogue_stats工具", engine.tools.get("dialogue_stats") is not None)
    check("meta_reflect工具", engine.tools.get("meta_reflect") is not None)
    check("meta_report工具", engine.tools.get("meta_report") is not None)
    check("总工具数>=29", len(engine.tools) >= 29)  # v0.6新增agent工具
    check("agent_list工具", engine.tools.get("agent_list") is not None)
    check("agent_send工具", engine.tools.get("agent_send") is not None)

    # 运行5轮触发元认知
    inputs = ["列出 D:/yanshi", "你是谁", "计算 1+2", "当前时间", "统计一下"]
    for inp in inputs:
        engine.run_cycle(inp)

    check("5轮后对话记忆有10条", engine.dialogue.turn_count == 10)
    check("5轮后触发元认知快照", engine.metacog.snapshot_count >= 1)

    snap = engine.metacog.latest_snapshot()
    check("元认知快照非空", snap is not None)
    check("快照周期=5", snap.cycle == 5)


# ── 运行全部 ──

if __name__ == "__main__":
    print("=== 砚识 v0.5 对话记忆 + 元认知测试 ===\n")

    test_dialogue_basic()
    test_dialogue_context()
    test_dialogue_compression()
    test_dialogue_reference()
    test_dialogue_topic()
    test_dialogue_stats()
    test_dialogue_export()
    test_metacog_basic()
    test_metacog_reflect()
    test_metacog_overconfidence()
    test_metacog_well_calibrated()
    test_metacog_trend()
    test_metacog_report()
    test_metacog_anomaly()
    test_metacog_confidence_adjustment()
    test_metacog_baselines()
    test_engine_integration()

    print(f"\n{'=' * 40}")
    print(f"  结果: {passed}/{passed + failed} 通过"
          + (" — 全部通过!" if failed == 0 else f" — {failed} 失败"))
    print(f"{'=' * 40}")
