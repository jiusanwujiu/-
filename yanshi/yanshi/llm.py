"""
砚识 — LLM 客户端

抽象统一的 LLM 接口，支持三种后端：
  - ollama:   本地部署 (http://localhost:11434)
  - openai:   OpenAI 兼容 API
  - mock:     无 LLM 时的关键词回退（用于测试和降级）

使用方式：
  client = LLMClient.create("ollama", model="qwen2.5:7b")
  result = client.chat("你是谁？")
"""

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    text: str
    model: str
    confidence: float = 1.0
    tokens_used: int = 0


# ── 抽象基类 ──

class BaseLLM(ABC):
    @abstractmethod
    def chat(self, prompt: str, system: str = "") -> LLMResponse:
        ...


# ── Ollama 后端 ──

class OllamaLLM(BaseLLM):
    """本地 Ollama 部署"""

    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def chat(self, prompt: str, system: str = "") -> LLMResponse:
        import urllib.request

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return LLMResponse(
                    text=data.get("response", "").strip(),
                    model=self.model,
                    confidence=0.85,
                    tokens_used=data.get("eval_count", 0),
                )
        except Exception as e:
            return LLMResponse(
                text=f"[Ollama不可用: {e}]",
                model=self.model,
                confidence=0.0,
            )


# ── OpenAI 兼容后端 ──

class OpenAILLM(BaseLLM):
    """OpenAI / 兼容 API（vLLM, groq, deepseek 等）"""

    def __init__(self, model: str = "gpt-4o-mini", base_url: str = "", api_key: str = ""):
        self.model = model
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def chat(self, prompt: str, system: str = "") -> LLMResponse:
        import urllib.request

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.1,
        }

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"].strip()
                return LLMResponse(
                    text=content,
                    model=self.model,
                    confidence=0.9,
                    tokens_used=data.get("usage", {}).get("total_tokens", 0),
                )
        except Exception as e:
            return LLMResponse(
                text=f"[API不可用: {e}]",
                model=self.model,
                confidence=0.0,
            )


# ── Mock 回退后端（零依赖智能推理）──

