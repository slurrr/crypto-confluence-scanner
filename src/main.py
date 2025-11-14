from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Sequence

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # we handle this gracefully below

from data.exchange_api import DummyExchangeAPI
from data.repository import DataRepository, DataRepositoryConfig


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
    timeframes: Sequence[str] = cfg.get("timeframes", ["1d"])
    repo_cfg = DataRepositoryConfig(timeframes=timeframes)
    api = DummyExchangeAPI()
    return DataRepository(api=api, cfg=repo_cfg)


def run_scan(config_path: str = "config.yaml") -> None:
    cfg = load_config(config_path)
    repo = build_repository(cfg)

    universe = repo.discover_universe()
    log.info("Universe size: %d symbols", len(universe))

    # Pick first timeframe for now
    timeframe = cfg.get("timeframes", ["1d"])[0]

    for sym in universe:
        try:
            bars = repo.fetch_ohlcv(sym.symbol, timeframe, limit=200)
        except NotImplementedError as exc:
            log.warning("OHLCV fetch not implemented yet for %s: %s", sym.symbol, exc)
            continue

        log.info("Fetched %d bars for %s", len(bars), sym.symbol)

    # Market health placeholder
    health = repo.compute_market_health(universe)
    log.info("Market regime (stub): %s", health.regime)


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
