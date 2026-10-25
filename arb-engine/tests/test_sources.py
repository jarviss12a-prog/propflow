"""Parser tests against payloads shaped like each API's documented responses.
These check our parsing logic, not the live APIs."""

import json
from pathlib import Path

import pytest

from arb.config import Config
from arb.engine import Engine
from arb.fees import FeeSpec
from arb.sources import kalshi, oddsapi, polymarket, replay

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


def test_oddsapi_parse():
    quotes = oddsapi.parse(load("oddsapi_ncaaf.json"))
    ml = [x for x in quotes if x.kind == "moneyline"]
    spreads = [x for x in quotes if x.kind == "spread"]
    totals = [x for x in quotes if x.kind == "total"]
    assert {x.outcome for x in ml} == {"home", "away"}
    # home -3.5 and away +3.5 must land on the same market key (line -3.5)
    assert {x.line for x in spreads} == {-3.5}
    assert {x.line for x in totals} == {57.5}
    assert all(x.sport == "ncaaf" and x.start is not None for x in quotes)


def test_kalshi_title_parsing():
    assert kalshi.parse_title("Texas Tech at Cincinnati") == ("Cincinnati", "Texas Tech", False)
    assert kalshi.parse_title("Texas Tech at Cincinnati Winner?") == ("Cincinnati", "Texas Tech", False)
    home, away, neutral = kalshi.parse_title("Sinner vs Alcaraz")
    assert neutral and {home, away} == {"Sinner", "Alcaraz"}
    assert kalshi.parse_title("Who will win the Heisman?") is None


def test_kalshi_ask_ladder_from_opposite_bids():
    # NO bids at 40c and 42c -> YES asks at 60c and 58c, cheapest first
    levels = kalshi.ask_ladder([[40, 100], [42, 50]], in_dollars=False)
    assert [(l.price, l.size) for l in levels] == [(0.58, 50), (0.60, 100)]
    levels = kalshi.ask_ladder([["0.4200", 50]], in_dollars=True)
    assert levels[0].price == pytest.approx(0.58)


def test_kalshi_build_quotes_both_routes():
    data = load("kalshi_event.json")
    quotes = kalshi.build_quotes(data["event"], data["books"], "ncaaf", "https://kalshi.com")
    refs = {(x.outcome, x.ref) for x in quotes}
    # Cincinnati (home): YES on CIN market, or NO on TTU market
    assert ("home", "KXNCAAFGAME-26OCT25TTUCIN-CIN:yes") in refs
    assert ("home", "KXNCAAFGAME-26OCT25TTUCIN-TTU:no") in refs
    assert ("away", "KXNCAAFGAME-26OCT25TTUCIN-TTU:yes") in refs


def test_polymarket_parse():
    data = load("polymarket_event.json")
    [(m, outcomes, tokens)] = polymarket.game_markets(data["event"])
    quotes = polymarket.build_quotes(data["event"], m, outcomes, tokens, data["books"], "ncaaf")
    assert {x.outcome for x in quotes} == {"home", "away"}
    assert all(x.neutral for x in quotes)
    assert quotes[0].levels[0].price <= quotes[0].levels[-1].price


def test_end_to_end_cross_venue(tmp_path):
    """Sportsbook feed + Kalshi + Polymarket for the same game, matched and scanned."""
    quotes = oddsapi.parse(load("oddsapi_ncaaf.json"))
    k = load("kalshi_event.json")
    quotes += kalshi.build_quotes(k["event"], k["books"], "ncaaf", "https://kalshi.com")
    p = load("polymarket_event.json")
    [(m, outcomes, tokens)] = polymarket.game_markets(p["event"])
    quotes += polymarket.build_quotes(p["event"], m, outcomes, tokens, p["books"], "ncaaf")

    cfg = Config(min_roi=0.0, min_profit=0.0, bankroll=1000, fees={"kalshi": FeeSpec("kalshi", 0.07)})
    opps = Engine(cfg).find(quotes)
    ml = [o for o in opps if o.kind == "moneyline"]
    assert len(ml) == 1
    assert len({o.event_id for o in opps}) == 1  # all three venues matched to one game
    venues = {f.venue for f in ml[0].fills}
    assert "polymarket" in venues

    # replay round-trip gives identical results
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps({"quotes": [replay.to_dict(x) for x in quotes]}))
    again = Engine(cfg).find(replay.load(snap))
    assert [o.key for o in again] == [o.key for o in opps]
