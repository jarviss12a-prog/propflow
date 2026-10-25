"""Polymarket game-winner markets: Gamma API for discovery, CLOB for order books.

This targets the international Polymarket APIs. Polymarket US (the CFTC-regulated app
US residents use) runs a separate API; point base URLs at it in config once you have
access, and expect to adapt the field names.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from ..models import Level, RawQuote
from . import parse_time

log = logging.getLogger(__name__)


def _json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    try:
        return json.loads(value or "[]")
    except json.JSONDecodeError:
        return []


def ask_ladder(book: dict[str, Any]) -> list[Level]:
    levels = [Level(float(a["price"]), float(a["size"])) for a in book.get("asks", []) if float(a["size"]) > 0]
    levels.sort(key=lambda l: l.price)
    return levels


def game_markets(event: dict[str, Any]) -> list[tuple[dict, list[str], list[str]]]:
    """Two-outcome team-vs-team markets (not Yes/No props)."""
    out = []
    for m in event.get("markets", []):
        if m.get("closed") or not m.get("active", True):
            continue
        outcomes = _json_list(m.get("outcomes"))
        tokens = _json_list(m.get("clobTokenIds"))
        if len(outcomes) != 2 or len(tokens) != 2:
            continue
        if {o.lower() for o in outcomes} == {"yes", "no"}:
            continue
        mtype = m.get("sportsMarketType")
        if mtype and mtype != "moneyline":
            continue
        out.append((m, outcomes, tokens))
    return out


def build_quotes(
    event: dict, market: dict, outcomes: list[str], tokens: list[str], books: dict[str, dict], sport: str
) -> list[RawQuote]:
    a, b = outcomes
    start = parse_time(market.get("gameStartTime") or event.get("startTime"))
    url = f"https://polymarket.com/event/{event.get('slug', '')}"
    quotes = []
    for side, token in zip(("home", "away"), tokens):
        levels = ask_ladder(books.get(token, {}))
        if levels:
            quotes.append(
                RawQuote(
                    venue="polymarket",
                    sport=sport,
                    # Polymarket's outcome order isn't a reliable home/away signal.
                    home=a,
                    away=b,
                    start=start,
                    kind="moneyline",
                    line=None,
                    outcome=side,
                    levels=levels,
                    url=url,
                    ref=token,
                    neutral=True,
                )
            )
    return quotes


async def fetch(client: httpx.AsyncClient, scfg: dict[str, Any]) -> list[RawQuote]:
    gamma = scfg.get("gamma_url", "https://gamma-api.polymarket.com")
    clob = scfg.get("clob_url", "https://clob.polymarket.com")
    sem = asyncio.Semaphore(scfg.get("concurrency", 8))
    quotes: list[RawQuote] = []

    for tag, sport in scfg.get("tags", {}).items():
        events: list[dict] = []
        offset = 0
        while True:
            params = {"tag_slug": tag, "closed": "false", "active": "true", "limit": 100, "offset": offset}
            try:
                resp = await client.get(f"{gamma}/events", params=params)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                log.warning("polymarket %s: %s", tag, e)
                break
            page = resp.json()
            events += page
            if len(page) < 100:
                break
            offset += 100

        pending = []
        for ev in events:
            for m, outcomes, tokens in game_markets(ev):
                pending.append((ev, m, outcomes, tokens))

        async def book(token: str) -> tuple[str, dict]:
            async with sem:
                try:
                    r = await client.get(f"{clob}/book", params={"token_id": token})
                    r.raise_for_status()
                    return token, r.json()
                except httpx.HTTPError as e:
                    log.debug("polymarket book %s: %s", token, e)
                    return token, {}

        all_tokens = [t for *_, tokens in pending for t in tokens]
        books = dict(await asyncio.gather(*(book(t) for t in all_tokens)))
        for ev, m, outcomes, tokens in pending:
            quotes += build_quotes(ev, m, outcomes, tokens, books, sport)
        log.info("polymarket %s: %d markets", tag, len(pending))
    return quotes
