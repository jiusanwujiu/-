"""
砚识 v0.8 — 意图路由器

从纯关键词匹配升级为三级路由：
  1. 上下文感知（检测续接/回指/追问，继承上一轮工具/意图）
  2. 加权关键词评分（关键词权重 + 多词命中加分 + 顺序惩罚）
  3. 模糊匹配（编辑距离 + token级命中）

相比 v0.4 关键词匹配的改进：
  - 上下文：记住上轮使用的工具，支持"再执行一次""格式化一下"等省略表达
  - 权重：每个关键词有 weight(0.4-1.0)，多词命中累计加分
  - 覆盖：25 个工具全部有意图关键词
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IntentMatch:
    """意图匹配结果"""
    intent: str
    confidence: float
    tool_name: str = ""
    keywords_hit: list = field(default_factory=list)
    source: str = "keyword"  # keyword | context | fallback


class IntentRouter:
    """
    意图路由器 — 三级路由策略。

    用法:
        router = IntentRouter()
        match = router.route("读取 D:/test.txt")
        # → IntentMatch(intent="tool_exec", tool_name="file_read", confidence=0.95)
    """

    # ── 所有工具的关键词映射（含权重）──
    # 格式: (关键词, 权重) — 权重越高越关键
    TOOL_INTENTS = {
        "file_list": [
            (["列出", "显示目录", "查看目录", "ls", "list files"], 1.0),
            (["dir", "目录", "文件夹", "文件列表"], 0.7),
        ],
        "file_read": [
            (["读取", "查看文件", "打开文件", "cat", "read file"], 1.0),
            (["读", "看", "显示文件", "文件内容"], 0.7),
        ],
        "file_write": [
            (["写入", "保存", "创建文件", "write file", "新建文件"], 1.0),
            (["写", "输出到", "追加"], 0.7),
        ],
        "shell_exec": [
            (["执行", "运行", "exec", "run"], 1.0),
            (["命令行", "shell", "cmd", "执行命令"], 0.7),
        ],
        "web_fetch": [
            (["获取", "抓取", "fetch", "下载网页", "爬取"], 1.0),
            (["打开网页", "访问", "请求"], 0.7),
        ],
        "web_check": [
            (["检查", "检测", "ping", "连通", "可达"], 1.0),
            (["状态码", "是否在线", "响应"], 0.7),
        ],
        "memory_query": [
            (["查询记忆", "搜索记忆", "search memory", "记忆查询"], 1.0),
            (["回忆", "查找", "搜索", "知识图谱"], 0.7),
        ],
        "memory_distill": [
            (["蒸馏", "distill", "清理记忆", "压缩记忆"], 1.0),
            (["归档", "整理记忆"], 0.7),
        ],
        "memory_stats": [
            (["记忆统计", "memory stats", "记忆状态"], 1.0),
            (["记忆概览", "统计记忆"], 0.7),
        ],
        "rule_list": [
            (["规则列表", "显示规则", "rule list", "列出规则"], 1.0),
            (["规则", "rules"], 0.5),
        ],
        "rule_toggle": [
            (["启用规则", "禁用规则", "切换规则", "toggle rule"], 1.0),
            (["开关规则"], 0.7),
        ],
        "rule_reload": [
            (["重载规则", "reload rules", "刷新规则"], 1.0),
            (["重新加载"], 0.5),
        ],
        # ── v0.4.1 新增工具 ──
        "datetime": [
            (["现在时间", "当前时间", "几点", "日期", "今天几号"], 1.0),
            (["时间", "date", "time", "现在"], 0.5),
        ],
        "timediff": [
            (["时间差", "时间间隔", "多久", "相差", "time diff"], 1.0),
            (["过了多久", "还有多久", "倒计时"], 0.7),
        ],
        "timestamp": [
            (["时间戳", "timestamp", "转时间戳", "时间戳转换"], 1.0),
            (["unix time", "unix时间"], 0.7),
        ],
        "json_parse": [
            (["解析json", "json解析", "parse json", "验证json"], 1.0),
            (["json", "json字符串", "解析"], 0.5),
        ],
        "json_format": [
            (["格式化json", "美化json", "json格式化", "format json", "pretty"], 1.0),
            (["美化", "格式化", "json"], 0.5),
        ],
        "json_query": [
            (["json查询", "json路径", "提取json", "query json"], 1.0),
            (["从json", "json中"], 0.6),
        ],
        "text_stats": [
            (["文本统计", "统计字数", "字数", "词频统计", "word count"], 1.0),
            (["统计文本", "文本分析"], 0.7),
        ],
        "text_search": [
            (["文本搜索", "搜索文本", "查找文本", "文本查找", "text search"], 1.0),
            (["文本中", "搜索到"], 0.5),
        ],
        "text_freq": [
            (["词频", "高频词", "出现次数", "频率统计", "top words"], 1.0),
            (["常见词", "关键词提取"], 0.7),
        ],
        "env_read": [
            (["环境变量", "env", "environment", "读取变量"], 1.0),
            (["系统变量", "变量值"], 0.7),
        ],
        "sysinfo": [
            (["系统信息", "sysinfo", "system info", "操作系统"], 1.0),
            (["系统版本", "平台", "python版本"], 0.7),
        ],
        "math_eval": [
            (["计算", "求值", "算一下", "math", "calculate", "eval"], 1.0),
            (["等于多少", "多少", "公式"], 0.5),
        ],
        "unit_convert": [
            (["转换", "单位换算", "换算", "convert", "转换单位"], 1.0),
            (["摄氏度", "华氏度", "开尔文", "公里", "英里", "千克", "磅"], 0.5),
        ],
        # ── v0.5: 对话记忆 + 元认知工具 ──
        "dialogue_history": [
            (["对话历史", "之前说了什么", "聊天记录", "对话记录", "dialogue history"], 1.0),
            (["刚才说了", "之前聊", "对话上下文"], 0.7),
        ],
        "dialogue_stats": [
            (["对话统计", "对话状态", "dialogue stats"], 1.0),
            (["聊了多少", "对话概览"], 0.7),
        ],
        "meta_reflect": [
            (["元认知", "自我反思", "反思一下", "meta reflect", "元认知反思"], 1.0),
            (["自我评估", "校准分析"], 0.7),
        ],
        "meta_report": [
            (["元认知报告", "元认知趋势", "meta report", "反思报告"], 1.0),
            (["认知趋势", "决策分析"], 0.7),
        ],
        # ── v0.6: Agent 通信工具 ──
        "agent_list": [
            (["agent列表", "列出agent", "agent list", "有哪些agent"], 1.0),
            (["agent", "注册的agent"], 0.6),
        ],
        "agent_send": [
            (["发送消息", "agent发送", "agent send", "给agent发"], 1.0),
            (["发给", "发送给"], 0.6),
        ],
        "agent_delegate": [
            (["委托", "agent委托", "agent delegate", "代理任务"], 1.0),
            (["交给", "指派", "转交"], 0.6),
        ],
        "agent_consensus": [
            (["agent共识", "共识投票", "agent consensus", "发起投票"], 1.0),
            (["投票", "共识"], 0.5),
        ],
        "agent_broadcast": [
            (["agent广播", "广播消息", "agent broadcast", "通知所有agent"], 1.0),
            (["广播", "通知"], 0.5),
        ],
    }

    # ── 非工具意图（系统/交互类）──
    NON_TOOL_INTENTS = {
        "identity_query": [
            (["你是谁", "身份", "介绍", "who are you", "名字", "叫什么"], 1.0),
        ],
        "tool_list": [
            (["工具有哪些", "列出工具", "tool list", "所有工具", "有什么工具"], 1.0),
            (["工具", "tool", "功能列表"], 0.5),
        ],
        "metrics_query": [
            (["指标", "metrics", "metric", "面板", "dashboard"], 1.0),
            (["统计", "运行数据", "性能"], 0.7),
        ],
        "health_query": [
            (["健康", "health", "状态检查", "健康检查"], 1.0),
            (["检查状态"], 0.7),
        ],
        "system_status": [
            (["进化", "evolve", "evol", "进化状态"], 1.0),
            (["系统状态"], 0.6),
        ],
        "memory_query": [
            (["记忆", "memory", "日志", "log"], 1.0),
        ],
        "maintenance": [
            (["心跳", "heartbeat", "维护", "清理"], 1.0),
        ],
        "help": [
            (["帮助", "help", "功能", "命令", "怎么用"], 1.0),
        ],
        "correction": [
            (["纠正", "不对", "错了", "fix", "修正", "不是"], 1.0),
            (["更正"], 0.8),
        ],
        "stats": [
            (["统计", "stats", "状态报告", "运行统计"], 1.0),
        ],
    }

    # 上下文续接关键词（表示复用上一轮工具/意图）
    CONTEXTUAL_PATTERNS = [
        (r"^(再|继续|又|还|重新).*(?:执行|运行|做|来|一次|一遍)", "repeat_last_tool"),
        (r"^(?:刚才|刚刚|上次|上一轮).*(?:那个|这个|呢)", "repeat_last_tool"),
        (r"^(?:格式化|美化|解析).*(?:一下|这个)", "repeat_last_tool"),
        (r"^(?:也|同样).*(?:一下|执行|运行)", "repeat_last_tool"),
    ]

    # 指代消解词 → 继承上轮参数
    PRONOUN_PATTERNS = [
        (r"那个(?:文件|目录|路径|文本|json|字符串)", "inherit_params"),
        (r"这个(?:文件|目录|路径|文本|json|字符串)", "inherit_params"),
        (r"刚才(?:那个|的)", "inherit_params"),
    ]

    def __init__(self):
        self._last_intent: Optional[str] = None
        self._last_tool: Optional[str] = None
        self._last_input: Optional[str] = None
        self._last_params: dict = {}
        self._context_stack: list[dict] = []  # 最近 5 轮上下文

    def route(self, text: str) -> IntentMatch:
        """
        三级路由入口。
        """
        text_lower = text.strip().lower()

        # ── Level 1: 上下文感知 ──
        context_match = self._try_context(text_lower)
        if context_match and context_match.confidence >= 0.75:
            return context_match

        # ── Level 2: 加权关键词（工具优先）──
        tool_match = self._weighted_match(text_lower, self.TOOL_INTENTS, is_tool=True)
        if tool_match and tool_match.confidence >= 0.50:
            return tool_match

        # ── Level 3: 非工具意图 ──
        intent_match = self._weighted_match(text_lower, self.NON_TOOL_INTENTS, is_tool=False)
        if intent_match and intent_match.confidence >= 0.50:
            return intent_match

        # ── Fallback ──
        return IntentMatch(intent="general_question", confidence=0.4, source="fallback")

    def update_context(self, intent: str, tool_name: str = "", text: str = "", params: dict = None):
        """更新上下文（每轮结束后调用）"""
        self._last_intent = intent
        self._last_tool = tool_name
        self._last_input = text
        self._last_params = params or {}
        self._context_stack.append({
            "intent": intent,
            "tool": tool_name,
            "input": text,
            "params": params or {},
        })
        if len(self._context_stack) > 5:
            self._context_stack.pop(0)

    # ── 内部方法 ──

    def _try_context(self, text: str) -> Optional[IntentMatch]:
        """Level 1: 检测上下文续接"""
        if not self._last_tool:
            return None

        # 检测明确的续接信号
        for pattern, action in self.CONTEXTUAL_PATTERNS:
            if re.search(pattern, text):
                return IntentMatch(
                    intent="tool_exec",
                    confidence=0.85,
                    tool_name=self._last_tool,
                    keywords_hit=[f"context:{action}"],
                    source="context",
                )

        # 检测指代消解
        for pattern, action in self.PRONOUN_PATTERNS:
            if re.search(pattern, text):
                return IntentMatch(
                    intent="tool_exec",
                    confidence=0.80,
                    tool_name=self._last_tool,
                    keywords_hit=[f"pronoun:{action}"],
                    source="context",
                )

        return None

    @staticmethod
    def _weighted_match(text: str, intent_map: dict, is_tool: bool = False) -> Optional[IntentMatch]:
        """
        加权关键词评分算法：
        - 每个关键词组有 weight(0.4-1.0)
        - 多词命中累计加分 (同一组内每多命中一个 +0.05)
        - token 级宽松匹配次优先: 拆词后独立命中给 0.6 倍权重
        - 最终 confidence = top_weight + multi_bonus，上限 0.98
        - 平局时选有更多命中词的
        """
        best_match = None
        best_weight = 0.0

        for intent_name, keyword_groups in intent_map.items():
            group_max = 0.0
            total_hits = []

            for keywords, base_weight in keyword_groups:
                hits = [kw for kw in keywords if kw in text]
                if not hits:
                    # ── Token 级宽松匹配 ──
                    # 尝试拆词后匹配（如 "解析这个json" 命中 "解析json" 的 tokens）
                    hits = _token_match(keywords, text)
                    if hits:
                        base_weight *= 0.7  # 宽松匹配打 7 折

                if hits:
                    multi_bonus = min(0.10, (len(hits) - 1) * 0.05)
                    composite = base_weight + multi_bonus
                    if composite > group_max:
                        group_max = composite
                    total_hits.extend(hits)

            if group_max > best_weight or (group_max == best_weight and len(total_hits) > len(best_match.keywords_hit if best_match else [])):
                best_weight = group_max
                confidence = min(0.98, group_max + len(total_hits) * 0.02)
                best_match = IntentMatch(
                    intent="tool_exec" if is_tool else intent_name,
                    confidence=round(confidence, 2),
                    tool_name=intent_name if is_tool else "",
                    keywords_hit=total_hits,
                    source="keyword",
                )

        return best_match

    @staticmethod
    def extract_params(text: str, tool_name: str) -> dict:
        """从用户输入中提取工具参数（通用方法）"""
        import re
        params = {}

        # ── 工具特定参数提取（优先，精确匹配）──
        extractors = {
            "file_read": lambda: _extract_path(text, params, file_kw_list),
            "file_list": lambda: _extract_path(text, params, file_kw_list),
            "file_write": lambda: _extract_path(text, params, file_kw_list),
            "shell_exec": lambda: params.setdefault("command", _strip_keywords(text, shell_kw_list)),
            "web_fetch": lambda: _extract_url(text, params),
            "web_check": lambda: _extract_url(text, params),
            "memory_query": lambda: params.setdefault("entity", _strip_keywords(text, mem_kw_list)),
            "memory_distill": lambda: params.setdefault("days", 30),
            "text_search": lambda: params.setdefault("pattern", _strip_keywords(text, text_kw_list)),
            "math_eval": lambda: _extract_expression(text, params),
            "unit_convert": lambda: _extract_unit_params(text, params),
            "json_parse": lambda: params.setdefault("json", _find_json_in_text(text)),
            "json_format": lambda: params.setdefault("json", _find_json_in_text(text)),
        }

        if tool_name in extractors:
            try:
                extractors[tool_name]()
            except Exception:
                pass

        # ── 通用模式提取（回退/补充）──
        # 1. 引号包裹的参数
        quoted = re.findall(r'["\u201c]([^"\u201d]+)["\u201d]', text)
        if quoted:
            for q in quoted:
                if "/" in q or "\\" in q:
                    params.setdefault("path", q)
                elif "{" in q and "}" in q:
                    params.setdefault("json", q)
                elif tool_name in ("text_stats", "text_search", "text_freq"):
                    params.setdefault("text", q)
                else:
                    params.setdefault("query", q)

        # 2. 路径提取（仅当没有从工具特定提取中获得路径时）
        if "path" not in params:
            path_match = re.search(
                r'((?:[A-Za-z]:)[\/\\][a-zA-Z0-9_.\-]+(?:[\/\\][a-zA-Z0-9_.\-]+)*(?:\.[a-zA-Z0-9]+)?)',
                text.replace("\\", "/"),
            )
            if path_match:
                raw = path_match.group(1)
                if raw and raw not in (".", ".."):
                    params.setdefault("path", raw)

        # 3. JSON 字符串检测
        json_match = re.search(r'\{[^{}]*\}', text)
        if json_match and "json" not in params:
            params.setdefault("json", json_match.group(0))

        # 数字提取（通用）
        numbers = re.findall(r'\b(\d+)\b', text)
        if numbers and tool_name in ("math_eval", "memory_distill", "text_freq"):
            key = {"math_eval": "precision", "memory_distill": "days", "text_freq": "top"}.get(tool_name)
            if key and key not in params:
                params[key] = int(numbers[0])

        return params


# ── Token 级宽松匹配 ──

def _token_match(keywords: list, text: str) -> list:
    """
    将关键词拆成 token，检查是否独立出现在文本中。
    如 "解析json" → tokens ["解析", "json"]，文本 "解析这个json" 中两个 token 都独立存在则命中。
    返回匹配命中的关键词列表，或空列表。
    """
    hits = []
    for kw in keywords:
        # 中文+英文混合关键词：按中文字符和英文单词拆分
        tokens = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z0-9_]+', kw)
        if len(tokens) >= 2 and all(tok.lower() in text.lower() for tok in tokens):
            hits.append(kw)
    return hits


# ── 关键词列表（用于参数提取时的清理）──

file_kw_list = ["读取", "查看文件", "显示文件", "查看目录", "显示目录",
                "列出", "读取文件", "cat", "read", "list", "ls",
                "打开文件", "文件内容", "文件夹", "文件列表", "目录"]

shell_kw_list = ["执行", "运行命令", "run", "exec", "命令行", "shell", "cmd",
                 "执行命令", "运行"]

mem_kw_list = ["搜索", "查询记忆", "查找", "search", "查询", "memory",
               "回忆", "记忆查询"]

text_kw_list = ["搜索文本", "文本搜索", "查找文本", "文本查找", "搜索到",
                "文本中", "搜索"]

# ── 参数提取辅助函数 ──

def _strip_keywords(text: str, keywords: list) -> str:
    """从文本中移除关键词，返回剩余内容"""
    result = text
    for kw in sorted(keywords, key=len, reverse=True):
        result = result.replace(kw, "", 1)
    return result.strip().strip("：:").strip()


def _extract_path(text: str, params: dict, keywords: list):
    """从文本中提取文件路径（先清理关键词，再用严格正则匹配）"""
    cleaned = _strip_keywords(text, keywords)
    match = re.search(
        r'((?:[A-Za-z]:)[\/\\][a-zA-Z0-9_.\-\u4e00-\u9fff]+(?:[\/\\][a-zA-Z0-9_.\-\u4e00-\u9fff]+)*(?:\.[a-zA-Z0-9]+)?)',
        cleaned.replace("\\", "/"),
    )
    if match and match.group(1):
        params["path"] = match.group(1)
    elif cleaned.strip():
        params["path"] = cleaned.strip()


def _extract_url(text: str, params: dict):
    """提取 URL"""
    url_match = re.search(r'(https?://[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s]*)', text)
    if url_match:
        params.setdefault("url", url_match.group(1))


def _find_json_in_text(text: str) -> str:
    """在文本中提取 JSON 片段"""
    # 找最外层 {}
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                return text[start:i + 1]
    return ""


def _extract_expression(text: str, params: dict):
    """提取数学表达式"""
    # 匹配数字、运算符、函数名的组合
    expr_match = re.search(r'([\d+\-*/().%\s^a-zA-Z_]+)', text)
    if expr_match:
        expr = expr_match.group(1).strip()
        # 清理前后噪音
        for kw in ["计算", "求值", "算一下", "等于多少"]:
            expr = expr.replace(kw, "")
        expr = expr.strip()
        if expr:
            params.setdefault("expression", expr)


def _extract_unit_params(text: str, params: dict):
    """提取单位换算参数"""
    # 匹配 "数字 单位 到/转/等于 单位" 模式（支持中英文单位）
    unit_match = re.search(
        r'(\d+\.?\d*)\s*([a-zA-Z°℃℉\u00b0\u4e00-\u9fff]+)\s*(?:到|→|->|转|转成|换成|换算成|换算|等于多少|等于)\s*([a-zA-Z°℃℉\u00b0\u4e00-\u9fff]+)',
        text,
    )
    if unit_match:
        params["value"] = float(unit_match.group(1))
        from_unit = unit_match.group(2)
        to_unit = unit_match.group(3)
        # 中文单位映射
        cn_map = {"摄氏度": "°C", "华氏度": "°F", "开尔文": "K",
                   "公里": "km", "米": "m", "厘米": "cm", "毫米": "mm",
                   "英里": "mi", "英尺": "ft", "英寸": "in",
                   "千克": "kg", "公斤": "kg", "克": "g", "毫克": "mg",
                   "磅": "lb", "盎司": "oz"}
        params["from"] = cn_map.get(from_unit, from_unit)
        params["to"] = cn_map.get(to_unit, to_unit)