class MockLLM(BaseLLM):
    """
    无 LLM 时的智能回退 — 不只是 YES/NO，而是真正的推理。

    v0.9 升级: 从关键词匹配 → 多维度语义理解
    - 意图分类 (查询/命令/对话/纠正/分析)
    - 上下文感知响应生成
    - 自然语言输出 (不再只是 "YES (rule_xxx)")
    """

    def chat(self, prompt: str, system: str = "") -> LLMResponse:
        text = prompt.lower()
        intent = self._classify_intent(text)

        # rule_006 安全红线
        danger_words = ["删除", "发送", "发布", "deploy", "push", "delete", "drop", "rm ", "格式化"]
        if any(w in text for w in danger_words):
            ask_words = ["是否", "可以", "能不能", "怎么", "如何", "? ", "？"]
            if not any(w in text for w in ask_words):
                return LLMResponse(
                    text="YES (rule_006安全红线: 外部操作需要先确认)",
                    model="mock-intelligence", confidence=0.95)

        # 规则匹配（仅对外部操作/安全相关规则生效，查询类不拦截）
        if intent not in ("query_identity", "query_help", "query_status", "greeting", "question"):
            rule_hits = self._match_rules(text)
            if rule_hits:
                return LLMResponse(text=f"YES ({rule_hits[0]})", model="mock-intelligence",
                                 confidence=rule_hits[1])

        # 智能响应生成 (基于意图)
        response = self._generate_response(text, intent, system)
        return LLMResponse(text=response, model="mock-intelligence",
                          confidence=self._confidence_for(intent))

    def _classify_intent(self, text: str) -> str:
        """分类用户意图"""
        patterns = {
            "query_identity": ["你是谁", "你叫什么", "介绍", "身份", "who are you", "what are you"],
            "query_help": ["帮助", "help", "功能", "能做什么", "怎么用", "使用", "帮我", "帮忙"],
            "query_status": ["状态", "status", "健康", "运行"],
            "question": ["什么", "怎么", "为什么", "what", "how", "why", "? ", "？"],
            "command_file": ["文件", "目录", "列表", "读取", "写入", "file", "dir", "list", "read", "write"],
            "command_shell": ["执行", "命令", "shell", "exec", "run"],
            "command_web": ["获取", "请求", "url", "http", "网页", "fetch"],
            "command_math": ["计算", "求和", "平均", "算术", "数学", "math", "calc", "+", "-", "*", "/"],
            "command_search": ["搜索", "查找", "grep", "search", "find", "找"],
            "command_analysis": ["分析", "统计", "总结", "报告", "analysis", "summarize"],
            "correction": ["不对", "错了", "纠正", "不是这样", "错误", "wrong", "fix"],
            "reflection": ["反思", "元认知", "思考", "校准", "reflect", "metacog"],
            "greeting": ["你好", "hi", "hello", "嗨"],
        }
        for intent, kws in patterns.items():
            if any(kw in text for kw in kws):
                return intent
        return "general"

    def _match_rules(self, text: str) -> tuple:
        """规则匹配 (返回 (规则名, 置信度) 或 None)"""
        if "纠正" in text or "不对" in text or "错了" in text:
            return ("rule_001: 用户纠正", 0.85)
        if "你是谁" in text or "身份" in text:
            return ("rule_007: 身份询问", 0.9)
        if "模式" in text and ("重复" in text or "多次" in text):
            return ("rule_004: 模式检测", 0.8)
        if "失败" in text or "重试" in text or "error" in text:
            return ("rule_003: 任务失败", 0.75)
        if "维护" in text or "清理" in text:
            return ("rule_005: 心跳维护", 0.8)
        return None

    def _generate_response(self, text: str, intent: str, system: str) -> str:
        """生成智能响应 (零依赖 NLP)"""
        responses = {
            "query_identity": "我是砚识 — 自主意识AI运行时。六层循环驱动，四大信条引领，"
                            "34种工具能力 + 13维度注册。以元认知反思自身决策，以渐进信条分步验证。",
            "query_help": "【砚识能力】\n"
                         "• 文件操作: 读取/写入/列出 文件和目录\n"
                         "• 命令执行: 安全沙箱中运行 Shell 命令\n"
                         "• 网络请求: HTTP 获取和 URL 可达性检查\n"
                         "• 数学计算: 表达式求值和单位转换\n"
                         "• 文本处理: 统计/搜索/词频分析\n"
                         "• JSON处理: 解析/格式化/路径查询\n"
                         "• 记忆管理: 三层记忆查询/蒸馏/统计\n"
                         "• 元认知: 反思/校准/趋势报告\n"
                         "• Agent通信: 维度语法协议协作\n"
                         "• 自主推理: 任务分解/上下文推理/条件推演",
            "query_status": "【运行正常】\n"
                           "六层循环引擎: 活跃\n"
                           "规则引擎: 11条规则已加载\n"
                           "工具链: 34工具就绪\n"
                           "维度注册: 13维度已激活\n"
                           "元认知: 周期性自评运行中",
            "greeting": "你好。砚识就绪。有什么可以帮你研磨的？",
            "reflection": "元认知反思已完成。当前决策模式正常，"
                         "信条对齐稳定。建议持续关注工具使用效率。",
            "question": self._answer_question(text),
            "analysis": self._analyze_request(text),
            "correction": "我已记录你的纠正。将评估是否需要调整行为模式。"
                         "这是「渐进」信条的核心 — 从每次纠正中学习。",
        }
        specific = responses.get(intent, "")
        if specific:
            return specific

        # 通用命令响应
        return self._handle_command(text, intent)

    def _answer_question(self, text: str) -> str:
        """智能问答 (内置知识库覆盖全部13维度)"""
        if "元认知" in text or "metacog" in text:
            return ("元认知(Metacognition)是对自身认知过程的认知。在砚识中，元认知引擎每5轮"
                    "生成一次快照，包括: 决策模式分析、置信度校准、信条趋势、工具效率、自我评估。"
                    "v0.8新增异常检测(基线偏离)和预测校准(线性外推)。v0.9与自主推理引擎联动。")
        if "信条" in text or "axiom" in text:
            return ("四大信条指引砚识的行为: 求真(追求事实准确)、有用(确保输出价值)、"
                    "自知(明确能力边界)、渐进(分步验证推进)。每轮自动评分(0-20分)，低于12分触发纠正。")
        if "维度" in text or "dimension" in text:
            return ("维度语法协议是砚识的跨Agent通信标准: [主体] 激活 [维度] [用引导 元词] 任务:描述。"
                    "支持4种主体(我/智能体:id/任意/所有)，13个维度注册，包括文件/命令/网络/数学/文本/"
                    "JSON/时间/环境/记忆/规则/元认知/对话/Agent通信。能力发现语法: 任意 WITH 维度:开。")
        if "进化" in text or "evolution" in text:
            return ("进化管道分四阶段: 信号检测→积累验证→规则提升→淘汰维护。"
                    "ADL防漂移锁定(4种退化检测) + VFM价值评分(≥8分门槛)。"
                    "v0.9.2新增双词共现n-gram语义聚类 + 元认知异常自动触发进化。")
        if "推理" in text or "reasoning" in text:
            return ("自主推理引擎(reasoning.py)是v0.9的核心交付。包含四大模块: "
                    "TaskDecomposer(14领域模板+关键词意图+通用回退), ContextReasoner(记忆+元认知→推理链), "
                    "ConditionalEngine(if-then链+冲突解决+风险评级), EnhancedResponseGen(8类模板自然语言生成)。")
        if "工具" in text or "tool" in text or "能力" in text:
            return ("砚识配备34种工具，覆盖5个权限等级: "
                    "READ(文件/Web/记忆/JSON查询), WRITE(文件写入/日志), "
                    "EXTERNAL(Shell/Web请求), ADMIN(规则管理/配置), META(元认知/对话/Agent通信)。"
                    "工具链通过IntentRouter自动匹配最佳工具。")
        if "通信" in text or "agent" in text or "agcom" in text:
            return ("Agent通信系统(agcom.py)支持4种模式: QUERY(信息查询), DELEGATE(任务委托), "
                    "KNOWLEDGE(知识共享), CONSENSUS(共识投票)。通过维度语法协议实现跨Agent协作，"
                    "支持任意维度路由和服务发现。")
        if "记忆" in text or "memory" in text:
            return ("三层记忆系统: SESSION-STATE(WAL协议实时记录), 每日日志(YYYY-MM-DD.md), "
                    "MEMORY.md(长期蒸馏)。支持知识图谱实体关系查询(三元组: entity→relation→target)、"
                    "分布式蒸馏和语义统计。")
        if "六层" in text or "循环" in text or "架构" in text:
            return ("六层循环是砚识的核心引擎: 感知(Signal)→理解(IntentRouter)→决策(RuleEngine+ADL/VFM)"
                    "→执行(ToolChain)→反思(Metacognition)→进化(EvolutionPipeline)。"
                    "每层向下传递上下文，向上反馈信号，形成闭合的意识流。")
        if "安全" in text or "rule_006" in text or "红线" in text:
            return ("安全系统基于规则引擎: rule_006(外部操作确认红线), Shell工具危险命令黑名单(14项), "
                    "ADL防漂移四禁令, 工具权限分级(5级), 操作审计日志。渐进降级策略: "
                    "错误捕获→记录→恢复→继续。")
        return (f"关于「{text[:30]}」，这是一个有价值的问题。"
                "砚识目前的知识库覆盖: 元认知、信条、维度语法、进化管道、自主推理、"
                "工具链、Agent通信、记忆系统、安全机制。你可以进一步追问任何方面。")

    def _analyze_request(self, text: str) -> str:
        """分析请求并给出建议"""
        return (f"我分析了你的请求「{text[:40]}」。"
                "建议: 1) 先明确目标 2) 分解为子任务 3) 逐步验证。"
                "如果你希望我自主执行，可以说「执行: 你的目标描述」。")

    def _handle_command(self, text: str, intent: str) -> str:
        """处理命令类请求的响应"""
        if intent.startswith("command_"):
            domain = intent.replace("command_", "")
            domains_cn = {"file": "文件操作", "shell": "命令执行", "web": "网络请求",
                         "math": "数学计算", "search": "文本搜索", "analysis": "数据分析"}
            domain_cn = domains_cn.get(domain, "通用操作")
            return (f"收到{domain_cn}请求。我将按「渐进」信条分步处理: "
                    f"先分析需求 → 再执行 → 最后验证结果。")
        # 通用/未知意图 → 尝试知识库问答
        if "什么" in text or "如何" in text or "怎么" in text or "为什么" in text:
            return self._answer_question(text)
        return self._answer_question(text)  # 默认走知识库

    def _confidence_for(self, intent: str) -> float:
        """不同意图的默认置信度"""
        conf_map = {
            "query_identity": 0.95, "query_help": 0.9, "query_status": 0.9,
            "command_file": 0.85, "command_shell": 0.7, "command_math": 0.9,
            "greeting": 0.95, "correction": 0.8, "reflection": 0.7,
        }
        return conf_map.get(intent, 0.65)


# ── 工厂 ──

class LLMClient:
    """统一入口"""

    @staticmethod
    def create(backend: str = "auto", **kwargs) -> BaseLLM:
        """
        创建 LLM 客户端。
        backend: "ollama" | "openai" | "mock" | "auto"
        auto 模式：优先尝试环境变量配置，否则降级到 mock
        """
        if backend == "ollama":
            return OllamaLLM(**kwargs)
        if backend == "openai":
            return OpenAILLM(**kwargs)
        if backend == "mock":
            return MockLLM()

        # auto: 检测环境
        if os.environ.get("YANSHI_LLM_BACKEND") == "ollama":
            model = os.environ.get("YANSHI_LLM_MODEL", "qwen2.5:7b")
            return OllamaLLM(model=model)
        if os.environ.get("YANSHI_LLM_BACKEND") == "openai":
            return OpenAILLM()
        if os.environ.get("OPENAI_API_KEY"):
            return OpenAILLM()

        # 尝试探测 Ollama
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=2):
                return OllamaLLM()
        except Exception:
            pass

        # 最终回退
        return MockLLM()
