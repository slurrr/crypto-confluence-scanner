from __future__ import annotations

import logging

from .main import load_config, build_repository
from .reports.daily_report import generate_daily_report


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = load_config("config.yaml")
    repo = build_repository(cfg)

    generate_daily_report(repo, cfg)


if __name__ == "__main__":
    main()
