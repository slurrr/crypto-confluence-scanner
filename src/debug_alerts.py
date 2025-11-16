from __future__ import annotations

import logging
import yaml

from .data.exchange_api import CcxtExchangeAPI   # <-- same as your ranking script
from .data.repository import DataRepository, DataRepositoryConfig
from .alerts.engine import run_alert_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg = load_config()

    # Same pattern as debug_ranking / debug_daily_report
    exchange_id = cfg.get("exchange", {}).get("id", "binance")
    api = CcxtExchangeAPI(exchange_id)

    timeframes = cfg.get("timeframes", ["1d"])
    repo_cfg = DataRepositoryConfig(timeframes=timeframes)

    repo = DataRepository(api=api, cfg=repo_cfg)

    run_alert_scan(repo, cfg)


if __name__ == "__main__":
    main()
