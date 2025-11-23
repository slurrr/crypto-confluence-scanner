from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from ..data.models import MarketHealth, ScoreBundle
from ..pipeline.score_pipeline import compile_score_bundles_for_universe
from ..ranking.ranking import RankingOutput, rank_score_bundles
from ..scoring.regimes import classify_regime

log = logging.getLogger(__name__)


def _fmt_num(x: Any, nd: int = 2) -> str:
    if x is None:
        return ""
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return str(x)


def _extract_extras(bundle: ScoreBundle) -> Dict[str, float]:
    features = bundle.features or {}
    return {
        "atr_pct": features.get("volatility_atr_pct_14"),
        "bb_width_pct": features.get("volatility_bb_width_pct_20"),
        "ret_1m": features.get("rs_ret_20_pct"),
        "ret_3m": features.get("rs_ret_60_pct"),
        "ret_6m": features.get("rs_ret_120_pct"),
    }


def format_console_table(
    ranked: Sequence[ScoreBundle],
    market_health: Optional[MarketHealth] = None,
) -> str:
    lines: list[str] = []

    if market_health is not None:
        lines.append(
            f"Market Regime: {market_health.regime.upper()} "
            f"(BTC trend: {_fmt_num(market_health.btc_trend, 1)}, "
            f"breadth: {_fmt_num(market_health.breadth, 1)}%)"
        )
        lines.append("")

    header = (
        "Rank  Symbol       CS    Trend   Vol   Volu    RS    Pos   ATR%   BBW%    1M%    3M%    6M%"
    )
    sep = "-" * len(header)
    lines.append(sep)
    lines.append(header)
    lines.append(sep)

    for idx, bundle in enumerate(ranked, start=1):
        scores = bundle.scores or {}
        extras = _extract_extras(bundle)

        line = (
            f"{idx:>4}  "
            f"{bundle.symbol:<10}  "
            f"{_fmt_num(bundle.confluence_score, 1):>5}  "
            f"{_fmt_num(scores.get('trend_score'), 1):>7}  "
            f"{_fmt_num(scores.get('volatility_score'), 1):>5}  "
            f"{_fmt_num(scores.get('volume_score'), 1):>5}  "
            f"{_fmt_num(scores.get('rs_score'), 1):>6}  "
            f"{_fmt_num(scores.get('positioning_score'), 1):>6}  "
            f"{_fmt_num(extras['atr_pct'], 1):>6}  "
            f"{_fmt_num(extras['bb_width_pct'], 1):>6}  "
            f"{_fmt_num(extras['ret_1m'], 1):>6}  "
            f"{_fmt_num(extras['ret_3m'], 1):>6}  "
            f"{_fmt_num(extras['ret_6m'], 1):>6}"
        )
        lines.append(line)

    lines.append(sep)
    return "\n".join(lines)


