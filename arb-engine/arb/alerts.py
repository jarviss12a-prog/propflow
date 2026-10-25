from __future__ import annotations

import logging
import os

import httpx

from .models import Opportunity
from .odds import fmt_american

log = logging.getLogger(__name__)


def format_opp(o: Opportunity) -> str:
    when = o.start.strftime("%a %H:%M UTC") if o.start else "time ?"
    lines = [
        f"ARB {o.roi * 100:.2f}%  profit ${o.profit:.2f} on ${o.total_cost:.2f}",
        f"{o.sport.upper()}  {o.away} @ {o.home}  ({when})",
        f"{o.describe_market()}",
    ]
    for f in o.fills:
        side = {"home": o.home, "away": o.away}.get(f.outcome, f.outcome)
        stake = f.contracts * f.price
        fee = f"  fee ${f.fee:.2f}" if f.fee else ""
        lines.append(
            f"  {f.venue:<11} {side:<22} {fmt_american(f.price):>5} ({f.price * 100:.1f}c)  "
            f"stake ${stake:,.2f}  -> pays ${f.contracts:,.2f}{fee}"
        )
        if f.url:
            lines.append(f"      {f.url}")
    for w in o.warnings:
        lines.append(f"  ! {w}")
    return "\n".join(lines)


class Alerter:
    def __init__(self) -> None:
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    async def send(self, client: httpx.AsyncClient, opp: Opportunity) -> None:
        text = format_opp(opp)
        print(text, "\n", flush=True)
        if not (self.token and self.chat_id):
            return
        try:
            resp = await client.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("telegram alert failed: %s", e)
