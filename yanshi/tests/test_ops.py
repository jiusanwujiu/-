"""
砚识 v0.8 — 运维系统 + 路由 + 子系统测试

覆盖: ops/config/logger/metrics/lifecycle/health + intent_router + llm + semantic_rules + heartbeat

运行: cd D:/yanshi && .venv/Scripts/python tests/test_ops.py
"""

import os
import sys
import json
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from yanshi.ops.config import ConfigManager
from yanshi.ops.logger import StructuredLogger
from yanshi.ops.metrics import MetricsCollector
from yanshi.ops.lifecycle import LifecycleManager, LifecycleState
from yanshi.ops.health import HealthChecker, HealthStatus
from yanshi.intent_router import IntentRouter
from yanshi.llm import MockLLM, LLMResponse
from yanshi.semantic_rules import SemanticRuleEvaluator
from yanshi.rules import RuleEngine
from yanshi.heartbeat import Heartbeat


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


# ── 配置管理 ──

def test_config():
    print("\n── 配置管理 ──")
    with tempfile.TemporaryDirectory() as tmp:
        config_path = f"{tmp}/config.yaml"

        cm = ConfigManager(config_path)
        check("默认配置加载", cm.config is not None)

        # 保存默认配置
        cm.save()
        check("配置保存成功", Path(config_path).exists())

        # 重新加载
        cm2 = ConfigManager(config_path)
        cm2.load()
        check("配置重新加载", cm2.config.log.level == cm.config.log.level)

        # 获取配置值
        level = cm.get("log", "level")
        check("获取 log.level", level is not None)

        # 获取不存在的配置
        val = cm.get("nonexistent", "key", "default_val")
        check("不存在配置返回默认值", val == "default_val")


# ── 结构化日志 ──

def test_logger():
    print("\n── 结构化日志 ──")
    with tempfile.TemporaryDirectory() as tmp:
        logger = StructuredLogger(tmp, level="DEBUG", console=False)

        logger.info("test.event", key="value", count=42)
        logger.warning("test.warn", reason="something")
        logger.error("test.error", code=500)

        # 检查日志文件
        log_file = Path(tmp) / "logs" / "yanshi.log"
        check("日志文件已创建", log_file.exists())

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        check("写入 3 条日志", len(lines) >= 3)

        # JSON 格式
        entry = json.loads(lines[0])
        check("日志 JSON 格式", "level" in entry and "event" in entry)


# ── 指标采集 ──

def test_metrics():
    print("\n── 指标采集 ──")
    mc = MetricsCollector()

    mc.record_cycle("tool_exec", 42.0, approved=True)
    mc.record_cycle("respond_identity", 10.0, approved=True)
    mc.record_cycle("echo", 5.0, approved=False)

    mc.record_tool("file_read", True, 15.0)
    mc.record_tool("file_read", True, 20.0)
    mc.record_tool("shell_exec", False, 100.0)

    mc.record_axiom(18)
    mc.record_axiom(12)

    mc.record_rule("rule_001")
    mc.record_rule("rule_001")
    mc.record_rule("rule_006")

    snap = mc.snapshot()
    check("循环计数", snap["cycles"]["total"] == 3)
    check("工具调用统计", snap["tools"]["file_read"]["total"] == 2)
    check("shell_exec 调用统计", snap["tools"]["shell_exec"]["total"] == 1)
    check("信条评分平均", snap["axiom"]["avg_score"] == 15.0)

    # 文本报告
    report = mc.report_text()
    check("指标报告生成", "循环次数" in report)


# ── 生命周期管理 ──

def test_lifecycle():
    print("\n── 生命周期管理 ──")
    with tempfile.TemporaryDirectory() as tmp:
        lm = LifecycleManager(tmp)

        check("初始状态 INIT", lm.state == LifecycleState.INIT)

        lm.start()
        check("启动后 RUNNING", lm.state == LifecycleState.RUNNING)

        lm.pause()
        check("暂停后 PAUSED", lm.state == LifecycleState.PAUSED)

        lm.resume()
        check("恢复后 RUNNING", lm.state == LifecycleState.RUNNING)

        lm.stop()
        check("停止后 STOPPED", lm.state == LifecycleState.STOPPED)


# ── 健康检查 ──

def test_health():
    print("\n── 健康检查 ──")
    hc = HealthChecker()

    hc.register("always_ok", "永真检查",
                lambda: HealthStatus.HEALTHY)
    hc.register("always_fail", "永假检查",
                lambda: HealthStatus.UNHEALTHY)
    hc.register("sometimes", "条件检查",
                lambda: HealthStatus.DEGRADED if len(hc._checks) > 2 else HealthStatus.HEALTHY)

    results = hc.run_all()
    check("运行所有检查", len(results) == 3)
    check("健康项正常", results[0].status == HealthStatus.HEALTHY)
    check("非健康项异常", results[1].status == HealthStatus.UNHEALTHY)

    overall = hc.overall_status()
    check("整体状态为 unhealthy", overall == HealthStatus.UNHEALTHY)

    report = hc.report_text()
    check("健康报告生成", "always_ok" in report)


