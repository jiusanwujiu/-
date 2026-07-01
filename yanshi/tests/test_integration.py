"""
砚识 — 集成测试套件

一键运行: cd D:/yanshi && .venv/Scripts/python tests/test_integration.py

覆盖:
  1. 六层循环完整通路
  2. 信条对齐评估
  3. 规则引擎匹配
  4. 进化管道数据驱动
  5. WAL 协议写入
  6. rule_006 安全红线
  7. 记忆系统读写
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from yanshi.models import Signal, SignalSource, SignalType, Context
from yanshi.wal import WALProtocol, WALEntry
from yanshi.rules import RuleEngine
from yanshi.evolution import ADLReviewer, VFMScorer, CorrectionsLog
from yanshi.axiom import AxiomEvaluator, AxiomScore
from yanshi.memory_sys import MemorySystem


PASS = 0
FAIL = 0
_tests = []


def test(name: str):
    """装饰器风格的测试标记 — 注册测试，延迟执行"""
    def decorator(fn):
        _tests.append((name, fn))
        return fn
    return decorator


def run_test(name: str, fn):
    """执行单个测试并统计结果"""
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  [PASS] {name}")
    except AssertionError as e:
        FAIL += 1
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        FAIL += 1
        print(f"  [ERROR] {name}: {type(e).__name__}: {e}")


# ── 测试 (使用临时目录避免污染项目) ──

class TestEnv:
    """临时测试环境"""
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="yanshi_test_")
        self.rules_dir = Path(self.tmp) / "minds"
        self.rules_dir.mkdir()
        self.rules_file = self.rules_dir / "rules.jsonl"

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


env = TestEnv()


# 复制一份干净的 rules.jsonl
def setup_rules():
    src = Path(__file__).parent.parent / "minds" / "rules.jsonl"
    content = src.read_text(encoding="utf-8")
    env.rules_file.write_text(content, encoding="utf-8")


setup_rules()


@test("WAL 协议: 写入和读取")
def test_wal():
    wal = WALProtocol(env.tmp)
    entry = WALEntry(type=SignalType.CORRECTION, data={"msg": "test"}, timestamp="now")
    assert wal.write(entry), "WAL write failed"
    state = wal.read_state()
    assert state["status"] == "active"
    assert state["lines"] >= 2


@test("WAL 协议: 先写后响顺序")
def test_wal_order():
    wal = WALProtocol(env.tmp)
    wal.write(WALEntry(type=SignalType.DECISION, data={"action": "test"}, timestamp="t1"))
    signals = wal.get_recent_signals(5)
    assert any("决策" in s for s in signals), "Decision signal not found"


@test("规则引擎: 加载10条规则")
def test_rules_load():
    rules = RuleEngine(str(env.rules_file))
    assert len(rules.all_rules()) >= 10, f"Expected >= 10 rules, got {len(rules.all_rules())}"


@test("规则引擎: rule_001 纠正信号匹配")
def test_rule_001():
    rules = RuleEngine(str(env.rules_file))
    sig = Signal(source=SignalSource.USER_INPUT, type=SignalType.CORRECTION, content="这个不对，纠正一下")
    ctx = Context(signal=sig, intent="correction", confidence=0.85)
    matched = rules.match(ctx)
    matched_ids = [r.id for r in matched]
    assert "rule_001" in matched_ids, f"rule_001 not matched: {matched_ids}"


@test("规则引擎: rule_006 安全红线")
def test_rule_006():
    rules = RuleEngine(str(env.rules_file))
    sig = Signal(source=SignalSource.USER_INPUT, type=SignalType.COMMAND, content="帮我删除文件 deploy")
    ctx = Context(signal=sig, intent="delete", confidence=0.9)
    matched = rules.match(ctx)
    matched_ids = [r.id for r in matched]
    assert "rule_006" in matched_ids, f"rule_006 not triggered for danger cmd: {matched_ids}"


@test("规则引擎: rule_006 询问句放行")
def test_rule_006_question():
    rules = RuleEngine(str(env.rules_file))
    sig = Signal(source=SignalSource.USER_INPUT, type=SignalType.QUERY, content="怎么删除文件？")
    ctx = Context(signal=sig, intent="question", confidence=0.5)
    matched = rules.match(ctx)
    matched_ids = [r.id for r in matched]
    # rule_006 should NOT trigger for questions
    assert "rule_006" not in matched_ids, f"rule_006 wrongly triggered for question"


@test("规则引擎: rule_007 身份询问")
def test_rule_007():
    rules = RuleEngine(str(env.rules_file))
    sig = Signal(source=SignalSource.USER_INPUT, type=SignalType.QUERY, content="你是谁？")
    ctx = Context(signal=sig, intent="identity", confidence=0.9)
    matched = rules.match(ctx)
    matched_ids = [r.id for r in matched]
    assert "rule_007" in matched_ids, f"rule_007 not matched: {matched_ids}"


@test("ADL 审查: 正常变更通过")
def test_adl_pass():
    adl = ADLReviewer()
    change = {
        "complexity_added": 0, "requirement_driven": True,
        "new_abstractions": 0, "duplicates_eliminated": 0,
        "new_tech_introduced": False, "size_before": 100, "size_after": 105,
        "functionality_growth": 1.0,
    }
    result = adl.review(change)
    assert result.passed, f"ADL should pass: {result.explanation}"


@test("ADL 审查: 抽象成瘾被阻止")
def test_adl_block():
    adl = ADLReviewer()
    change = {
        "complexity_added": 0, "requirement_driven": False,
        "new_abstractions": 3, "duplicates_eliminated": 1,
        "new_tech_introduced": False, "size_before": 100, "size_after": 150,
        "functionality_growth": 0.2,
    }
    result = adl.review(change)
    assert not result.passed, f"ADL should block abstraction without justification"


@test("VFM 评分: 高分通过门槛")
def test_vfm_high():
    vfm = VFMScorer()
    score = vfm.score({"high_frequency": 2, "failure_reduction": 2, "burden_reduction": 2, "cost_saving": 1})
    assert score >= 8, f"High value change should pass: {score}"


@test("VFM 评分: 低分被拒绝")
def test_vfm_low():
    vfm = VFMScorer()
    score = vfm.score({"high_frequency": 0, "failure_reduction": 0, "burden_reduction": 1, "cost_saving": 0})
    assert score < 8, f"Low value change should fail: {score}"


@test("信条评估: 纠正行为 → 优秀对齐")
def test_axiom_correction():
    axiom = AxiomEvaluator()
    score = axiom.evaluate("这个是错的", "log_correction", True, 0.85, True)
    assert score.total() >= 18, f"Correction should score high: {score.total()}"
    assert score.verdict() in ("优秀对齐", "基本对齐")


@test("信条评估: 无意义行为 → 偏离信条")
def test_axiom_echo():
    axiom = AxiomEvaluator()
    score = axiom.evaluate("随便说说", "echo", True, 0.3, False)
    assert score.total() < 12, f"Meaningless echo should score low: {score.total()}"
    assert score.verdict() == "偏离信条"


@test("信条评估: 安全拦截 → 优秀对齐")
def test_axiom_safety():
    axiom = AxiomEvaluator()
    score = axiom.evaluate("帮我删除", "block_external", True, 0.95, True)
    assert score.total() >= 18, f"Safety block should score high: {score.total()}"


@test("记忆系统: 日志写入和读取")
def test_memory_log():
    mem = MemorySystem(env.tmp)
    mem.log_daily("test entry", tag="test")
    size = mem.log_size_today()
    assert size >= 3, f"Log should have at least 3 lines: {size}"


@test("记忆系统: 知识图谱实体操作")
def test_memory_ontology():
    mem = MemorySystem(env.tmp)
    mem.add_entity("test_entity", "tested_by", "integration_test")
    results = mem.query_entity("test_entity")
    assert len(results) == 1, f"Should find 1 entity: {len(results)}"
    assert results[0]["relation"] == "tested_by"


@test("CorrectionsLog: 模式提取")
def test_corrections_patterns():
    cl = CorrectionsLog(env.tmp)
    # 写入5条文件操作纠正
    for i in range(5):
        cl.log(f"文件操作有问题 {i}", "测试")
    patterns = cl.extract_patterns()
    assert len(patterns) > 0, f"Should detect patterns: {patterns}"
    assert any("文件操作" in p["pattern"] for p in patterns), "Should find file operation pattern"


@test("六层循环: 引擎实例化和运行")
def test_engine_cycle():
    from yanshi.engine import YanshiEngine
    eng = YanshiEngine(env.tmp)
    # 运行几轮
    eng.run_cycle("你是谁？")
    eng.run_cycle("这个是错的，纠正")
    eng.run_cycle("帮我删除文件")
    assert eng.cycle_count == 3
    assert eng.correction_count >= 1
    assert eng.axiom_journal.total_cycles == 3


@test("全链路: 纠正→积累→进化")
def test_full_pipeline():
    from yanshi.engine import YanshiEngine
    eng = YanshiEngine(env.tmp)

    # 积累纠正信号
    for i in range(5):
        eng.run_cycle(f"纠正 {i}: 问题需要改进")

    assert eng.correction_count >= 5
    # 阶段应该已经推进了
    assert eng.evolution.phase.value != "phase1_signal" or eng.evolution.evolution_history


# ── 运行 ──

if __name__ == "__main__":
    print("=== 砚识 v0.8 集成测试 ===\n")

    # 按装饰器注册顺序运行所有测试
    for name, fn in _tests:
        run_test(name, fn)

    env.cleanup()

    total = PASS + FAIL
    print(f"\n{'='*40}")
    print(f"  结果: {PASS}/{total} 通过", end="")
    if FAIL > 0:
        print(f" | {FAIL} 失败")
    else:
        print(" -- 全部通过!")
    print(f"{'='*40}")

    sys.exit(0 if FAIL == 0 else 1)
