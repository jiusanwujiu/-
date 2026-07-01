"""
砚识工具 — 文本处理工具

提供文本统计、搜索和转换能力。
权限级别: READ（仅处理传入的数据，无副作用）
"""

import re
from collections import Counter

from .base import Tool, ToolResult, ToolPermission


class TextStatsTool(Tool):
    """文本统计"""

    def __init__(self):
        super().__init__(
            name="text_stats",
            description="统计文本的字数、行数、词数、字符数",
            permission=ToolPermission.READ,
            parameters={
                "text": {"type": "string", "description": "要统计的文本内容"},
            },
        )

    def execute(self, **params) -> ToolResult:
        text = params.get("text", "")
        if not text:
            return ToolResult(success=False, output="未提供文本", error="empty input")

        chars = len(text)
        chars_no_space = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
        lines = text.count("\n") + 1
        words = len(text.split())

        cjk_pattern = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
        cjk_chars = len(cjk_pattern.findall(text))

        return ToolResult(
            success=True,
            output=f"字符: {chars} | 行: {lines} | 词: {words} | 中文字: {cjk_chars}",
            data={
                "characters": chars,
                "characters_no_space": chars_no_space,
                "lines": lines,
                "words": words,
                "chinese_characters": cjk_chars,
                "avg_word_length": round(chars / max(words, 1), 1),
            },
        )


class TextSearchTool(Tool):
    """文本搜索"""

    def __init__(self):
        super().__init__(
            name="text_search",
            description="在文本中搜索关键词/正则，返回匹配位置和上下文",
            permission=ToolPermission.READ,
            parameters={
                "text": {"type": "string", "description": "要搜索的文本"},
                "pattern": {"type": "string", "description": "搜索关键词或正则表达式"},
                "regex": {"type": "boolean", "description": "是否使用正则匹配，默认 false"},
                "context": {"type": "integer", "description": "上下文行数，默认 1"},
            },
        )

    def execute(self, **params) -> ToolResult:
        text = params.get("text", "")
        pattern = params.get("pattern", "")
        use_regex = params.get("regex", False)
        context_lines = params.get("context", 1)

        if not text or not pattern:
            return ToolResult(success=False, output="未提供文本或搜索模式", error="empty input")

        lines = text.split("\n")
        matches = []

        for i, line in enumerate(lines):
            if use_regex:
                try:
                    found = [(m.start(), m.end()) for m in re.finditer(pattern, line)]
                except re.error as e:
                    return ToolResult(success=False, output=f"正则表达式无效: {e}", error=str(e))
            else:
                start = 0
                found = []
                while True:
                    idx = line.find(pattern, start)
                    if idx == -1:
                        break
                    found.append((idx, idx + len(pattern)))
                    start = idx + 1

            if found:
                ctx_start = max(0, i - context_lines)
                ctx_end = min(len(lines), i + context_lines + 1)
                matches.append({
                    "line": i + 1,
                    "content": line,
                    "positions": list(found),
                    "context": lines[ctx_start:ctx_end],
                })

        return ToolResult(
            success=True,
            output=f"找到 {len(matches)} 处匹配" if matches else "未找到匹配",
            data={"total_matches": len(matches), "matches": matches[:20]},
        )


class TextFreqTool(Tool):
    """词频统计"""

    def __init__(self):
        super().__init__(
            name="text_freq",
            description="统计文本中词的出现频率（Top N）",
            permission=ToolPermission.READ,
            parameters={
                "text": {"type": "string", "description": "要统计的文本"},
                "top": {"type": "integer", "description": "返回前 N 个高频词，默认 10"},
                "min_len": {"type": "integer", "description": "最小词长度，默认 2"},
                "lang": {"type": "string", "description": "语言: zh/en/auto，默认 auto"},
            },
        )

    def execute(self, **params) -> ToolResult:
        text = params.get("text", "")
        if not text:
            return ToolResult(success=False, output="未提供文本", error="empty input")

        top_n = params.get("top", 10)
        min_len = params.get("min_len", 2)
        lang = params.get("lang", "auto")

        if lang == "zh" or any("\u4e00" <= c <= "\u9fff" for c in text[:100]):
            cleaned = re.sub(r"[^\u4e00-\u9fff\w]", " ", text)
            words = [w for w in cleaned.split() if len(w) >= min_len]
        else:
            cleaned = re.sub(r"[^\w\s]", "", text)
            words = [w.lower() for w in cleaned.split() if len(w) >= min_len]

        counter = Counter(words)
        top_words = counter.most_common(top_n)

        return ToolResult(
            success=True,
            output="\n".join(f"  {w}: {c}次" for w, c in top_words),
            data={
                "total_unique": len(counter),
                "total_words": len(words),
                "top": [{"word": w, "count": c} for w, c in top_words],
            },
        )
