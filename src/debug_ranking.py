from __future__ import annotations

import logging
from typing import Any, Dict

from .main import load_config, build_repository
from .ranking.ranking import rank_universe


def run_ranking(cfg: Dict[str, Any]) -> None:
    repo = build_repository(cfg)
    ranked = rank_universe(repo, cfg, top_n=10)

    if not ranked:
        logging.warning("No ranked symbols produced.")
        return

    logging.info("Top %d symbols by Confluence Score:", len(ranked))
    for idx, r in enumerate(ranked, start=1):
        cs = r.confluence.confluence_score
        comps = r.confluence.components
        logging.info(
            "%2d) %-12s CS: %6.2f | Trend: %6.2f | Vol: %6.2f | Volu: %6.2f | RS: %6.2f",
            idx,
            r.symbol,
            cs,
            comps.trend,
            comps.volatility,
            comps.volume,
            comps.rs,
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = load_config("config.yaml")
    run_ranking(cfg)


if __name__ == "__main__":
    main()
