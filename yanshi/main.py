"""
砚识 v0.9 — 交互式入口 (增强版)

启动六层循环引擎，进入增强 CLI 交互模式。
支持命令前缀 / 和多种运行模式。

用法:
  python main.py                    # 标准交互模式
  python main.py --demo             # 全功能演示
  python main.py --task "目标"      # 单次自主任务
"""

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from yanshi.engine import YanshiEngine
from yanshi.llm import MockLLM

BANNER = r"""
  ╔══════════════════════════════════════╗
  ║     砚 识   ·   Y a n s h i         ║
  ║     {version}   信条引领 求真有用    ║
  ║     "研磨信息成有用之物"            ║
  ║                                     ║
  ║  感知→理解→决策→执行→反思→进化      ║
  ║  受 ADL + VFM 双协议约束            ║
  ║  {llm_label}
  ╚══════════════════════════════════════╝

  输入 /help 查看命令  |  /quit 退出
"""

HELP_TEXT = """
  ═══ 砚识 v0.9 交互命令 ═══

  对话模式:
    直接输入任何问题或任务 — Agent 自主处理

  斜杠命令:
    /task <目标>     — 自主任务分解与执行
    /meta            — 查看元认知状态报告
    /status          — 查看系统状态
    /tools           — 列出可用工具
    /rules           — 列出所有规则
    /agent           — 查看 Agent 通信状态
    /memory          — 查看记忆系统状态
    /stats           — 查看运行统计
    /test            — 运行自检测试
    /demo            — 运行全功能演示
    /help            — 显示此帮助
    /quit            — 退出

  示例:
    > 你是谁
    > 列出 D:/yanshi 目录
    > /task 优化项目代码结构
    > /meta
"""


def show_banner(engine: YanshiEngine):
    llm_type = type(engine.llm).__name__
    llm_label = f"AI模式 ({llm_type})"
    if isinstance(engine.llm, MockLLM):
        llm_label = "AI模式 (内置智能推理)"
    print(BANNER.format(version=f"v{engine.version}", llm_label=llm_label))


def run_demo(engine: YanshiEngine):
    """全功能演示 — 展示所有子系统"""
    demo_steps = [
        ("身份查询", "你是谁"),
        ("系统帮助", "/help"),
        ("文件操作", "列出 D:/yanshi 目录结构"),
        ("元认知报告", "/meta"),
        ("运行状态", "/status"),
        ("规则列表", "/rules"),
        ("Agent状态", "/agent"),
        ("自主任务", "/task 查询记忆状态并生成元认知报告"),
        ("工具列表", "/tools"),
        ("统计信息", "/stats"),
    ]

    print("\n  ═══ 砚识 v0.9 全功能演示 ═══\n")
    for label, cmd in demo_steps:
        print(f"  [{label}] {cmd}")
        print("  " + "─" * 50)
        start = time.perf_counter()
        if cmd.startswith("/task "):
            response = engine.run_task(cmd[6:])
        elif cmd.startswith("/"):
            response = engine.run_cycle(f"/{cmd[1:]}")
        else:
            response = engine.run_cycle(cmd)
        elapsed = time.perf_counter() - start
        # 缩进显示响应
        for line in response.split("\n")[:8]:
            print(f"  {line}")
        print(f"  [{elapsed*1000:.0f}ms]\n")


def interactive_loop(engine: YanshiEngine):
    """交互式对话循环"""
    while True:
        try:
            user_input = input("\n砚识 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  正在退出...")
            break

        if not user_input:
            continue

        # 斜杠命令
        if user_input.startswith("/"):
            parts = user_input[1:].split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ("quit", "exit", "q"):
                print("  砚识引擎已停止。")
                break
            elif cmd == "help":
                print(HELP_TEXT)
            elif cmd == "task" and arg:
                start = time.perf_counter()
                response = engine.run_task(arg)
                elapsed = time.perf_counter() - start
                print(f"\n{response}")
                print(f"\n  [自主任务 {elapsed*1000:.0f}ms]")
            elif cmd == "meta":
                response = engine.run_cycle("查看元认知状态")
                print(f"\n{response}")
            elif cmd == "status":
                response = engine.run_cycle("查看系统状态")
                print(f"\n{response}")
            elif cmd == "tools":
                response = engine.run_cycle("列出工具")
                print(f"\n{response}")
            elif cmd == "rules":
                rules = engine.rules.all_rules()
                enabled = [r.id for r in rules if r.enabled]
                disabled = [r.id for r in rules if not r.enabled]
                print(f"\n  规则总数: {len(rules)}")
                print(f"  已启用: {', '.join(enabled)}")
                if disabled:
                    print(f"  已禁用: {', '.join(disabled)}")
            elif cmd == "agent":
                agents = engine.agent_registry.list_all()
                print(f"\n  注册 Agent: {len(agents)} 个")
                for a in agents:
                    dims = [d["name"] for d in a.get("dimensions", [])]
                    print(f"    [{a['id']}] {a['name']} — 维度: {', '.join(dims[:4])}")
            elif cmd == "memory":
                stats = engine.memory.stats()
                print(f"\n  记忆系统状态:")
                for k, v in stats.items():
                    print(f"    {k}: {v}")
            elif cmd == "stats":
                print(f"\n  总循环: {engine.cycle_count}")
                print(f"  错误数: {engine.error_count}")
                print(f"  纠正数: {engine.correction_count}")
                print(f"  通信消息: {engine.agent_bus.message_count}")
            elif cmd == "test":
                response = engine.run_cycle("运行自检")
                print(f"\n{response}")
            elif cmd == "demo":
                run_demo(engine)
            else:
                print(f"  未知命令: /{cmd} (输入 /help 查看命令列表)")
        else:
            # 普通对话
            start = time.perf_counter()
            response = engine.run_cycle(user_input)
            elapsed = time.perf_counter() - start
            print(f"\n{response}")
            print(f"  [{engine.cycle_count}轮 | {elapsed*1000:.0f}ms]")


def main():
    args = sys.argv[1:]

    # 工作空间初始化
    workspace = str(PROJECT_ROOT)
    for fname in ["HEARTBEAT.md"]:
        path = Path(workspace) / fname
        if not path.exists():
            path.write_text(f"# {fname}\n", encoding="utf-8")

    # 初始化引擎
    engine = YanshiEngine(workspace)
    engine.heartbeat.start()

    show_banner(engine)
    print(f"  规则: {len(engine.rules.all_rules())} 条 | 工具: {len(engine.tools)} 个 | 维度: {len(engine.agent_registry.get(engine.agent_id).dimensions)} 个")
    print("─" * 50)

    if "--demo" in args:
        run_demo(engine)
        return

    if "--task" in args:
        idx = args.index("--task")
        if idx + 1 < len(args):
            goal = args[idx + 1]
            print(f"\n  自主任务: {goal}")
            print(engine.run_task(goal))
        return

    interactive_loop(engine)


if __name__ == "__main__":
    main()