def build_markdown_report(
    ranked: Sequence[ScoreBundle],
    cfg: Dict[str, Any],
    run_dt: datetime,
    market_health: Optional[MarketHealth] = None,
) -> str:
    timeframes = cfg.get("data_repository", {}).get(
        "timeframes", cfg.get("timeframes", ["1d"])
    )
    timeframe = timeframes[0] if timeframes else "1d"
    exchange_id = cfg.get("exchange", {}).get("id", "unknown")
    top_n = len(ranked)

    lines: list[str] = []

    lines.append("# Daily Confluence Report")
    lines.append("")
    lines.append(f"**Date:** {run_dt.strftime('%Y-%m-%d %H:%M UTC')}  ")
    lines.append(f"**Timeframe:** {timeframe}  ")
    lines.append(f"**Exchange:** `{exchange_id}`  ")
    lines.append(f"**Top Symbols:** {top_n}")
    lines.append("")

    if market_health is not None:
        lines.append("## Market Regime")
        lines.append("")
        lines.append(f"- **Regime:** **{market_health.regime.upper()}**")
        lines.append(
            f"- **BTC Trend Score:** {_fmt_num(market_health.btc_trend, 1)}"
        )
        lines.append(
            f"- **Breadth:** {_fmt_num(market_health.breadth, 1)}% of universe in uptrend"
        )
        lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("**Legend**")
    lines.append("")
    lines.append("- **CS** = Confluence Score (0-100)")
    lines.append("- **Trend / Vol / Volu / RS / Pos** = component scores (0-100)")
    lines.append("- **ATR%** = ATR(14) as % of price")
    lines.append("- **BBW%** = Bollinger Band width as % of mid")
    lines.append("- **1M/3M/6M%** = approximate returns over 20/60/120 bars")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append(
        "| # | Symbol | CS | Trend | Vol | Volu | RS | Pos | ATR% | BBW% | 1M% | 3M% | 6M% |"
    )
    lines.append(
        "|:-:|:------:|:--:|:-----:|:---:|:----:|:--:|:---:|:----:|:----:|:---:|:---:|:---:|"
    )

    for idx, bundle in enumerate(ranked, start=1):
        scores = bundle.scores or {}
        extras = _extract_extras(bundle)

        row = (
            f"| {idx} "
            f"| {bundle.symbol} "
            f"| {_fmt_num(bundle.confluence_score, 1)} "
            f"| {_fmt_num(scores.get('trend_score'), 1)} "
            f"| {_fmt_num(scores.get('volatility_score'), 1)} "
            f"| {_fmt_num(scores.get('volume_score'), 1)} "
            f"| {_fmt_num(scores.get('rs_score'), 1)} "
            f"| {_fmt_num(scores.get('positioning_score'), 1)} "
            f"| {_fmt_num(extras['atr_pct'], 1)} "
            f"| {_fmt_num(extras['bb_width_pct'], 1)} "
            f"| {_fmt_num(extras['ret_1m'], 1)} "
            f"| {_fmt_num(extras['ret_3m'], 1)} "
            f"| {_fmt_num(extras['ret_6m'], 1)} |"
        )
        lines.append(row)

    lines.append("")
    lines.append("> _Generated by crypto-confluence-scanner_")
    lines.append("")

    return "\n".join(lines)


def write_markdown_report(
    ranked: Sequence[ScoreBundle],
    cfg: Dict[str, Any],
    run_dt: datetime,
    market_health: Optional[MarketHealth],
    output_dir: str | Path = "reports",
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fname = f"daily_report_{run_dt.strftime('%Y-%m-%d_%H-%M')}.md"
    out_path = output_dir / fname

    content = build_markdown_report(ranked, cfg, run_dt, market_health)
    out_path.write_text(content, encoding="utf-8")

    return out_path


def generate_daily_report(
    repo,
    cfg: Dict[str, Any],
    *,
    ranking_output: RankingOutput | None = None,
    ranked_bundles: Sequence[ScoreBundle] | None = None,
    market_health: Optional[MarketHealth] = None,
) -> None:
    run_dt = datetime.utcnow()
    reports_cfg = cfg.get("reports", {})
    top_n = int(reports_cfg.get("top_n", 10))
    output_dir = reports_cfg.get("output_dir", "reports")

    if market_health is None:
        market_health = repo.compute_market_health()
    regime = classify_regime(market_health, cfg.get("regimes", {}))

    if ranking_output is None:
        if ranked_bundles is None:
            timeframes = cfg.get("data_repository", {}).get("timeframes", ["1d"])
            timeframe = timeframes[0]

            universe = repo.discover_universe()
            max_symbols = (
                cfg.get("ranking", {}).get("max_symbols")
                or cfg.get("data_repository", {}).get("max_symbols")
            )
            if max_symbols:
                universe = universe[:max_symbols]

            symbols = [u.symbol for u in universe]
            derivatives_by_symbol = repo.fetch_derivatives_for_symbols(symbols)

            ranked_bundles = compile_score_bundles_for_universe(
                repo=repo,
                symbols=symbols,
                timeframe=timeframe,
                cfg=cfg,
                regime=regime,
                derivatives_by_symbol=derivatives_by_symbol,
            )

        ranking_output = rank_score_bundles(
            ranked_bundles,
            cfg,
            top_n=top_n,
            apply_filtering=True,
        )

    ranked = list(ranking_output.leaderboards.get("top_confluence", []))[:top_n]

    if not ranked:
        log.warning("No symbols passed filters / ranking for daily report.")
        return

    table = format_console_table(ranked, market_health)
    print("\n" + table + "\n")

    out_path = write_markdown_report(
        ranked,
        cfg,
        run_dt,
        market_health,
        output_dir=output_dir,
    )
    log.info("Wrote daily report to %s", out_path)
