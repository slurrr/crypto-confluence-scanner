from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

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
    Apply basic filters to a ranked symbol.

    `symbol_obj` is expected to have:
      - confluence.components.(trend/volatility/volume/rs)
      - volatility.features["atr_pct_raw"], ["bb_width_pct_raw"]

    Returns:
      (passed: bool, reasons_if_failed: List[str])
    """
    reasons: List[str] = []

    comps = symbol_obj.confluence.components

    if comps.trend < cfg.min_trend_score:
        reasons.append(f"trend<{cfg.min_trend_score}")
    if comps.rs < cfg.min_rs_score:
        reasons.append(f"rs<{cfg.min_rs_score}")
    if comps.volume < cfg.min_volume_score:
        reasons.append(f"volume<{cfg.min_volume_score}")
    if comps.volatility < cfg.min_volatility_score:
        reasons.append(f"volatility<{cfg.min_volatility_score}")

    vol_feats = getattr(symbol_obj, "volatility", None)
    if vol_feats is not None:
        feats = vol_feats.features or {}
        atr = feats.get("atr_pct_raw")
        bbw = feats.get("bb_width_pct_raw")

        if cfg.max_atr_pct is not None and atr is not None:
            if atr > cfg.max_atr_pct:
                reasons.append(f"atr_pct>{cfg.max_atr_pct}")

        if cfg.max_bb_width_pct is not None and bbw is not None:
            if bbw > cfg.max_bb_width_pct:
                reasons.append(f"bb_width_pct>{cfg.max_bb_width_pct}")

    passed = len(reasons) == 0
    return passed, reasons


def apply_filters(
    symbols: List[Any],
    raw_cfg: Dict[str, Any] | None,
) -> List[Any]:
    """
    Filter a list of ranked symbol objects according to config.

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
            # For now we silently drop. You could log reasons here if desired.
            # Example:
            # print(f"[FILTER] Dropping {s.symbol}: {', '.join(reasons)}")
            pass
    logger.info(
        "[filters] %d symbols passed filters, %d dropped",
        len(kept),
    )
    return kept
