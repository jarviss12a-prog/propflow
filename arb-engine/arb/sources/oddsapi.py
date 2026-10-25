"""Sportsbook prices from The Odds API (https://the-odds-api.com), v4.

Each call costs quota (markets x regions per sport), so keep `markets` and `regions` tight.
Sportsbooks don't publish limits, so their levels carry size=None and the engine caps
them at scan.sportsbook_max_stake.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from ..models import Level, RawQuote
from ..odds import american_to_prob
from . import parse_time

log = logging.getLogger(__name__)

_FIXED = {
    "americanfootball_nfl": "nfl",
    "americanfootball_ncaaf": "ncaaf",
    "basketball_nba": "nba",
    "basketball_ncaab": "ncaab",
    "basketball_wnba": "wnba",
    "icehockey_nhl": "nhl",
    "baseball_mlb": "mlb",
}


def canonical_sport(key: str) -> str:
    if key in _FIXED:
        return _FIXED[key]
    if key.startswith("tennis_atp"):
        return "tennis_atp"
    if key.startswith("tennis_wta"):
        return "tennis_wta"
    if key.startswith("soccer_"):
        return key  # league-specific, e.g. soccer_epl
    return key


def parse(events: list[dict[str, Any]]) -> list[RawQuote]:
    quotes: list[RawQuote] = []
    for ev in events:
        sport = canonical_sport(ev["sport_key"])
        home, away = ev["home_team"], ev["away_team"]
        start = parse_time(ev.get("commence_time"))
        neutral = sport.startswith("tennis")
        for book in ev.get("bookmakers", []):
            venue = book["key"]
            for market in book.get("markets", []):
                for oc in market.get("outcomes", []):
                    q = _outcome(market["key"], oc, home, away)
                    if q is None:
                        continue
                    kind, line, outcome = q
                    try:
                        prob = american_to_prob(float(oc["price"]))
                    except (KeyError, ValueError):
                        continue
                    quotes.append(
                        RawQuote(
                            venue=venue,
                            sport=sport,
                            home=home,
                            away=away,
                            start=start,
                            kind=kind,
                            line=line,
                            outcome=outcome,
                            levels=[Level(prob)],
                            url=oc.get("link") or market.get("link") or book.get("link"),
                            ref=ev.get("id"),
                            neutral=neutral,
                        )
                    )
    return quotes


def _outcome(market_key: str, oc: dict, home: str, away: str):
    name = oc.get("name")
    if market_key == "h2h":
        if name == home:
            return "moneyline", None, "home"
        if name == away:
            return "moneyline", None, "away"
        if name == "Draw":
            return "moneyline", None, "draw"
    elif market_key == "spreads" and "point" in oc:
        point = float(oc["point"])
        if name == home:
            return "spread", point, "home"
        if name == away:
            return "spread", -point, "away"
    elif market_key == "totals" and "point" in oc:
        if name in ("Over", "Under"):
            return "total", float(oc["point"]), name.lower()
    return None


async def fetch(client: httpx.AsyncClient, scfg: dict[str, Any]) -> list[RawQuote]:
    key = os.environ.get(scfg.get("api_key_env", "ODDS_API_KEY"))
    if not key:
        log.warning("oddsapi: no API key in $%s, skipping", scfg.get("api_key_env", "ODDS_API_KEY"))
        return []
    base = scfg.get("base_url", "https://api.the-odds-api.com/v4")
    sports = list(scfg.get("sports", []))
    if scfg.get("include_tennis", False):
        # Tennis keys are per tournament; /sports is free and lists the active ones.
        resp = await client.get(f"{base}/sports", params={"apiKey": key})
        resp.raise_for_status()
        sports += [s["key"] for s in resp.json() if s["key"].startswith("tennis_") and s.get("active")]

    quotes: list[RawQuote] = []
    for sport in sports:
        params = {
            "apiKey": key,
            "regions": scfg.get("regions", "us"),
            "markets": scfg.get("markets", "h2h,spreads,totals"),
            "oddsFormat": "american",
            "includeLinks": "true",
        }
        if scfg.get("bookmakers"):
            params["bookmakers"] = ",".join(scfg["bookmakers"])
            params.pop("regions")
        resp = await client.get(f"{base}/sports/{sport}/odds", params=params)
        if resp.status_code != 200:
            log.warning("oddsapi %s: HTTP %s %s", sport, resp.status_code, resp.text[:200])
            continue
        log.debug("oddsapi %s: quota remaining %s", sport, resp.headers.get("x-requests-remaining"))
        quotes += parse(resp.json())
    return quotes
