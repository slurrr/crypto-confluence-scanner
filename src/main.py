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
    timeframes = cfg["data_repository"].get("timeframes", ["1d"])
    max_symbols = cfg["data_repository"].get("max_symbols", None)
    repo_cfg = DataRepositoryConfig(
        timeframes=timeframes,
        max_symbols=max_symbols,
    )

    exchange_cfg = cfg.get("exchange", {})
    exchange_id = exchange_cfg.get("id", "binance")
    symbols = exchange_cfg.get("symbols")  # e.g. ["BTC/USDT", "ETH/USDT"]

    deriv_cfg = exchange_cfg.get("derivatives", {})
    deriv_exchange_id = deriv_cfg.get("id")  # e.g. "binanceusdm"

    api = CcxtExchangeAPI(
        exchange_id=exchange_id,
        symbols=symbols,
        derivatives_exchange_id=deriv_exchange_id,
    )
    return DataRepository(api=api, cfg=repo_cfg)



def run_scan(config_path: str = "config.yaml") -> None:
    cfg = load_config(config_path)
    repo = build_repository(cfg)

    # Discover the tradeable universe via the repository
    universe = repo.discover_universe()
    logging.info("Universe size: %d symbols", len(universe))

    # Pick the first timeframe from data_repository.timeframes as the working TF
    timeframe = cfg["data_repository"].get("timeframes", ["1d"])[0]

    # Respect max_symbols (ranking.max_symbols wins, then data_repository.max_symbols)
    max_symbols = (
        cfg.get("ranking", {}).get("max_symbols")
        or cfg["data_repository"].get("max_symbols")
    )
    if max_symbols:
        universe = universe[: max_symbols]

    symbols = [u.symbol for u in universe]

    # 🔗 Call your pipeline
    bundles = compile_score_bundles_for_universe(
        repo=repo,
        symbols=symbols,
        timeframe=timeframe,
        # universe_returns=...,          # plug in later if/when you have it
        # derivatives_by_symbol=...,     # plug in later for futures/positioning
        # weights={"trend_score": 1.0},  # plug in from config if you add weights
    )

    # Example: sort bundles by confluence score (highest first)
    bundles.sort(key=lambda b: b.confluence_score, reverse=True)

    for b in bundles:
        logging.info(
            "Score %s %s -> confluence=%.2f scores=%s",
            b.symbol,
            b.timeframe,
            b.confluence_score,
            b.scores,
        )

    # Keep using repo for market health (or any other high-level metrics)
    health = repo.compute_market_health(universe)
    logging.info("Market regime (stub): %s", health.regime)




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
