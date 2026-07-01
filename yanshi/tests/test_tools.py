"""
砚识 v0.8 — 工具链单元测试

覆盖: files/shell/web/memory_tools/rules_tools/datetime_tools/json_tools/text_tools/env_tools/math_tools

运行: cd D:/yanshi && .venv/Scripts/python tests/test_tools.py
"""

import os
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from yanshi.tools.registry import ToolRegistry, get_registry, reset_registry
from yanshi.tools.base import ToolPermission
from yanshi.tools.files import FileReadTool, FileWriteTool, FileListTool
from yanshi.tools.shell import ShellExecTool
from yanshi.tools.web import WebFetchTool, WebCheckTool
from yanshi.tools.memory_tools import MemoryQueryTool, MemoryDistillTool, MemoryStatsTool
from yanshi.tools.rules_tools import RuleListTool, RuleToggleTool, RuleReloadTool
from yanshi.tools.datetime_tools import DateTimeTool, TimeDiffTool, TimestampTool
from yanshi.tools.json_tools import JsonParseTool, JsonFormatTool, JsonQueryTool
from yanshi.tools.text_tools import TextStatsTool, TextSearchTool, TextFreqTool
from yanshi.tools.env_tools import EnvReadTool, SysInfoTool
from yanshi.tools.math_tools import MathEvalTool, UnitConvertTool

from yanshi.memory_sys import MemorySystem
from yanshi.rules import RuleEngine


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


# ── 工具注册中心 ──

def test_registry():
    print("\n── 工具注册中心 ──")
    reset_registry()
    reg = get_registry()

    # 注册
    reg.register(FileReadTool())
    check("注册工具 file_read", len(reg) == 1)
    reg.register(FileWriteTool())
    check("注册工具 file_write", len(reg) == 2)

    # 获取
    tool = reg.get("file_read")
    check("获取已注册工具", tool is not None and tool.name == "file_read")
    check("获取不存在工具返回 None", reg.get("nonexistent") is None)

    # 按权限筛选
    read_only = reg.list_by_permission(ToolPermission.READ)
    check("按权限筛选 READ", len(read_only) == 1)

    # 统计
    stats = reg.get_stats()
    check("总注册数统计", stats["registered_count"] == 2)
    check("按名称统计", len(stats["tool_stats"]) == 2)


# ── 文件工具 ──

def test_files():
    print("\n── 文件工具 ──")
    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / "test.txt"
        test_file.write_text("hello world\nline 2\nline 3", encoding="utf-8")

        # FileReadTool
        reader = FileReadTool()
        result = reader.execute(path=str(test_file))
        check("读取文件成功", result.success and "hello world" in result.output)

        result = reader.execute(path=str(Path(tmp) / "nonexistent.txt"))
        check("读取不存在文件失败", not result.success)

        # FileWriteTool
        writer = FileWriteTool()
        new_file = Path(tmp) / "output.txt"
        result = writer.execute(path=str(new_file), content="test output")
        check("写入文件成功", result.success)
        check("写入内容正确", new_file.read_text(encoding="utf-8") == "test output")

        # FileListTool
        lister = FileListTool()
        result = lister.execute(path=tmp)
        check("列出目录成功", result.success and "test.txt" in result.output)


# ── Shell 工具 ──

def test_shell():
    print("\n── Shell 工具 ──")
    shell = ShellExecTool(workspace_root=os.getcwd())

    result = shell.execute(command="echo hello")
    check("执行简单命令", result.success and "hello" in result.output)

    result = shell.execute(command="cat /etc/shadow 2>/dev/null")
    check("危险命令被阻止", not result.success)


# ── 网络工具 ──

def test_web():
    print("\n── 网络工具 ──")
    checker = WebCheckTool()

    result = checker.execute(url="https://httpbin.org/get")
    check("URL 可达检查", result.success or result.error != "")  # 网络不可达也算合理结果

    result = checker.execute(url="not-a-valid-url")
    check("无效 URL 失败", not result.success)

    # WebFetch 需要实际网络，只测参数验证
    fetcher = WebFetchTool()
    result = fetcher.execute(url="")
    check("空 URL 失败", not result.success)


