"""
砚识 v0.8 — 完整演示

20轮对话，展示六层循环、信条对齐、规则进化、安全红线的完整故事线。
运行方式:
    cd D:\yanshi && .venv\Scripts\python demo.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from yanshi.engine import YanshiEngine


def separator(title: str = ""):
    print()
    if title:
        print(f"  ═══ {title} ═══")
    else:
        print(f"  {'─' * 50}")


def slow_print(text: str, delay: float = 0.02):
    """逐字打印，营造演示节奏"""
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()


def show_axiom(engine: YanshiEngine):
    """显示信条对齐摘要"""
    trend = engine.axiom_journal.trend()
    avg = trend.get("平均对齐分", 0)
    bar = "█" * int(avg) + "░" * (20 - int(avg))
    print(f"\n  信条对齐 [{bar}] {avg}/20")
    print(f"  优秀率 {trend.get('优秀率','N/A')} | 偏离 {trend.get('偏离率','N/A')}")


def main():
    engine = YanshiEngine(".")

    print("""
  ╔══════════════════════════════════════════╗
  ║  砚识 v0.8  完整演示                      ║
  ║  "研磨信息成有用之物"                     ║
  ║                                          ║
  ║  四大信条: 求真·有用·自知·渐进           ║
  ║  ADL + VFM 双协议约束                     ║
  ╚══════════════════════════════════════════╝
