from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Sequence

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # we handle this gracefully below

from .data.exchange_api import CcxtExchangeAPI
from .data.repository import DataRepository, DataRepositoryConfig
from .pipeline.score_pipeline import compile_score_bundles_for_universe 
from .data.market_health import compute_market_health
from .scoring.regimes import classify_regime
from .ranking.ranking import RankingOutput, rank_score_bundles
from .reports.daily_report import generate_daily_report


log = logging.getLogger(__name__)


def load_config(path: str | Path) -> Dict[str, Any]:
    """
    Load a YAML config file.

    If YAML or the file is missing, fall back to a tiny built-in default
    so you can still run the script during early development.
    """
    path = Path(path)

    if yaml is None or not path.exists():
        log.warning(
            "Config file %s not found or PyYAML not installed; using minimal defaults.",
            path,
        )
        return {
            "timeframes": ["1d"],
            "universe": {
                "symbols": ["BTCUSDT", "ETHUSDT"],
            },
        }

    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    return cfg


def build_repository(cfg: Dict[str, Any]) -> DataRepository:
    data_cfg = cfg.get("data_repository", {})
    exchange_cfg = cfg.get("exchange", {})
    deriv_cfg = exchange_cfg.get("derivatives", {})

    timeframes = data_cfg.get("timeframes", ["1d"])
    max_symbols = data_cfg.get("max_symbols")

    exchange_id = exchange_cfg.get("id", "binance")
    deriv_exchange_id = deriv_cfg.get("id")

    repo_cfg = DataRepositoryConfig(
        timeframes=timeframes,
        max_symbols=max_symbols,
    )

    api = CcxtExchangeAPI(
        exchange_id=exchange_id,
        derivatives_exchange_id=deriv_exchange_id,
    )
    return DataRepository(api=api, cfg=repo_cfg)



def run_scan(config_path: str = "config.yaml") -> Dict[str, RankingOutput]:
    cfg = load_config(config_path)
    repo = build_repository(cfg)

    # Discover the tradeable universe via the repository
    universe = repo.discover_universe()

    # Pick the first timeframe from data_repository.timeframes as the working TF
    timeframes = cfg.get("data_repository", {}).get("timeframes", ["1d"])

    # Respect max_symbols (ranking.max_symbols wins, then data_repository.max_symbols)
    max_symbols = (cfg.get("data_repository", {}).get("max_symbols"))
    if max_symbols:
        universe = universe[: max_symbols]
    
    symbols = [u.symbol for u in universe]
    log.info(
        "Scanning %d symbols on timeframes %s",
        len(symbols),
        ", ".join(timeframes),
    )
    
    derivatives_by_symbol = repo.fetch_derivatives_for_symbols(symbols)
    '''
    log.info("Sample derivatives (first 3): %s", {
        s: derivatives_by_symbol.get(s)
        for s in symbols[:3]
    })
    '''

    # Market health (regime detection)
    health = compute_market_health(repo, universe)
    #regime = classify_regime(health, cfg.get("regimes", {}))
    log.info("Market regime: %s", health.regime)

    results_by_timeframe: Dict[str, RankingOutput] = {}

    # 🔗 Call your pipeline
    for timeframe in timeframes:
        log.info("=== RUNNING TIMEFRAME: %s ===", timeframe)
        try:
            bundles = compile_score_bundles_for_universe(
                repo=repo,
                symbols=symbols,
                timeframe=timeframe,
                cfg=cfg,
                regime=health.regime,
                derivatives_by_symbol=derivatives_by_symbol, 
                # weights={"trend_score": 1.0},  # plug in from config if you add weights
                # universe_returns=...,          # plug in later if/when you have it
            )
        except Exception as e:
            log.exception("Error while running timeframe %s: %s", timeframe, e)
            raise

        ranking_result = rank_score_bundles(
            bundles,
            cfg,
            top_n=cfg.get("reports", {}).get("top_n"),
            apply_filtering=True,
        )
        results_by_timeframe[timeframe] = ranking_result

        filtered = ranking_result.filtered
        log.info(
            "Timeframe %s: kept %d/%d symbols after filters",
            timeframe,
            len(filtered),
            len(bundles),
        )

        top_confluence = ranking_result.leaderboards.get("top_confluence", [])
        if not top_confluence:
            log.info("No symbols passed ranking for timeframe %s", timeframe)
            continue

        preview = top_confluence[: min(len(top_confluence), 5)]
        log.info(
            "Top symbols for %s: %s",
            timeframe,
            [b.symbol for b in preview],
        )

        for b in preview:
            log.info(
                "Score %s %s -> confluence=%.2f, confidence=%s scores=%s",
                b.symbol,
                b.timeframe,
                b.confluence_score,
                b.confidence,
                b.scores,
            )

    if timeframes:
        first_tf = timeframes[0]
        first_output = results_by_timeframe.get(first_tf)
        if first_output is not None:
            generate_daily_report(
                repo,
                cfg,
                ranking_output=first_output,
                market_health=health,
            )

    return results_by_timeframe


def main() -> None:
    parser = argparse.ArgumentParser(description="Confluence Score Crypto Scanner")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config file (default: config.yaml)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_scan(args.config)


if __name__ == "__main__":
    main()
