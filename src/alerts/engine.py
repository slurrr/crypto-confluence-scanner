from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging

from ..ranking.ranking import rank_universe, RankedSymbol
from ..data.repository import DataRepository
from ..data.models import MarketHealth
from .types import AlertEvent
from .notifiers import dispatch_alerts
from .state import load_alert_state, save_alert_state, filter_with_state
from ..patterns.rsi_divergence import detect_rsi_divergence_from_bars


log = logging.getLogger(__name__)


def _make_alert_from_ranked(
    r: RankedSymbol,
    market_health: MarketHealth,
    reason: str,
) -> AlertEvent:
    comps = r.confluence.components

    msg = (
        f"CS: {r.confluence.confluence_score:.1f} | "
        f"Trend: {comps.trend:.1f} | Vol: {comps.volatility:.1f} | "
        f"Volu: {comps.volume:.1f} | RS: {comps.rs:.1f} | Pos: {comps.positioning:.1f} | "
        f"Regime: {market_health.regime.upper()} "
        f"(BTC trend {market_health.btc_trend:.1f}, breadth {market_health.breadth:.1f}%)"
    )

    return AlertEvent(
        symbol=r.symbol,
        created_at=datetime.utcnow(),
        reason=reason,
        message=msg,
        confluence_score=r.confluence.confluence_score,
        trend_score=comps.trend,
        vol_score=comps.volatility,
        volume_score=comps.volume,
        rs_score=comps.rs,
        positioning_score=comps.positioning,
        regime_label=market_health.regime,
    )


def _get_bbw_pct(r: RankedSymbol) -> Optional[float]:
    """
    Extract Bollinger Band width (%) from the volatility feature bundle,
    if available.
    """
    try:
        vol_feats = r.volatility.features or {}
    except AttributeError:
        return None

    val = vol_feats.get("bb_width_pct_raw")
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None


def _build_symbol_alerts(
    repo: DataRepository,
    ranked: List[RankedSymbol],
    market_health: MarketHealth,
    cfg: Dict[str, Any],
) -> List[AlertEvent]:
    """
    Build symbol-level alerts of various types:
      - HIGH_CONFLUENCE
      - VOLUME_SPIKE
      - SQUEEZE_CANDIDATE
    """
    alerts_cfg = cfg.get("alerts", {}) or {}
    types_cfg = alerts_cfg.get("types", {}) or {}

    enable_high = bool(types_cfg.get("high_confluence", True))
    enable_vol_spike = bool(types_cfg.get("volume_spike", True))
    enable_squeeze = bool(types_cfg.get("squeeze_candidate", True))
    enable_rsi_div = bool(types_cfg.get("rsi_divergence", True))


    min_cs = float(alerts_cfg.get("min_confluence_score", 60.0))
    min_trend = float(alerts_cfg.get("min_trend_score", 55.0))
    min_vol_score = float(alerts_cfg.get("min_volume_score", 50.0))
    min_pos = float(alerts_cfg.get("min_positioning_score", 50.0))

    vol_spike_min = float(alerts_cfg.get("volume_spike_min_volume_score", 75.0))
    squeeze_max_vol = float(alerts_cfg.get("squeeze_max_vol_score", 40.0))
    squeeze_max_bbw = float(alerts_cfg.get("squeeze_max_bbw_pct", 6.0))

    # Support either a single timeframe or a list of timeframes
    raw_tfs = alerts_cfg.get("rsi_divergence_timeframes")
    if raw_tfs is None:
        # Fallback to old single-string key
        raw_single = alerts_cfg.get("rsi_divergence_timeframe", "4h")
        rsi_tfs = [str(raw_single)]
    elif isinstance(raw_tfs, str):
        rsi_tfs = [raw_tfs]
    else:
        rsi_tfs = [str(tf) for tf in raw_tfs]

    rsi_lookback = int(alerts_cfg.get("rsi_divergence_lookback", 150))
    rsi_pivot_lb = int(alerts_cfg.get("rsi_divergence_pivot_lookback", 3))
    rsi_min_strength = float(alerts_cfg.get("rsi_divergence_min_strength", 5.0))
    rsi_max_bars_from_last = int(
        alerts_cfg.get("rsi_divergence_max_bars_from_last", 1)
    )
    rsi_debug = bool(alerts_cfg.get("rsi_divergence_debug", False))
    rsi_tz = alerts_cfg.get("rsi_divergence_timezone", "UTC")



    require_uptrend_regime = bool(alerts_cfg.get("require_uptrend_regime", False))

    if require_uptrend_regime and market_health.regime not in {"bull", "sideways"}:
        log.info(
            "Global regime is %s; symbol alerts disabled due to require_uptrend_regime",
            market_health.regime,
        )
        return []

    events: List[AlertEvent] = []

    for r in ranked:
        cs = r.confluence.confluence_score
        comps = r.confluence.components

        # --- HIGH_CONFLUENCE ---
        if enable_high:
            if (
                cs >= min_cs
                and comps.trend >= min_trend
                and comps.volume >= min_vol_score
                and comps.positioning >= min_pos
            ):
                events.append(
                    _make_alert_from_ranked(
                        r,
                        market_health=market_health,
                        reason="HIGH_CONFLUENCE",
                    )
                )

        # --- VOLUME_SPIKE ---
        if enable_vol_spike:
            if comps.volume >= vol_spike_min:
                events.append(
                    _make_alert_from_ranked(
                        r,
                        market_health=market_health,
                        reason="VOLUME_SPIKE",
                    )
                )

        # --- SQUEEZE_CANDIDATE ---
        if enable_squeeze:
            bbw_pct = _get_bbw_pct(r)
            if (
                bbw_pct is not None
                and comps.volatility <= squeeze_max_vol
                and bbw_pct <= squeeze_max_bbw
            ):
                events.append(
                    _make_alert_from_ranked(
                        r,
                        market_health=market_health,
                        reason="SQUEEZE_CANDIDATE",
                    )
                )

        # --- RSI_DIVERGENCE (bullish/bearish) across multiple timeframes ---
        if enable_rsi_div:
            for tf in rsi_tfs:
                try:
                    bars = repo.fetch_ohlcv(
                        symbol=r.symbol,
                        timeframe=tf,
                        limit=rsi_lookback,
                    )
                except Exception:
                    bars = []

                if not bars:
                    continue

                div = detect_rsi_divergence_from_bars(
                    bars,
                    timeframe=tf,
                    period=14,
                    lookback=rsi_lookback,
                    pivot_lookback=rsi_pivot_lb,
                    min_strength=rsi_min_strength,
                    max_bars_from_last=rsi_max_bars_from_last,
                    debug=rsi_debug,
                    timezone=rsi_tz,
                )


                if div.kind == "bullish":
                    events.append(
                        _make_alert_from_ranked(
                            r,
                            market_health=market_health,
                            reason=f"RSI_BULLISH_DIVERGENCE_{tf}",
                        )
                    )
                elif div.kind == "bearish":
                    events.append(
                        _make_alert_from_ranked(
                            r,
                            market_health=market_health,
                            reason=f"RSI_BEARISH_DIVERGENCE_{tf}",
                        )
                    )


    return events


