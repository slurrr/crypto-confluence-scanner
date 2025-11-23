from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ..data.models import ScoreBundle

import logging
logger = logging.getLogger(__name__)


@dataclass
class FilterConfig:
    min_trend_score: float = 0.0
    min_rs_score: float = 0.0
    min_volume_score: float = 0.0
    min_volatility_score: float = 0.0
    max_atr_pct: float | None = None
    max_bb_width_pct: float | None = None


def parse_filter_config(raw: Dict[str, Any] | None) -> FilterConfig:
    raw = raw or {}
    return FilterConfig(
        min_trend_score=float(raw.get("min_trend_score", 0.0)),
        min_rs_score=float(raw.get("min_rs_score", 0.0)),
        min_volume_score=float(raw.get("min_volume_score", 0.0)),
        min_volatility_score=float(raw.get("min_volatility_score", 0.0)),
        max_atr_pct=(
            float(raw["max_atr_pct"]) if "max_atr_pct" in raw else None
        ),
        max_bb_width_pct=(
            float(raw["max_bb_width_pct"]) if "max_bb_width_pct" in raw else None
        ),
    )


def symbol_passes_filters(symbol_obj: Any, cfg: FilterConfig) -> Tuple[bool, List[str]]:
    """
    Apply basic filters to a scored symbol (ScoreBundle).

    Expects `symbol_obj` to expose:
      - .scores with keys: trend_score, rs_score, volume_score, volatility_score
      - .features with volatility/volume context (ATR%, BB width)

    Returns (passed, reasons_if_failed)
    """
    reasons: List[str] = []

    scores = getattr(symbol_obj, "scores", {}) or {}

    trend_val = float(scores.get("trend_score", 0.0))
    rs_val = float(scores.get("rs_score", 0.0))
    volume_val = float(scores.get("volume_score", 0.0))
    volatility_val = float(scores.get("volatility_score", 0.0))

    if trend_val < cfg.min_trend_score:
        reasons.append(f"trend<{cfg.min_trend_score}")
    if rs_val < cfg.min_rs_score:
        reasons.append(f"rs<{cfg.min_rs_score}")
    if volume_val < cfg.min_volume_score:
        reasons.append(f"volume<{cfg.min_volume_score}")
    if volatility_val < cfg.min_volatility_score:
        reasons.append(f"volatility<{cfg.min_volatility_score}")

    def _first_feature(obj: Dict[str, Any], keys: List[str]) -> Any:
        for k in keys:
            if k in obj:
                return obj[k]
        return None

    features = getattr(symbol_obj, "features", {}) or {}

    # Prefer canonical feature keys but keep legacy aliases for flexibility.
    atr = _first_feature(
        features,
        ["volatility_atr_pct_14", "atr_pct_raw", "atr_pct"],
    )
    bbw = _first_feature(
        features,
        ["volatility_bb_width_pct_20", "bb_width_pct_raw", "bb_width_pct"],
    )

    if cfg.max_atr_pct is not None and atr is not None:
        try:
            if float(atr) > cfg.max_atr_pct:
                reasons.append(f"atr_pct>{cfg.max_atr_pct}")
        except (TypeError, ValueError):
            reasons.append("atr_pct_unusable")

    if cfg.max_bb_width_pct is not None and bbw is not None:
        try:
            if float(bbw) > cfg.max_bb_width_pct:
                reasons.append(f"bb_width_pct>{cfg.max_bb_width_pct}")
        except (TypeError, ValueError):
            reasons.append("bb_width_pct_unusable")

    passed = len(reasons) == 0
    return passed, reasons


def apply_filters(
    symbols: List[ScoreBundle],
    raw_cfg: Dict[str, Any] | None,
) -> List[Any]:
    """
    Filter a list of ScoreBundle objects according to config.

    Returns only those that pass.
    """
    logger.info(
        "[filters] received %d symbols",
        len(symbols)
    )

    cfg = parse_filter_config(raw_cfg)
    kept: List[Any] = []

    for s in symbols:
        passed, reasons = symbol_passes_filters(s, cfg)
        if passed:
            kept.append(s)
        else:
            logger.debug(
                "[filters] dropping %s: %s",
                getattr(s, "symbol", "<unknown>"),
                ", ".join(reasons),
            )
    logger.info(
        "[filters] %d symbols passed filters, %d dropped",
        len(kept),
        len(symbols) - len(kept),
    )
    return kept
