"""
砚识 — 配置管理

从 YAML 文件加载配置，支持默认值和环境变量覆盖。
"""

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


# ── 配置数据结构 ──

@dataclass
class LogConfig:
    level: str = "INFO"              # DEBUG | INFO | WARNING | ERROR
    file_enabled: bool = True        # 是否写入文件
    console_enabled: bool = True     # 是否输出到控制台
    max_file_size_mb: int = 10       # 单日志文件最大大小
    backup_count: int = 3            # 备份文件数量


@dataclass
class EngineConfig:
    llm_backend: str = "auto"        # auto | ollama | openai | mock
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    cycle_interval_ms: int = 0       # 循环间隔（0=无间隔）


@dataclass
class ToolConfig:
    shell_timeout: int = 30          # Shell 默认超时（秒）
    web_timeout: int = 10            # Web 请求默认超时（秒）
    file_max_read_lines: int = 500   # 文件读取最大行数
    danger_commands: list[str] = field(default_factory=lambda: [
        "rm -rf /", "dd if=", "mkfs", "> /dev/sda"
    ])


@dataclass
class HeartbeatConfig:
    enabled: bool = True
    interval_seconds: int = 15


@dataclass
class OpsConfig:
    health_check_enabled: bool = True
    metrics_enabled: bool = True
    dashboard_enabled: bool = True


@dataclass
class WorkspaceConfig:
    """完整的工作空间配置"""
    log: LogConfig = field(default_factory=LogConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    tool: ToolConfig = field(default_factory=ToolConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    ops: OpsConfig = field(default_factory=OpsConfig)

    def to_dict(self) -> dict:
        result = {}
        for section in ["log", "engine", "tool", "heartbeat", "ops"]:
            result[section] = asdict(getattr(self, section))
        return result


# ── 配置管理器 ──

class ConfigManager:
    """
    配置管理器。

    加载顺序: 默认值 → YAML 文件 → 环境变量覆盖
    环境变量前缀: YANSHI_
    例如: YANSHI_LOG_LEVEL=DEBUG 覆盖 log.level
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else None
        self.config = WorkspaceConfig()
        self._loaded = False

    def load(self, config_path: Optional[str] = None) -> WorkspaceConfig:
        """加载配置"""
        if config_path:
            self.config_path = Path(config_path)

        # 从 YAML 文件加载
        if self.config_path and self.config_path.exists():
            self._load_yaml()

        # 环境变量覆盖
        self._apply_env_overrides()

        self._loaded = True
        return self.config

    def _load_yaml(self):
        """从 YAML 文件加载配置（不依赖 PyYAML，纯手动解析）"""
        try:
            content = self.config_path.read_text(encoding="utf-8")
            self._parse_yaml_simple(content)
        except Exception:
            # 解析失败则使用默认值
            pass

    def _parse_yaml_simple(self, content: str):
        """简单的 YAML 键值解析（支持一级和二级键）"""
        current_section = None
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # 检测 section header
            if not stripped.startswith("-") and ":" in stripped and not stripped.startswith(" "):
                section = stripped.rstrip(":").strip()
                if hasattr(self.config, section):
                    current_section = section
                continue

            # 二级键值
            if current_section and ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")

                section_obj = getattr(self.config, current_section)
                if hasattr(section_obj, key):
                    field_type = type(getattr(section_obj, key))
                    if field_type == bool:
                        setattr(section_obj, key, val.lower() in ("true", "yes", "1"))
                    elif field_type == int:
                        setattr(section_obj, key, int(val))
                    elif field_type == float:
                        setattr(section_obj, key, float(val))
                    elif field_type == list:
                        pass  # 列表暂不支持简单解析
                    else:
                        setattr(section_obj, key, val)

    def _apply_env_overrides(self):
        """环境变量覆盖（YANSHI_ 前缀）"""
        for key, value in os.environ.items():
            if not key.startswith("YANSHI_"):
                continue

            parts = key[7:].lower().split("__", 1)
            if len(parts) != 2:
                continue

            section, field = parts
            if hasattr(self.config, section):
                section_obj = getattr(self.config, section)
                if hasattr(section_obj, field):
                    field_type = type(getattr(section_obj, field))
                    if field_type == bool:
                        setattr(section_obj, field, value.lower() in ("true", "yes", "1"))
                    elif field_type == int:
                        setattr(section_obj, field, int(value))
                    else:
                        setattr(section_obj, field, value)

    def save(self, path: Optional[str] = None) -> str:
        """保存当前配置到 YAML 文件"""
        target = Path(path) if path else self.config_path
        if not target:
            raise ValueError("未指定配置路径")

        lines = ["# 砚识 v0.8 配置文件", "# 环境变量覆盖: YANSHI_<section>__<key>=<value>", ""]
        for section_name in ["log", "engine", "tool", "heartbeat", "ops"]:
            section = getattr(self.config, section_name)
            lines.append(f"{section_name}:")
            for key, value in asdict(section).items():
                if isinstance(value, bool):
                    lines.append(f"  {key}: {'true' if value else 'false'}")
                elif isinstance(value, list):
                    lines.append(f"  {key}: [{', '.join(value)}]")
                elif isinstance(value, str):
                    lines.append(f'  {key}: "{value}"')
                else:
                    lines.append(f"  {key}: {value}")
            lines.append("")

        target.write_text("\n".join(lines), encoding="utf-8")
        return str(target)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """获取单个配置项"""
        if hasattr(self.config, section):
            section_obj = getattr(self.config, section)
            if hasattr(section_obj, key):
                return getattr(section_obj, key)
        return default
