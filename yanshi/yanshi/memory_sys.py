"""
砚识 — 记忆系统

三层记忆模型：
  Layer 1 — 工作记忆: SESSION-STATE.md (WAL 协议，由 wal.py 管理)
  Layer 2 — 日志记忆: memory/YYYY-MM-DD.md (append-only 每日日志)
  Layer 3 — 蒸馏记忆: MEMORY.md + memory/ontology/graph.jsonl

蒸馏流程: daily logs (≥30天) → 按主题提炼 → MEMORY.md + ontology更新
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class MemorySystem:
    """三层记忆的读写和管理"""

    def __init__(self, workspace_root: str):
        self.root = Path(workspace_root)
        self.memory_dir = self.root / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "ontology").mkdir(exist_ok=True)

        self.memory_md = self.root / "MEMORY.md"
        self.ontology_file = self.memory_dir / "ontology" / "graph.jsonl"

    # ── Layer 2: 每日日志 ──

    def log_daily(self, entry: str, *, tag: str = "") -> bool:
        """追加一条记录到今日日志"""
        today = self._today()
        log_file = self.memory_dir / f"{today}.md"

        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        tag_prefix = f"[{tag}] " if tag else ""
        line = f"- **{timestamp}** {tag_prefix}{entry}\n"

        if not log_file.exists():
            header = f"# {today} — 砚识运行日志\n\n"
            log_file.write_text(header + line, encoding="utf-8")
        else:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
        return True

    def read_log(self, date_str: str) -> str:
        """读取指定日期的日志"""
        log_file = self.memory_dir / f"{date_str}.md"
        if not log_file.exists():
            return ""
        return log_file.read_text(encoding="utf-8")

    def log_size_today(self) -> int:
        """今日日志行数"""
        today = self._today()
        log_file = self.memory_dir / f"{today}.md"
        if not log_file.exists():
            return 0
        return len(log_file.read_text(encoding="utf-8").splitlines())

    # ── Layer 3: MEMORY.md 蒸馏 ──

    def distill(self, days: int = 30) -> list[str]:
        """蒸馏：从近期日志提炼到 MEMORY.md"""
        distilled = []
        recent_logs = self._get_recent_logs(days)

        if not recent_logs:
            return ["无日志可供蒸馏"]

        # 简单蒸馏策略：提取以"结论"、"教训"、"模式"、"决定" 开头的条目
        patterns = []
        for date_str, content in recent_logs:
            for line in content.splitlines():
                line = line.strip()
                if any(line.startswith(p) for p in [
                    "- **", "结论:", "教训:", "模式:", "决定:", "ADR:", "原则:"
                ]):
                    patterns.append(f"  - [{date_str}] {line.lstrip('- ')}")

        if not patterns:
            return ["无可蒸馏的模式"]

        if self.memory_md.exists():
            current = self.memory_md.read_text(encoding="utf-8")
        else:
            current = "# MEMORY.md — 蒸馏后的长期智慧\n\n"

        # 追加蒸馏内容
        section = f"\n## 蒸馏记录 ({self._today()})\n"
        section += "\n".join(patterns[-20:]) + "\n"  # 只保留最近20条

        new_content = current.rstrip() + section
        self.memory_md.write_text(new_content, encoding="utf-8")
        distilled.append(f"蒸馏了 {len(patterns[-20:])} 条模式到 MEMORY.md")
        return distilled

    # ── Layer 3: ontology 知识图谱 ──

    def add_entity(self, entity: str, relation: str, target: str) -> bool:
        """向知识图谱添加实体-关系-目标 三元组"""
        entry = {
            "entity": entity,
            "relation": relation,
            "target": target,
            "timestamp": self._now(),
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        try:
            with open(self.ontology_file, "a", encoding="utf-8") as f:
                f.write(line)
            return True
        except IOError:
            return False

    def query_entity(self, entity: str) -> list[dict]:
        """查询与某实体相关的所有关系"""
        if not self.ontology_file.exists():
            return []
        results = []
        with open(self.ontology_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line.strip())
                    if e.get("entity") == entity or e.get("target") == entity:
                        results.append(e)
                except json.JSONDecodeError:
                    continue
        return results

    def ontology_stats(self) -> dict:
        """知识图谱统计"""
        if not self.ontology_file.exists():
            return {"entities": 0, "relations": 0}
        entities = set()
        count = 0
        with open(self.ontology_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line.strip())
                    entities.add(e.get("entity", ""))
                    entities.add(e.get("target", ""))
                    count += 1
                except json.JSONDecodeError:
                    continue
        entities.discard("")
        return {"entities": len(entities), "relations": count}

    # ── 工具方法 ──

    def _today(self) -> str:
        from .models import utc_today
        return utc_today()

    def _now(self) -> str:
        from .models import utc_now
        return utc_now()

    def _get_recent_logs(self, days: int) -> list[tuple[str, str]]:
        """获取最近 N 天的日志"""
        logs = []
        if not self.memory_dir.exists():
            return logs
        files = sorted(self.memory_dir.glob("*.md"))
        # 只保留最近 N 个文件（按文件名排序，文件名形如 YYYY-MM-DD.md）
        if days > 0 and len(files) > days:
            files = files[-days:]
        for f in files:
            if f.name == "MEMORY.md":
                continue
            logs.append((f.stem, f.read_text(encoding="utf-8")))
        return logs[-days:]
