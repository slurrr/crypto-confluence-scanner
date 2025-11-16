from __future__ import annotations

import logging
from typing import Sequence, Dict, Any

import requests  # make sure 'requests' is in requirements.txt

from .types import AlertEvent

log = logging.getLogger(__name__)


def send_console_alerts(events: Sequence[AlertEvent]) -> None:
    if not events:
        return

    log.info("Sending %d alert(s) to console", len(events))
    for evt in events:
        log.info(
            "[ALERT] %s | %s | CS: %.1f | %s",
            evt.symbol,
            evt.reason,
            evt.confluence_score,
            evt.message,
        )


def send_telegram_alerts(events: Sequence[AlertEvent], cfg: Dict[str, Any]) -> None:
    alerts_cfg = cfg.get("alerts", {}) or {}
    tg_cfg = alerts_cfg.get("telegram", {}) or {}

    if not tg_cfg.get("enabled", False):
        return

    bot_token = tg_cfg.get("bot_token")
    chat_id = tg_cfg.get("chat_id")

    if not bot_token or not chat_id:
        log.warning("Telegram alerts enabled but bot_token or chat_id is missing")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    for evt in events:
        text = (
            f"🚨 *{evt.reason}* on *{evt.symbol}*\n"
            f"CS: {evt.confluence_score:.1f}\n"
            f"{evt.message}"
        )
        try:
            resp = requests.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=5,
            )
            if resp.status_code != 200:
                log.warning(
                    "Telegram send failed (%s): %s",
                    resp.status_code,
                    resp.text[:200],
                )
        except Exception as exc:
            log.warning("Telegram send error: %s", exc)


def send_discord_alerts(events: Sequence[AlertEvent], cfg: Dict[str, Any]) -> None:
    alerts_cfg = cfg.get("alerts", {}) or {}
    dc_cfg = alerts_cfg.get("discord", {}) or {}

    if not dc_cfg.get("enabled", False):
        return

    webhook_url = dc_cfg.get("webhook_url")
    if not webhook_url:
        log.warning("Discord alerts enabled but webhook_url is missing")
        return

    for evt in events:
        content = (
            f"🚨 **{evt.reason}** on **{evt.symbol}**\n"
            f"CS: {evt.confluence_score:.1f}\n"
            f"{evt.message}"
        )
        try:
            resp = requests.post(
                webhook_url,
                json={"content": content},
                timeout=5,
            )
            if resp.status_code >= 300:
                log.warning(
                    "Discord send failed (%s): %s",
                    resp.status_code,
                    resp.text[:200],
                )
        except Exception as exc:
            log.warning("Discord send error: %s", exc)


def dispatch_alerts(events: Sequence[AlertEvent], cfg: Dict[str, Any]) -> None:
    """
    Fan out to the configured notifiers.
    We always log to console; Telegram/Discord are optional.
    """
    if not events:
        return

    send_console_alerts(events)
    send_telegram_alerts(events, cfg)
    send_discord_alerts(events, cfg)
