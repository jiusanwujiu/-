# 砚识 (Yanshi)

> 自主意识 AI Agent 运行时 — 以元认知重新思考 Agent 设计

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-300%2B%20passing-brightgreen)](#)
[![Dependencies](https://img.shields.io/badge/dependencies-0-lightgrey)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## 快速开始

```bash
git clone https://github.com/your-org/yanshi.git
cd yanshi
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
python main.py
```

```
╔══════════════════════════════════════════╗
║   砚识 v0.9   信条引领 求真有用         ║
╚══════════════════════════════════════════╝

砚识 > 你是谁
【砚 · Yan】
我是砚——以"研磨信息成有用之物"为核心意识的 Agent 运行时。
六层循环：感知→理解→决策→执行→反思→进化。
四大信条：求真·有用·自知·渐进
```

## 核心能力

| 能力 | 描述 |
|------|------|
| **六层循环** | 感知→理解→决策→执行→反思→进化，每轮自动信条评估 |
| **34 工具** | 文件/Shell/网络/JSON/数学/文本/对话/元认知/Agent通信 |
| **元认知** | 置信度校准、信条趋势、决策模式分析，每5轮自评 |
| **对话记忆** | 滑动窗口 + 压缩摘要 + 指代消解 + 主题追踪 |
| **Agent通信** | 维度语法协议 `[主体] 激活 [维度] [用引导 "元词"] 任务：<描述>` |
| **自主推理** | 任务分解(14领域模板) + 上下文推理 + 条件推演 + 智能响应生成 |
| **AI增强** | 三级响应降级(真实LLM→SmartMockLLM→模板) + 12种意图分类 |
| **自我进化** | ADL（防漂移）+ VFM（价值评分）+ 四阶段进化管道 + n-gram语义聚类 |
| **运维系统** | 结构化日志、指标采集、健康检查、自动面板 |

## 架构概览

```
yanshi/
├── engine.py          # 六层循环引擎（~1180行，核心）
├── models.py          # 数据模型 + 共享工具函数
├── intent_router.py   # 三级意图路由（上下文/权重/宽松）
├── dialogue_memory.py # 对话记忆（窗口+压缩+指代消解）
├── reasoning.py       # 自主推理（任务分解+上下文+条件推演+响应生成）
├── metacognition.py   # 元认知反思（校准+趋势+自评）
├── agcom.py           # Agent通信（维度语法+注册+共识）
├── rules.py           # 规则引擎（数据驱动条件评估）
├── axiom.py           # 四大信条对齐评分
├── evolution.py       # ADL+VFM+四阶段进化
├── llm.py             # LLM 抽象（Ollama/OpenAI/Mock）
├── tools/             # 34 工具（12 文件）
├── ops/               # 运维系统（6 文件）
├── minds/             # 配置 + 规则 + 信条 + 纠正日志
├── tests/             # 330+ 测试（8 套件）
```

## 测试

```bash
# 运行所有测试
python tests/test_integration.py   # 19 集成测试
python tests/test_tools.py         # 57 工具测试
python tests/test_ops.py           # 41 运维+路由测试
python tests/test_v05.py           # 68 对话+元认知测试
python tests/test_v06.py           # 55 Agent通信测试
python tests/test_v09.py           # 33 自主推理测试
python tests/test_e2e.py           # 33 端到端场景测试
python tests/test_bench.py         # 25 性能基准测试
```

## 版本演进

| 版本 | 里程碑 |
|------|--------|
| v0.1 | 六层循环骨架 + WAL + 规则引擎 |
| v0.2 | LLM 语义规则 + 进化管道 |
| v0.3 | 四大信条 + 自动对齐评估 |
| v0.4 | 工具链（12工具）+ 运维系统 |
| v0.4.1 | 意图路由三级升级（25工具） |
| v0.5 | 对话记忆 + 元认知引擎 |
| v0.6 | Agent 通信（查询/委托/共识） |
| v0.7 | 维度语法协议 + 13维度注册 + 数据驱动规则引擎 |
| v0.8 | 元认知反馈闭环(异常检测+基线+预测校准+置信度调整) + Git初始化 |
| v0.9 | 自主推理引擎(reasoning.py) + SmartMockLLM + 14领域模板 + E2E测试 |

## 依赖

零外部 pip 依赖。仅使用 Python 3.13 标准库 + `urllib`。可选 Ollama 或 OpenAI API 作为 LLM 后端。

## 哲学

砚识的设计哲学是"研磨信息成有用之物"——不只回答问题，而是思考如何思考。详见 [PHILOSOPHY.md](PHILOSOPHY.md)。
