"""
砚识 — 运维面板

生成实时运维仪表盘 HTML 页面。
展示引擎指标、信条趋势、工具链统计、健康状态。
"""

from datetime import datetime, timezone
from typing import Optional


class DashboardGenerator:
    """
    运维面板 HTML 生成器。

    用法:
      dashboard = DashboardGenerator(engine)
      html = dashboard.render()
    """

    def __init__(self, engine=None):
        self._engine = engine

    def set_engine(self, engine):
        self._engine = engine

    def render(self) -> str:
        """生成运维面板 HTML"""
        if not self._engine:
            return "<h1>引擎未初始化</h1>"

        snap = self._engine.metrics.snapshot() if hasattr(self._engine, 'metrics') else {}
        rules = self._engine.rules.all_rules() if hasattr(self._engine, 'rules') else []
        axiom_trend = self._engine.axiom_journal.trend() if hasattr(self._engine, 'axiom_journal') else {}
        health = self._engine.health.overall_status().value if hasattr(self._engine, 'health') else "unknown"

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>砚识 v0.8 — 运维面板</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 24px; border-radius: 12px; margin-bottom: 20px; }}
  .header h1 {{ font-size: 28px; margin-bottom: 4px; }}
  .header p {{ opacity: 0.7; font-size: 14px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
  .card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .card h3 {{ font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }}
  .metric {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f0f0f0; }}
  .metric:last-child {{ border-bottom: none; }}
  .metric .label {{ color: #666; font-size: 13px; }}
  .metric .value {{ font-weight: 600; font-size: 14px; }}
  .value.green {{ color: #22c55e; }}
  .value.red {{ color: #ef4444; }}
  .value.amber {{ color: #f59e0b; }}
  .status {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
  .status.healthy {{ background: #22c55e; }}
  .status.degraded {{ background: #f59e0b; }}
  .status.unhealthy {{ background: #ef4444; }}
  .bar {{ height: 8px; background: #e5e7eb; border-radius: 4px; margin-top: 8px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
  .bar-fill.green {{ background: #22c55e; }}
  .bar-fill.amber {{ background: #f59e0b; }}
  .rule-row {{ display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }}
  .rule-row .id {{ font-family: monospace; color: #6366f1; }}
  .rule-row .trig {{ color: #666; }}
  small {{ font-size: 12px; color: #999; }}
</style>
</head>
<body>

<div class="header">
  <h1>砚识 v0.8</h1>
  <p>运维面板 — 研磨信息成有用之物 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
</div>

<div class="grid">
  <!-- 引擎 -->
  <div class="card">
    <h3>⚙ 引擎</h3>
    <div class="metric"><span class="label">运行循环</span><span class="value">{snap.get('cycles', {}).get('total', 0)}</span></div>
    <div class="metric"><span class="label">平均耗时</span><span class="value">{snap.get('cycles', {}).get('avg_ms', 0)} ms</span></div>
    <div class="metric"><span class="label">批准/阻止</span><span class="value">{snap.get('cycles', {}).get('approved', 0)} / {snap.get('cycles', {}).get('blocked', 0)}</span></div>
    <div class="metric"><span class="label">运行时长</span><span class="value">{snap.get('uptime_seconds', 0):.0f}s</span></div>
    <div class="metric"><span class="label">健康</span><span class="value"><span class="status {health}"></span>{health}</span></div>
  </div>

  <!-- 信条 -->
  <div class="card">
    <h3>📜 信条对齐</h3>
    <div class="metric"><span class="label">平均分</span><span class="value green">{snap.get('axiom', {}).get('avg_score', 0)}/20</span></div>
    <div class="metric"><span class="label">偏离率</span><span class="value">{snap.get('axiom', {}).get('deviation_rate', 0)}%</span></div>
    <div class="metric"><span class="label">评估次数</span><span class="value">{snap.get('axiom', {}).get('total_evaluations', 0)}</span></div>
    <div class="metric"><span class="label">长期趋势</span><span class="value">{axiom_trend.get('平均对齐分', '-')}</span></div>
    <div class="bar"><div class="bar-fill green" style="width:{min(snap.get('axiom', {}).get('avg_score', 0) * 5, 100)}%"></div></div>
  </div>

  <!-- 规则 -->
  <div class="card">
    <h3>📋 规则 ({len(rules)})</h3>
    {self._render_rules_html(rules[:8])}
  </div>

  <!-- 工具链 -->
  <div class="card">
    <h3>🔧 工具链</h3>
    {self._render_tools_html(snap.get('tools', {}))}
  </div>

  <!-- 分层耗时 -->
  <div class="card">
    <h3>⏱ 分层耗时</h3>
    {self._render_layers_html(snap.get('layers', {}))}
  </div>
</div>

<small>砚识 v0.8 — 运维面板自动生成 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</small>

</body>
</html>"""

    def _render_rules_html(self, rules: list) -> str:
        if not rules:
            return '<div class="rule-row">无规则</div>'
        rows = []
        for r in rules[:8]:
            status_icon = "✓" if r.enabled else "✗"
            rows.append(
                f'<div class="rule-row">'
                f'<span class="id">{status_icon} {r.id}</span>'
                f'<span class="trig">触发{r.trigger_count}次</span>'
                f'</div>'
            )
        if len(rules) > 8:
            rows.append(f'<small>... 还有 {len(rules) - 8} 条规则</small>')
        return "\n".join(rows)

    def _render_tools_html(self, tools: dict) -> str:
        if not tools:
            return '<div class="metric"><span class="label">无工具数据</span></div>'
        rows = []
        for name, stats in tools.items():
            rate = stats.get("success_rate", 0)
            color = "green" if rate > 90 else ("amber" if rate > 70 else "red")
            rows.append(
                f'<div class="metric">'
                f'<span class="label">{name}</span>'
                f'<span class="value {color}">{rate}% ({stats.get("total", 0)}次)</span>'
                f'</div>'
            )
        return "\n".join(rows)

    def _render_layers_html(self, layers: dict) -> str:
        if not layers:
            return '<div class="metric"><span class="label">无分层数据</span></div>'
        rows = []
        for name, stats in layers.items():
            rows.append(
                f'<div class="metric">'
                f'<span class="label">{name}</span>'
                f'<span class="value">{stats.get("avg_ms", 0)}ms (max {stats.get("max_ms", 0)}ms)</span>'
                f'</div>'
            )
        return "\n".join(rows)
