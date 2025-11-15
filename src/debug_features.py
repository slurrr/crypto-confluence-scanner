from __future__ import annotations

import logging
from typing import Any, Dict

from .main import load_config, build_repository
from .features.trend import (
    compute_ma_alignment,
    compute_trend_persistence,
    compute_distance_from_ma,
    compute_ma_slope_percent,
)
from .features.volatility import (
    compute_atr_percent,
    compute_bb_width_percent,
    compute_volatility_contraction_ratio,
)


def compute_basic_features(cfg: Dict[str, Any]) -> None:
    repo = build_repository(cfg)
    universe = repo.discover_universe()
    if not universe:
        logging.error("Universe is empty; check your exchange/symbol config.")
        return

    symbol = universe[0].symbol
    timeframe = cfg.get("timeframes", ["1d"])[0]

    logging.info("Fetching bars for %s (%s)...", symbol, timeframe)
    bars = repo.fetch_ohlcv(symbol, timeframe, limit=200)

    if not bars:
        logging.error("No bars returned for %s", symbol)
        return

    trend_features = {
        "ma_alignment_20_50": compute_ma_alignment(bars, 20, 50),
        "trend_persistence_20": compute_trend_persistence(bars, 20),
        "distance_from_ma_50_pct": compute_distance_from_ma(bars, 50),
        "ma50_slope_pct_5": compute_ma_slope_percent(bars, 50, 5),
    }

    vol_features = {
        "atr_pct_14": compute_atr_percent(bars, 14),
        "bb_width_pct_20": compute_bb_width_percent(bars, 20, 2.0),
        "vol_contraction_ratio": compute_volatility_contraction_ratio(bars, 60, 20),
    }

    logging.info("Trend features for %s: %s", symbol, trend_features)
    logging.info("Volatility features for %s: %s", symbol, vol_features)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = load_config("config.yaml")
    compute_basic_features(cfg)


if __name__ == "__main__":
    main()
