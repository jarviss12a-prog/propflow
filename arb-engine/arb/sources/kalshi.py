"""Kalshi game-winner markets via the public trade API (no auth needed for market data).

A Kalshi game event holds one binary market per team ("Will <team> win?"). Kalshi's order
book only lists bids, so asks are derived: buying YES at X cents is filling a NO bid at
(100 - X). That gives two ways to back a team in a 2-way game: YES on its market, or NO on
the opponent's market. Both go in as quotes and the engine picks the cheaper.

Series tickers (e.g. KXNCAAFGAME) map Kalshi series to our sport keys in config.toml.
Check them against GET /series if a sport returns nothing.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from ..matcher import normalize, similarity
from ..models import Level, RawQuote

log = logging.getLogger(__name__)

_TITLE = re.compile(r"^\s*(?P<a>.+?)\s+(?P<sep>at|@|vs\.?|v\.?)\s+(?P<b>.+?)\s*(?:[:?].*)?$", re.I)
_SUFFIX = re.compile(r"\s+(winner|wins?|game|match)\s*\??$", re.I)


def parse_title(title: str) -> tuple[str, str, bool] | None:
    """'Texas Tech at Cincinnati' -> ('Cincinnati', 'Texas Tech', neutral=False)."""
    m = _TITLE.match(_SUFFIX.sub("", title))
    if not m:
        return None
    a, b, sep = m["a"].strip(), m["b"].strip(), m["sep"].lower()
    if sep in ("at", "@"):
        return b, a, False  # "away at home"
    return a, b, True


def ask_ladder(bids: list[list[float]], in_dollars: bool) -> list[Level]:
    """Opposite-side bids -> this side's asks, best (cheapest) first."""
    levels = []
    for price, qty in bids:
        p = float(price) if in_dollars else float(price) / 100.0
        if qty and 0 < p < 1:
            levels.append(Level(round(1.0 - p, 4), float(qty)))
    levels.sort(key=lambda l: l.price)
    return levels


def _book_sides(payload: dict[str, Any]) -> tuple[list, list, bool]:
    ob = payload.get("orderbook") or {}
    if ob.get("yes_dollars") is not None or ob.get("no_dollars") is not None:
        return ob.get("yes_dollars") or [], ob.get("no_dollars") or [], True
    return ob.get("yes") or [], ob.get("no") or [], False


def build_quotes(event: dict[str, Any], books: dict[str, dict], sport: str, base_web: str) -> list[RawQuote]:
    parsed = parse_title(event.get("title", ""))
    markets = [m for m in event.get("markets", []) if m.get("status", "active") in ("active", "open")]
    if parsed is None or len(markets) != 2:
        return []
    home, away, neutral = parsed
    nh, na = normalize(home), normalize(away)

    sides: dict[str, dict] = {}
    for m in markets:
        name = normalize(m.get("yes_sub_title") or m.get("subtitle") or "")
        sh, sa = similarity(name, nh), similarity(name, na)
        side = "home" if sh > sa else "away"
        if max(sh, sa) < 0.6 or side in sides:
            return []  # can't tell which market is which team; skip rather than guess
        sides[side] = m

    url = f"{base_web}/markets/{event.get('series_ticker', '').lower()}"
    quotes = []
    for side, m in sides.items():
        other = sides["away" if side == "home" else "home"]
        yes_bids, no_bids, dollars = _book_sides(books.get(m["ticker"], {}))
        o_yes_bids, _, o_dollars = _book_sides(books.get(other["ticker"], {}))
        for levels, ref in (
            (ask_ladder(no_bids, dollars), f"{m['ticker']}:yes"),
            (ask_ladder(o_yes_bids, o_dollars), f"{other['ticker']}:no"),
        ):
            if levels:
                quotes.append(
                    RawQuote(
                        venue="kalshi",
                        sport=sport,
                        home=home,
                        away=away,
                        start=None,
                        kind="moneyline",
                        line=None,
                        outcome=side,
                        levels=levels,
                        url=url,
                        ref=ref,
                        neutral=neutral,
                    )
                )
    return quotes


async def fetch(client: httpx.AsyncClient, scfg: dict[str, Any]) -> list[RawQuote]:
    base = scfg.get("base_url", "https://api.elections.kalshi.com/trade-api/v2")
    base_web = scfg.get("web_url", "https://kalshi.com")
    sem = asyncio.Semaphore(scfg.get("concurrency", 8))

    async def get(path: str, params: dict | None = None) -> dict:
        async with sem:
            resp = await client.get(f"{base}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

    quotes: list[RawQuote] = []
    for series, sport in scfg.get("series", {}).items():
        events: list[dict] = []
        cursor = None
        while True:
            params = {"series_ticker": series, "status": "open", "with_nested_markets": "true", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            try:
                data = await get("/events", params)
            except httpx.HTTPError as e:
                log.warning("kalshi %s: %s", series, e)
                break
            events += data.get("events", [])
            cursor = data.get("cursor")
            if not cursor:
                break

        tickers = [m["ticker"] for ev in events for m in ev.get("markets", [])]

        async def book(t: str) -> tuple[str, dict]:
            try:
                return t, await get(f"/markets/{t}/orderbook")
            except httpx.HTTPError as e:
                log.debug("kalshi orderbook %s: %s", t, e)
                return t, {}

        books = dict(await asyncio.gather(*(book(t) for t in tickers)))
        for ev in events:
            quotes += build_quotes(ev, books, sport, base_web)
        log.info("kalshi %s: %d events, %d quotes", series, len(events), len(quotes))
    return quotes