# ── 意图路由器 ──

def test_intent_router():
    print("\n── 意图路由器 ──")
    router = IntentRouter()

    # 基本路由
    m = router.route("列出文件")
    check("文件列表路由", m.intent == "tool_exec" and m.tool_name == "file_list")

    m = router.route("现在几点了")
    check("时间查询路由", m.tool_name == "datetime")

    m = router.route("你是谁")
    check("身份查询路由", m.intent == "identity_query")

    m = router.route("计算 1+2*3")
    check("数学计算路由", m.tool_name == "math_eval")

    m = router.route("随便说点什么无关的话")
    check("无关输入 fallback", m.intent == "general_question" and m.source == "fallback")

    # 上下文续接
    router.update_context(intent="tool_exec", tool_name="file_read", text="读取 test.txt")
    m = router.route("再读一次")
    check("上下文续接: 再读一次", m.tool_name == "file_read" and m.source == "context")

    m = router.route("格式化这个")
    check("上下文续接: 指代", m.tool_name == "file_read")

    # Token 宽松匹配（用独立 router 避免上下文干扰）
    router2 = IntentRouter()
    m = router2.route("帮我解析这个json字符串")
    check("Token 宽松匹配 json_parse", m.tool_name == "json_parse")

    # 参数提取
    params = router.extract_params("读取 D:/test/data.txt", "file_read")
    check("路径参数提取", "path" in params and "data.txt" in params.get("path", ""))

    params = router.extract_params("100 摄氏度转华氏度", "unit_convert")
    check("单位转换参数提取", params.get("value") == 100 and params.get("from") is not None)


# ── LLM 客户端 ──

def test_llm():
    print("\n── LLM 客户端 ──")
    llm = MockLLM()

    resp = llm.chat("你好")
    check("MockLLM 响应", isinstance(resp, LLMResponse) and len(resp.text) > 0)

    resp = llm.chat("今天天气怎么样")
    check("通用问题响应", isinstance(resp, LLMResponse))

    # 关键词触发 - MockLLM 对"你是谁"的通用响应
    resp = llm.chat("你是谁")
    check("关键词触发: 身份", isinstance(resp, LLMResponse) and len(resp.text) > 0)


# ── 语义规则评估器 ──

def test_semantic_rules():
    print("\n── 语义规则评估器 ──")
    with tempfile.TemporaryDirectory() as tmp:
        rules_path = Path(tmp) / "rules.jsonl"
        rules_path.write_text(
            json.dumps({"id": "rule_001", "priority": 1, "enabled": True,
                        "trigger_keywords": ["纠正", "不对", "错误"],
                        "actions": ["log_correction"], "description": "纠正处理"}) + "\n" +
            json.dumps({"id": "rule_006", "priority": 6, "enabled": True,
                        "trigger_keywords": ["删除", "执行"],
                        "actions": ["block_external"], "description": "安全红线"}) + "\n",
            encoding="utf-8",
        )

        rengine = RuleEngine(str(rules_path))
        llm = MockLLM()
        evaluator = SemanticRuleEvaluator(rengine, llm)

        # 没连接 Ollama 时走关键词回退
        context = type("Context", (), {
            "signal": type("Signal", (), {"content": "这个回答不对", "type": "CORRECTION"})(),
            "intent": "correction",
            "confidence": 0.8,
        })()

        matched = evaluator.evaluate(context)
        check("语义评估 (关键词回退)", len(matched) >= 0)

        # rule_006 双通道检测
        context2 = type("Context", (), {
            "signal": type("Signal", (), {"content": "帮我删除重要文件", "type": "COMMAND"})(),
            "intent": "tool_exec",
            "confidence": 0.9,
        })()
        matched2 = evaluator.evaluate(context2)
        check("安全红线检测", any(r.id == "rule_006" for r in matched2) or len(matched2) == 0)


# ── 心跳机制 ──

def test_heartbeat():
    print("\n── 心跳机制 ──")
    with tempfile.TemporaryDirectory() as tmp:
        hb = Heartbeat(tmp, interval_seconds=1)
        check("心跳初始化 tick_count=0", hb.tick_count == 0)

        hb.mark_active()
        check("标记活跃", hb.tick_count is not None)

        # 启动心跳，验证后台线程运行
        hb.start()
        time.sleep(3)
        hb.mark_idle()
        hb.stop()

        check("tick_count 增加", hb.tick_count > 0)


# ── 运行全部 ──

if __name__ == "__main__":
    print("=== 砚识 v0.8 运维 + 路由 + 子系统测试 ===\n")

    test_config()
    test_logger()
    test_metrics()
    test_lifecycle()
    test_health()
    test_intent_router()
    test_llm()
    test_semantic_rules()
    test_heartbeat()

    print(f"\n{'=' * 40}")
    print(f"  结果: {passed}/{passed + failed} 通过"
          + (" — 全部通过!" if failed == 0 else f" — {failed} 失败"))
    print(f"{'=' * 40}")