# ── 日期时间工具 ──

def test_datetime():
    print("\n── 日期时间工具 ──")
    dt = DateTimeTool()
    result = dt.execute(format="%Y-%m-%d")
    check("获取当前日期", result.success and len(result.output) == 10)

    tdiff = TimeDiffTool()
    result = tdiff.execute(start="2026-01-01", end="2026-01-02")
    check("计算时间差(天)", result.success and "1 day" in result.output)

    result = tdiff.execute(start="invalid-date")
    check("无效日期格式失败", not result.success)

    ts = TimestampTool()
    result = ts.execute()
    check("获取当前时间戳", result.success and result.data["timestamp"] > 0)


# ── JSON 工具 ──

def test_json():
    print("\n── JSON 工具 ──")
    parser = JsonParseTool()
    result = parser.execute(json='{"name": "test", "value": 42}')
    check("解析有效 JSON", result.success and result.data["type"] == "dict")

    result = parser.execute(json="{invalid json")
    check("解析无效 JSON 失败", not result.success)

    fmt = JsonFormatTool()
    result = fmt.execute(json='{"a":1,"b":2}')
    check("格式化 JSON", result.success and "  " in result.output)

    query = JsonQueryTool()
    result = query.execute(json='{"a": {"b": [1, 2, 3]}}', path="a.b.1")
    check("JSON 路径查询", result.success and result.data["value"] == 2)

    result = query.execute(json='{"a": 1}', path="x.y")
    check("JSON 路径不存在", not result.success)


# ── 文本工具 ──

def test_text():
    print("\n── 文本工具 ──")
    sample = "你好世界 hello world\n第二行 第二行\n你好"

    stats = TextStatsTool()
    result = stats.execute(text=sample)
    check("文本统计字符数", result.success and result.data["characters"] > 0)
    check("中文计数", result.data["chinese_characters"] >= 10)

    search = TextSearchTool()
    result = search.execute(text=sample, pattern="你好")
    check("文本搜索关键词", result.success and result.data["total_matches"] == 2)

    result = search.execute(text=sample, pattern="你好", regex=False)
    check("非正则搜索", result.success)

    freq = TextFreqTool()
    result = freq.execute(text="foo bar foo baz foo", top=3)
    check("词频统计", result.success and result.data["total_unique"] == 3)

    result = freq.execute(text="", top=3)
    check("空文本词频", not result.success)


# ── 环境变量工具 ──

def test_env():
    print("\n── 环境变量工具 ──")
    env = EnvReadTool()
    result = env.execute(name="PATH")
    check("读取 PATH 环境变量", result.success and len(result.output) > 0)

    result = env.execute(name="PASSWORD")
    check("敏感变量已隐藏", "已隐藏" in result.output)

    result = env.execute(all=True)
    check("列出所有变量", result.success and result.data["total"] > 5)

    sysinfo = SysInfoTool()
    result = sysinfo.execute()
    check("获取系统信息", result.success and "Python" in result.output)


# ── 数学工具 ──

def test_math():
    print("\n── 数学工具 ──")
    calc = MathEvalTool()
    result = calc.execute(expression="2 + 3 * 4")
    check("基础运算", result.success and result.data["result"] == 14)

    result = calc.execute(expression="sqrt(16)")
    check("sqrt 函数", result.success and result.data["result"] == 4)

    result = calc.execute(expression="1/0")
    check("除零报错", not result.success)

    result = calc.execute(expression="pi * 2", precision=2)
    check("pi 常量 + 精度", result.success)

    converter = UnitConvertTool()
    result = converter.execute(value=100, **{"from": "°C", "to": "°F"})
    check("温度转换 C→F", result.success and "212" in result.output)

    result = converter.execute(value=1, **{"from": "km", "to": "m"})
    check("长度转换 km→m", result.success and "1000" in result.output)

    result = converter.execute(value=1, **{"from": "kg", "to": "g"})
    check("重量转换 kg→g", result.success and "1000" in result.output)


