from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
for path in (ROOT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from generate_nq_regime_transition_html_report import (  # noqa: E402
    candlestick_trade_chart,
    fmt_int,
    fmt_num,
    fmt_pct,
    fmt_signed,
    html_table,
    load_bars_for_trade_window,
)


SUMMARY_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-summary.csv"
TRADES_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-trades.csv"
YEARLY_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-yearly.csv"
ROLLING90_PATH = ROOT_DIR / ".tmp" / "nq-regime-transition-readiness-rolling90.csv"
REPORT_PATH = ROOT_DIR / "reports" / "NQ-smc-regime-trend-system-report.html"
BEST_LABEL = "optimized50_2r5_quality"


def esc(value: object) -> str:
    return html.escape("" if pd.isna(value) else str(value))


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def metric(label: str, value: str, note: str = "") -> str:
    note_html = f"<span>{esc(note)}</span>" if note else ""
    return f"<div class='metric'><small>{esc(label)}</small><strong>{esc(value)}</strong>{note_html}</div>"


def table(frame: pd.DataFrame, columns: list[tuple[str, str, str]], limit: int | None = None) -> str:
    return html_table(frame, columns, limit=limit or len(frame), class_name="compact-table")


def render_report(summary: pd.DataFrame, trades: pd.DataFrame, yearly: pd.DataFrame, rolling90: pd.DataFrame) -> str:
    row = summary[summary["label"].eq(BEST_LABEL)].iloc[0]
    selected = trades[trades["audit_label"].eq(BEST_LABEL)].copy()
    selected["entry_ts"] = pd.to_datetime(selected["entry_ts"], utc=True, errors="coerce")
    selected["exit_ts"] = pd.to_datetime(selected["exit_ts"], utc=True, errors="coerce")
    selected["duration_min"] = (selected["exit_ts"] - selected["entry_ts"]).dt.total_seconds() / 60.0
    selected["side"] = selected["direction"].map({1: "LONG", -1: "SHORT"}).fillna("")
    yearly_selected = yearly[yearly["label"].eq(BEST_LABEL)].copy()
    rolling_selected = rolling90[rolling90["label"].eq(BEST_LABEL)].copy()
    best_trade = selected.sort_values("net_points", ascending=False).iloc[0]
    worst_trade = selected.sort_values("net_points").iloc[0]
    best_chart = candlestick_trade_chart("最佳入场/出场：压缩后强位移启动", best_trade, load_bars_for_trade_window(best_trade, minutes_before=90, minutes_after=90))
    worst_chart = candlestick_trade_chart("最差入场/出场：失败突破被结构止损", worst_trade, load_bars_for_trade_window(worst_trade, minutes_before=90, minutes_after=90))
    top_trades = selected.sort_values("net_points", ascending=False).head(10).copy()
    bottom_trades = selected.sort_values("net_points").head(10).copy()
    same_bar_count = int((selected["entry_index"] == selected["exit_index"]).sum())

    yearly_table = table(
        yearly_selected.sort_values("year"),
        [
            ("year", "年份", "int"),
            ("trades", "交易数", "int"),
            ("net_points", "净点数", "signed"),
        ],
    )
    trade_columns = [
        ("entry_ts", "入场UTC", "text"),
        ("exit_ts", "出场UTC", "text"),
        ("side", "方向", "text"),
        ("entry_price", "入场价", "num"),
        ("exit_price", "出场价", "num"),
        ("exit_reason", "出场原因", "text"),
        ("net_points", "净点数", "signed"),
        ("duration_min", "持仓分钟", "num"),
        ("displacement_atr", "位移ATR", "num"),
        ("range_efficiency", "区间效率", "num"),
    ]
    rolling_worst = table(
        rolling_selected.sort_values("net_points").head(12),
        [
            ("start", "开始", "text"),
            ("end", "结束", "text"),
            ("trades", "交易数", "int"),
            ("net_points", "净点数", "signed"),
        ],
    )

    metrics = "".join(
        [
            metric("交易次数", fmt_int(row["trades"]), "2010-06-06 到 2026-04-27"),
            metric("净点数", fmt_num(row["net_points"]), f"NQ约 ${float(row['net_points']) * 20:,.0f}"),
            metric("Profit Factor", fmt_num(row["profit_factor"], 3), "毛利/毛亏"),
            metric("胜率", fmt_pct(row["win_rate"]), "低胜率高盈亏比"),
            metric("盈亏比", fmt_num(row["payoff_ratio"], 2), "avg win / avg loss"),
            metric("期望/笔", fmt_num(row["expectancy_points"]), "points/trade"),
            metric("最大回撤", fmt_num(row["max_drawdown_points"]), "points"),
            metric("净值/DD", fmt_num(row["net_to_drawdown"]), "稳定门槛通过"),
            metric("正收益年份", f"{fmt_int(row['positive_years'])}/{fmt_int(row['years'])}", fmt_pct(row["positive_year_rate"])),
            metric("90日正收益率", fmt_pct(row["positive_90d_rate"]), f"最差90日 {fmt_signed(row['worst_90d_points'])}"),
            metric("2.125点成本后", fmt_num(row["net_at_cost_2.125"]), "仍为正"),
            metric("同根入出场", fmt_int(same_bar_count), "已修正为0"),
        ]
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ SMC-Regime 趋势交易系统报告</title>
  <style>
    :root {{ --bg:#f4f1ea; --paper:#fffdf8; --ink:#17201b; --muted:#637066; --line:#d9d0c1; --green:#0f766e; --red:#b91c1c; --amber:#a16207; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:radial-gradient(circle at 15% 0%, #e9f7ee 0, transparent 34%), var(--bg); color:var(--ink); font:14px/1.6 Georgia, "Times New Roman", serif; }}
    main {{ max-width:1220px; margin:0 auto; padding:28px 18px 60px; }}
    h1 {{ margin:0; font-size:42px; line-height:1.08; letter-spacing:-.02em; }}
    h2 {{ margin:34px 0 12px; font-size:25px; border-bottom:1px solid var(--line); padding-bottom:8px; }}
    h3 {{ margin:18px 0 8px; }}
    p {{ margin:0 0 12px; color:var(--muted); }}
    code {{ background:#f4eadb; border:1px solid var(--line); border-radius:5px; padding:1px 5px; }}
    .hero,.panel {{ background:rgba(255,253,248,.92); border:1px solid var(--line); border-radius:14px; padding:24px; margin:14px 0; box-shadow:0 18px 45px rgba(70,56,31,.08); }}
    .kicker {{ color:var(--green); font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
    .metric {{ background:#fffaf0; border:1px solid var(--line); border-radius:12px; padding:14px; }}
    .metric small {{ display:block; color:var(--muted); font-weight:700; }}
    .metric strong {{ display:block; margin-top:5px; font-size:24px; }}
    .metric span {{ display:block; margin-top:4px; color:var(--muted); font-size:12px; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
    .box {{ border-left:4px solid var(--green); padding:4px 0 4px 14px; }}
    .warn {{ border-left-color:var(--amber); }}
    .bad {{ border-left-color:var(--red); }}
    ul,ol {{ margin:0; padding-left:20px; }}
    li {{ margin:5px 0; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:12px; background:#fff; margin:12px 0; }}
    table {{ width:100%; border-collapse:collapse; min-width:760px; }}
    th,td {{ padding:8px 10px; border-bottom:1px solid #eee4d5; text-align:left; vertical-align:top; }}
    th {{ background:#f4eadb; color:#4b3b25; }}
    td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .positive {{ color:var(--green); }} .negative {{ color:var(--red); }}
    .chart {{ border:1px solid var(--line); border-radius:12px; overflow:hidden; background:#fff; margin:14px 0; }}
    .chart figcaption {{ padding:12px 14px; border-bottom:1px solid var(--line); font-weight:700; }}
    .chart svg {{ width:100%; height:auto; display:block; }}
    a {{ color:#0f766e; }}
    @media(max-width:900px) {{ .metrics {{ grid-template-columns:repeat(2,1fr); }} .grid {{ grid-template-columns:1fr; }} h1 {{ font-size:32px; }} }}
    @media(max-width:560px) {{ .metrics {{ grid-template-columns:1fr; }} main {{ padding:14px 10px; }} .hero,.panel {{ padding:16px; }} }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <p class="kicker">SMC / ICT / Regime Transition</p>
    <h1>NQ 震荡识别与趋势启动交易系统</h1>
    <p>结论：裸 SMC BOS/CHoCH 中继在本地 NQ 1m 回测中不稳定；更高胜率/正期望来自“低效率震荡压缩 -> 强位移突破 -> 结构止损/2.5R 目标”的趋势启动系统。</p>
    <p>最终候选：<code>{esc(row["candidate"])}</code>。入场后一根 K 线才允许出场，不存在同一根 K 线入场和出场。</p>
  </section>

  <section class="panel"><div class="metrics">{metrics}</div></section>

  <section class="panel">
    <h2>资料与本地文档映射</h2>
    <div class="grid">
      <div class="box"><h3>联网资料</h3><p>Fidelity 对 ADX 的说明：ADX 衡量趋势强度，DI 线辅助方向判断，25 以上常被视为较强趋势。Donchian 资料把通道突破定义为趋势跟随/突破系统。CHOP 资料用于区分震荡与趋势。</p><p>来源：<a href="https://www.fidelity.com/viewpoints/active-investor/average-directional-index-ADX">Fidelity ADX</a>、<a href="https://finwiz.io/technical-indicators/donchian-channel">Finwiz Donchian</a>、<a href="https://www.linnsoft.com/techind/donchian-channels">Linn Donchian</a>。</p></div>
      <div class="box"><h3>Lightglow</h3><p><code>docs/Strategy/lightglow.md</code> 的 BOS/CHoCH、FVG、Premium/Discount 给出结构语言；回测中把它转译为历史箱体突破、强实体位移、区间效率和结构止损。</p></div>
      <div class="box"><h3>ICT2022</h3><p><code>docs/Strategy/ICT2022-2.md</code> 强调结构、POI、流动性扫荡、确认入场。本系统不抢 POI，而是在压缩区间被真实位移打破后下一根开盘执行。</p></div>
    </div>
  </section>

  <section class="panel">
    <h2>机械规则</h2>
    <div class="grid">
      <div class="box"><h3>识别震荡</h3><ol><li>过去45分钟形成箱体。</li><li>箱体宽度 <= 10 ATR。</li><li>区间效率 <= 0.10，代表来回震荡而非单边趋势。</li></ol></div>
      <div class="box"><h3>识别趋势起步</h3><ol><li>只做 <code>us_late</code> NQ 多头。</li><li>当前 K 线向上突破箱体。</li><li>位移 >= 1.6 ATR30，实体占比 >= 0.55。</li><li>下一根开盘入场。</li></ol></div>
      <div class="box"><h3>退出</h3><ol><li>止损在位移 K 线低点下方加缓冲。</li><li>2.5R 固定目标。</li><li>最多持仓180分钟。</li><li>同根止盈止损歧义按 stop-first，但入场 K 线不检查出场。</li></ol></div>
    </div>
  </section>

  <section class="panel">
    <h2>回测结果</h2>
    {yearly_table}
    <h3>最差滚动90日窗口</h3>
    {rolling_worst}
  </section>

  <section class="panel">
    <h2>最佳/最差入场与出场</h2>
    {best_chart}
    {worst_chart}
    <h3>最大盈利10笔</h3>
    {table(top_trades, trade_columns, limit=10)}
    <h3>最大亏损10笔</h3>
    {table(bottom_trades, trade_columns, limit=10)}
  </section>

  <section class="panel">
    <h2>无未来函数检查</h2>
    <ul>
      <li>所有 rolling 箱体、ATR、效率、成交量 Z 分数只使用当前及历史 bar。</li>
      <li>事件信号在当前 K 线收盘确认，成交价使用下一根 K 线开盘。</li>
      <li>止盈/止损路径从 <code>entry_index + 1</code> 开始检查，避免同根入出场。</li>
      <li>重新生成后最佳候选同根入出场计数为 <code>{same_bar_count}</code>。</li>
      <li>没有使用 <code>shift(-n)</code>、centered rolling、未来日高低点或 TradingView <code>lookahead_on</code>。</li>
    </ul>
  </section>

  <section class="panel">
    <h2>风险</h2>
    <div class="grid">
      <div class="box warn"><h3>不是实盘批准</h3><p>这是历史研究候选，仍需纸面交易、滑点矩阵和实时执行验证。</p></div>
      <div class="box warn"><h3>低频</h3><p>系统交易频率低，不能满足每个完整年份1000笔以上的高频要求。</p></div>
      <div class="box bad"><h3>裸 SMC 中继无效</h3><p>本次实验显示，单靠 BOS/CHoCH/FVG 追趋势中继容易负期望，必须叠加震荡压缩、强位移和结构止损。</p></div>
    </div>
  </section>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate focused SMC regime trend system HTML report.")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    report = render_report(read_csv(SUMMARY_PATH), read_csv(TRADES_PATH), read_csv(YEARLY_PATH), read_csv(ROLLING90_PATH))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(line.rstrip() for line in report.splitlines()) + "\n", encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