def _build_regime_change_event(
    market_health: MarketHealth,
    state: Dict[str, Any],
    alerts_cfg: Dict[str, Any],
) -> Optional[AlertEvent]:
    """
    Create a single REGIME_CHANGE alert if global regime flipped
    since the last run.
    """
    types_cfg = alerts_cfg.get("types", {}) or {}
    if not bool(types_cfg.get("regime_change", True)):
        return None

    prev_regime = state.get("global_regime")
    current_regime = market_health.regime

    # First-time run: just save and don't alert
    if prev_regime is None:
        state["global_regime"] = current_regime
        return None

    if prev_regime == current_regime:
        return None

    # Regime changed – update state and emit alert
    state["global_regime"] = current_regime

    msg = (
        f"Market regime changed from {prev_regime.upper()} to {current_regime.upper()} "
        f"(BTC trend {market_health.btc_trend:.1f}, breadth {market_health.breadth:.1f}%)."
    )

    return AlertEvent(
        symbol="__GLOBAL__",  # special symbol for global alerts
        created_at=datetime.utcnow(),
        reason="REGIME_CHANGE",
        message=msg,
        confluence_score=0.0,
        trend_score=None,
        vol_score=None,
        volume_score=None,
        rs_score=None,
        positioning_score=None,
        regime_label=current_regime,
    )


def run_alert_scan(
    repo: DataRepository,
    cfg: Dict[str, Any],
) -> None:
    alerts_cfg = cfg.get("alerts", {}) or {}
    if not alerts_cfg.get("enabled", True):
        log.info("Alerts are disabled in config")
        return

    # Global state
    state_file = Path(alerts_cfg.get("state_file", "alerts_state.json"))
    state = load_alert_state(state_file)

    # Global health + ranking
    market_health = repo.compute_market_health()

    top_n = int(alerts_cfg.get("scan_top_n", 100))
    ranked = rank_universe(repo, cfg, top_n=top_n)

    if not ranked:
        log.info("No ranked symbols available; no alerts generated")
        save_alert_state(state_file, state)
        return

    # 1) Symbol-level alerts (threshold-based)
    symbol_events = _build_symbol_alerts(repo, ranked, market_health, cfg)

    # 2) Apply per-symbol state filter (CS improvement + cooldown)
    symbol_events = filter_with_state(symbol_events, state, alerts_cfg)

    # 3) Global regime-change alert (doesn't use CS-based state)
    regime_event = _build_regime_change_event(market_health, state, alerts_cfg)

    # Combine
    events: List[AlertEvent] = list(symbol_events)
    if regime_event is not None:
        events.append(regime_event)

    if not events:
        log.info("No alerts after state filters and regime-change check")
        save_alert_state(state_file, state)
        return

    # Persist updated state
    save_alert_state(state_file, state)

    # Fan out to console / Telegram / Discord
    dispatch_alerts(events, cfg)