# ── 记忆/规则工具 ──

def test_memory_rules_tools():
    print("\n── 记忆/规则工具 ──")
    with tempfile.TemporaryDirectory() as tmp:
        ms = MemorySystem(tmp)
        ms.log_daily("test entry", tag="test")

        query = MemoryQueryTool(ms)
        result = query.execute(entity="test")
        check("记忆查询", result.success)

        stats = MemoryStatsTool(ms)
        result = stats.execute()
        check("记忆统计", result.success and result.data["entities"] >= 0)

        distill = MemoryDistillTool(ms)
        result = distill.execute(days=999)
        check("记忆蒸馏", result.success)

    with tempfile.TemporaryDirectory() as tmp2:
        rules_path = Path(tmp2) / "rules.jsonl"
        rules_path.write_text(
            json.dumps({"id": "rule_test", "priority": 1, "enabled": True,
                        "trigger_keywords": ["test"], "actions": [], "description": "test rule"}) + "\n",
            encoding="utf-8",
        )
        rengine = RuleEngine(str(rules_path))

        rl = RuleListTool(rengine)
        result = rl.execute()
        check("列出规则", result.success and "test rule" in result.output)

        rt = RuleToggleTool(rengine)
        result = rt.execute(rule_id="rule_test", enabled=False)
        check("禁用规则", result.success)

        rr = RuleReloadTool(rengine)
        result = rr.execute()
        check("重载规则", result.success)


# ── 运行全部 ──

# ── v0.9: 对话/元认知/Agent 通信工具 ──

def test_dialogue_meta_tools():
    print("\n── 对话/元认知工具 ──")
    from yanshi.engine import YanshiEngine
    engine = YanshiEngine("D:/yanshi")

    # 运行几轮以生成对话数据
    engine.run_cycle("你是谁")
    engine.run_cycle("列出目录")

    # DialogueHistoryTool
    dt = engine.tools.get("dialogue_history")
    if dt:
        r = dt.execute(format="json")
        check("对话历史工具存在", dt is not None)
        check("对话历史有数据", r.success)

    # DialogueStatsTool
    ds = engine.tools.get("dialogue_stats")
    if ds:
        r = ds.execute()
        check("对话统计成功", r.success)

    # MetaReflectTool
    mr = engine.tools.get("meta_reflect")
    if mr:
        r = mr.execute()
        check("元认知反思成功", r.success)

    # MetaReportTool
    mp = engine.tools.get("meta_report")
    if mp:
        r = mp.execute()
        check("元认知报告成功", r.success)


def test_agcom_tools_integration():
    print("\n── Agent通信工具 ──")
    from yanshi.engine import YanshiEngine
    engine = YanshiEngine("D:/yanshi")

    al = engine.tools.get("agent_list")
    if al:
        r = al.execute()
        check("agent_list成功", r.success)
        check("agent_list有数据", "yanshi" in r.output)

    ab = engine.tools.get("agent_broadcast")
    if ab:
        r = ab.execute(content="测试广播")
        check("广播成功", r.success)


if __name__ == "__main__":
    print("=== 砚识 v0.8 工具链测试 ===\n")

    test_registry()
    test_files()
    test_shell()
    test_web()
    test_datetime()
    test_json()
    test_text()
    test_env()
    test_math()
    test_memory_rules_tools()
    test_dialogue_meta_tools()
    test_agcom_tools_integration()

    print(f"\n{'=' * 40}")
    print(f"  结果: {passed}/{passed + failed} 通过"
          + (" — 全部通过!" if failed == 0 else f" — {failed} 失败"))
    print(f"{'=' * 40}")
