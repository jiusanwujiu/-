"""
砚识 — 健康检查系统

定期检查各子系统状态：
  - WAL 协议: 写入测试
  - 规则引擎: 规则加载状态
  - 记忆系统: 存储可用性
  - 心跳: 是否活跃
  - 工具链: 关键工具可用性
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class CheckResult:
    name: str
    status: HealthStatus
    message: str = ""
    detail: dict = field(default_factory=dict)


class HealthChecker:
    """
    健康检查器。

    用法:
      checker = HealthChecker()
      checker.register("wal", lambda: HealthStatus.HEALTHY)
      results = checker.run_all()
    """

    def __init__(self):
        self._checks: dict[str, tuple[str, Callable]] = {}  # {name: (description, check_fn)}
        self._last_results: list[CheckResult] = []

    def register(self, name: str, description: str, check_fn: Callable[[], HealthStatus]):
        """注册一个健康检查"""
        self._checks[name] = (description, check_fn)

    def run_all(self) -> list[CheckResult]:
        """运行所有健康检查"""
        results = []
        for name, (desc, fn) in self._checks.items():
            try:
                status = fn()
                if not isinstance(status, HealthStatus):
                    status = HealthStatus.HEALTHY if status else HealthStatus.UNHEALTHY
                results.append(CheckResult(name=name, status=status, message=desc))
            except Exception as e:
                results.append(CheckResult(
                    name=name, status=HealthStatus.UNHEALTHY,
                    message=f"{desc}: 检查异常 - {e}"
                ))

        self._last_results = results
        return results

    def overall_status(self) -> HealthStatus:
        """整体健康状态（使用缓存结果，不重复运行）"""
        if not self._last_results:
            return HealthStatus.HEALTHY

        if any(r.status == HealthStatus.UNHEALTHY for r in self._last_results):
            return HealthStatus.UNHEALTHY
        if any(r.status == HealthStatus.DEGRADED for r in self._last_results):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def report_text(self) -> str:
        """生成文本格式的健康报告"""
        results = self.run_all()
        overall = self.overall_status()

        emoji = {"healthy": "✓", "degraded": "△", "unhealthy": "✗"}
        lines = [
            f"健康状态: {emoji[overall.value]} {overall.value}",
            "-" * 30,
        ]
        for r in results:
            marker = emoji[r.status.value]
            lines.append(f"  {marker} {r.name}: {r.status.value}")
            if r.message:
                lines.append(f"    {r.message}")

        return "\n".join(lines)

    def get_last_results(self) -> list[CheckResult]:
        return self._last_results
