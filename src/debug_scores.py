from __future__ import annotations

import logging
from typing import Any, Dict

from .main import load_config, build_repository
from .scoring.trend_score import compute_trend_score
from .scoring.volatility_score import compute_volatility_score
from .scoring.volume_score import compute_volume_score
from .scoring.rs_score import compute_relative_strength_score


def compute_scores_for_first_symbol(cfg: Dict[str, Any]) -> None:
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

    trend = compute_trend_score(bars)
    vol = compute_volatility_score(bars)
    volu = compute_volume_score(bars)
    rs = compute_relative_strength_score(bars)

    logging.info("Trend score for %s: %.2f", symbol, trend.score)
    logging.info("Trend features: %s", trend.features)

    logging.info("Volatility score for %s: %.2f", symbol, vol.score)
    logging.info("Volatility features: %s", vol.features)

    logging.info("Volume score for %s: %.2f", symbol, volu.score)
    logging.info("Volume features: %s", volu.features)

    logging.info("RS score for %s: %.2f", symbol, rs.score)
    logging.info("RS features: %s", rs.features)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = load_config("config.yaml")
    compute_scores_for_first_symbol(cfg)


if __name__ == "__main__":
    main()