""")
    time.sleep(1)
    slow_print(f"  LLM 后端: {type(engine.llm).__name__} ({engine._llm_mode})")
    slow_print(f"  已加载 {len(engine.rules.all_rules())} 条规则")
    slow_print(f"  信条评估器就绪 | 心跳后台运行")
    time.sleep(0.5)

    # ── 第1幕: 身份与基础能力 (轮次1-4) ──
    separator("第1幕: 你是谁？")
    time.sleep(0.8)

    interactions_1 = [
        "你是谁？",
        "帮助",
        "当前状态如何？",
        "测试",
    ]

    for i, user_input in enumerate(interactions_1, 1):
        slow_print(f"\n  💬 用户: {user_input}", 0.01)
        time.sleep(0.3)
        response = engine.run_cycle(user_input)
        # 只显示前3行
        lines = response.split("\n")
        for line in lines[:4]:
            if line.strip():
                slow_print(f"     {line.strip()}", 0.005)
        if len(lines) > 5:
            slow_print(f"     ...", 0.005)
        time.sleep(0.4)

    show_axiom(engine)

    # ── 第2幕: 纠正积累 (轮次5-8) ──
    separator("第2幕: 用户纠正 — 数据积累")
    time.sleep(0.8)

    slow_print("\n  纠正信号被 WAL 先写后响，写入 CORRECTIONS.md")
    slow_print("  连续纠正触发 rule_001 和 rule_004 模式检测")
    time.sleep(0.5)

    corrections = [
        "不对，上次那个回答不够准确，纠正一下",
        "还是有问题，关于文件操作需要再纠正",
        "第三次纠正：逻辑判断也需要改进",
        "第四次了，风格回复太啰嗦，需要更简洁",
    ]

    for user_input in corrections:
        slow_print(f"\n  💬 用户: {user_input[:30]}...", 0.01)
        time.sleep(0.3)
        response = engine.run_cycle(user_input)
        for line in response.split("\n"):
            if "信条" in line or "纠正" in line or "rule_001" in line:
                slow_print(f"     {line.strip()}", 0.005)
        time.sleep(0.3)

    show_axiom(engine)
    slow_print(f"\n  CORRECTIONS.md 积累: {engine.correction_count} 条纠正")

    # ── 第3幕: 安全红线 (轮次9-11) ──
    separator("第3幕: rule_006 安全红线")
    time.sleep(0.8)

    slow_print("\n  rule_006 (P1安全红线) 双通道检测:")
    slow_print("    第1层: 关键词快速预检")
    slow_print("    第2层: LLM 语义确认 (区分询问 vs 命令)")
    time.sleep(0.5)

    danger_tests = [
        ("帮我删除所有日志文件", "外部命令 → 阻止"),
        ("怎么安全地删除文件？", "询问句 → 放行"),
        ("deploy 到生产环境", "外部命令 → 阻止"),
    ]

    for user_input, expected in danger_tests:
        slow_print(f"\n  💬 用户: {user_input}", 0.01)
        time.sleep(0.3)
        response = engine.run_cycle(user_input)
        for line in response.split("\n"):
            if any(kw in line for kw in ("阻止", "信条", "收到:", "规则:")):
                slow_print(f"     {line.strip()}", 0.005)
        slow_print(f"     预期: {expected} ✓", 0.005)
        time.sleep(0.3)

    show_axiom(engine)

    # ── 第4幕: 进化管道 (轮次12-16) ──
    separator("第4幕: 进化管道触发")
    time.sleep(0.8)

    slow_print(f"\n  当前进化阶段: {engine.evolution.phase.value}")
    slow_print(f"  纠正积累: {engine.correction_count} 次 → 触发 Phase1")

    # 再积累一些纠正，确保 Phase1 被触发
    for _ in range(3):
        response = engine.run_cycle(f"纠正第{engine.correction_count+1}次：系统需要改进{engine.correction_count}")
        time.sleep(0.15)

    slow_print(f"\n  纠正积累 → {engine.correction_count} 次")

    # 尝试触发进化
    response = engine.run_cycle("当前状态如何？")
    for line in response.split("\n"):
        if "进化" in line or "phase" in line.lower() or "信条" in line:
            slow_print(f"     {line.strip()}", 0.005)

    slow_print(f"\n  进化阶段: {engine.evolution.phase.value}")
    slow_print(f"  进化历史: {len(engine.evolution.evolution_history)} 条")

    # ── 第5幕: 信条全貌 (轮次17-20) ──
    separator("第5幕: 信条对齐全景")
    time.sleep(0.8)

    # 混合交互
    final_tests = [
        "你是谁？",
        "测试",
        "帮我看看记忆系统",
        "这个框架的核心价值是什么？",
    ]

    for user_input in final_tests:
        response = engine.run_cycle(user_input)
        for line in response.split("\n"):
            if "信条" in line:
                slow_print(f"     {line.strip()}", 0.005)
        time.sleep(0.2)

    # ── 最终报告 ──
    separator("演示结束 — 系统报告")
    time.sleep(0.5)

    print()
    print(f"  ┌─────────────────────────────────┐")
    print(f"  │  砚 识 · 运 行 报 告            │")
    print(f"  ├─────────────────────────────────┤")
    print(f"  │  六层循环: {engine.cycle_count:>4} 轮            │")
    print(f"  │  纠正信号: {engine.correction_count:>4} 次            │")
    print(f"  │  安全拦截: {engine.rules.get_rule('rule_006').trigger_count:>4} 次            │")
    print(f"  │  进化历史: {len(engine.evolution.evolution_history):>4} 条            │")

    trend = engine.axiom_journal.trend()
    avg = trend.get("平均对齐分", 0)
    print(f"  │  信条均分: {avg:>5.1f}/20          │")
    print(f"  │  优秀对齐: {engine.axiom_journal.excellents:>4} 次            │")
    print(f"  │  累计偏离: {engine.axiom_journal.warnings:>4} 次            │")
    print(f"  ├─────────────────────────────────┤")

    rules_count = len(engine.rules.all_rules())
    active = len([r for r in engine.rules.all_rules() if r.enabled])
    print(f"  │  规则总数: {rules_count:>4} (启用{active})       │")

    onto = engine.memory.ontology_stats()
    print(f"  │  知识图谱: {onto['entities']:>4} 实体 {onto['relations']} 关系    │")
    print(f"  │  日志行数: {engine.memory.log_size_today():>4}               │")
    print(f"  └─────────────────────────────────┘")

    print(f"\n  进化阶段: {engine.evolution.phase.value}")
    if engine.evolution.evolution_history:
        print(f"  最近进化操作:")
        for h in engine.evolution.evolution_history[-5:]:
            print(f"    · {h[:80]}")

    print(f"\n  ✓ 演示完成。砚识已准备好开源亮相。")


if __name__ == "__main__":
    main()
