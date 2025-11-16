from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

from .types import AlertEvent

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def load_alert_state(path: Path) -> Dict[str, Any]:
    """
    Load alert state from disk. If file doesn't exist or is invalid,
    return a fresh empty state.
    """
    if not path.exists():
        return {"symbols": {}}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # corrupt or unreadable -> start fresh
        return {"symbols": {}}


def save_alert_state(path: Path, state: Dict[str, Any]) -> None:
    """
    Atomically write alert state to disk.
    """
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    tmp.replace(path)


def filter_with_state(
    events: List[AlertEvent],
    state: Dict[str, Any],
    alerts_cfg: Dict[str, Any],
) -> List[AlertEvent]:
    """
    Dedupe symbol-level alerts using per-symbol state:

      - min_cs_delta: only alert if CS improved sufficiently vs last alert
      - cooldown_minutes: minimum time between alerts per symbol
    """
    symbols_state: Dict[str, Any] = state.setdefault("symbols", {})

    min_cs_delta = float(alerts_cfg.get("min_cs_delta", 3.0))
    cooldown_minutes = int(alerts_cfg.get("cooldown_minutes", 60))

    now = datetime.utcnow()
    keep: List[AlertEvent] = []

    for evt in events:
        sym_state = symbols_state.get(evt.symbol, {})

        last_cs = sym_state.get("last_cs")
        last_ts_str = sym_state.get("last_ts")
        last_ts = None
        if last_ts_str:
            try:
                last_ts = datetime.strptime(last_ts_str, ISO_FORMAT)
            except Exception:
                last_ts = None

        # Cooldown check
        if last_ts is not None:
            if now - last_ts < timedelta(minutes=cooldown_minutes):
                # still on cooldown -> skip
                continue

        # Minimum CS improvement check
        if last_cs is not None:
            if evt.confluence_score < last_cs + min_cs_delta:
                continue

        # Passed filters -> keep & update state
        keep.append(evt)
        symbols_state[evt.symbol] = {
            "last_cs": evt.confluence_score,
            "last_ts": now.strftime(ISO_FORMAT),
        }

    return keep
