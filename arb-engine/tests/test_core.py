from datetime import datetime, timezone

import pytest

from arb.config import Config
from arb.engine import Engine
from arb.fees import FeeSpec, kalshi_fee
from arb.matcher import Matcher, normalize, similarity
from arb.models import Level, RawQuote
from arb.odds import american_to_prob, parse_price, prob_to_american

T0 = datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)


def q(venue, outcome, price, size=None, kind="moneyline", line=None, home="Texas Tech",
      away="Cincinnati", sport="ncaaf", start=T0, neutral=False, levels=None):
    return RawQuote(venue, sport, home, away, start, kind, line, outcome,
                    levels or [Level(price, size)], neutral=neutral)


def cfg(**kw):
    c = Config(min_roi=0.0, min_profit=0.0, bankroll=1000, sportsbook_max_stake=10_000,
               fees={"kalshi": FeeSpec("kalshi", 0.07)})
    for k, v in kw.items():
        setattr(c, k, v)
    return c


# --- odds -------------------------------------------------------------------------

def test_american_roundtrip():
    assert american_to_prob(-250) == pytest.approx(250 / 350)
    assert american_to_prob(310) == pytest.approx(100 / 410)
    assert prob_to_american(american_to_prob(-132)) == pytest.approx(-132)
    assert prob_to_american(american_to_prob(451)) == pytest.approx(451)


def test_parse_price_formats():
    assert parse_price("+110") == pytest.approx(100 / 210)
    assert parse_price("57c") == pytest.approx(0.57)
    assert parse_price("0.79") == pytest.approx(0.79)
    assert parse_price("2.0") == pytest.approx(0.5)


# --- fees -------------------------------------------------------------------------

def test_kalshi_fee_rounds_up_to_cent():
    fee = kalshi_fee(0.07)
    # 100 contracts at 50c: 0.07 * 100 * 0.25 = 1.75
    assert fee(100, 0.5) == pytest.approx(1.75)
    # 1 contract at 50c: 0.0175 -> 0.02
    assert fee(1, 0.5) == pytest.approx(0.02)
    assert fee(0, 0.5) == 0


# --- engine: cases taken from the 4C Odds screen ------------------------------------

def test_texas_tech_total_is_about_one_percent():
    quotes = [
        q("bookA", "over", american_to_prob(100), kind="total", line=57.5),
        q("novig", "under", american_to_prob(104), kind="total", line=57.5),
    ]
    [opp] = Engine(cfg()).find(quotes)
    assert opp.roi == pytest.approx(1 / (0.5 + 100 / 204) - 1, abs=2e-4)  # ~0.99%
    payouts = {}
    for f in opp.fills:
        payouts[f.outcome] = payouts.get(f.outcome, 0) + f.contracts
    assert min(payouts.values()) - opp.total_cost == pytest.approx(opp.profit)


def test_kalshi_fee_kills_toledo_arb():
    # W. Michigan +134 at a book vs Toledo -132 on Kalshi: 0.37% before fees.
    no_fee = [
        q("bookA", "home", american_to_prob(134)),
        q("kalshi_nofee", "away", american_to_prob(-132), size=27_000),
    ]
    assert Engine(cfg()).find(no_fee)
    with_fee = [
        q("bookA", "home", american_to_prob(134)),
        q("kalshi", "away", american_to_prob(-132), size=27_000),
    ]
    assert Engine(cfg()).find(with_fee) == []


def test_depth_limits_size():
    quotes = [
        q("bookA", "home", american_to_prob(110)),
        q("ex", "away", 0.45, size=200),  # only 200 contracts at 45c
    ]
    [opp] = Engine(cfg()).find(quotes)
    away = sum(f.contracts for f in opp.fills if f.outcome == "away")
    assert away <= 200


def test_ladder_walks_multiple_venues():
    quotes = [
        q("bookA", "home", american_to_prob(120)),          # 45.45%
        q("ex1", "away", 0.50, size=300),
        q("ex2", "away", 0.51, size=1000),
    ]
    [opp] = Engine(cfg(bankroll=5000)).find(quotes)
    venues = {f.venue for f in opp.fills if f.outcome == "away"}
    assert venues == {"ex1", "ex2"}


def test_no_arb_on_efficient_market():
    # LSU/Auburn screen: best prices +110 / -116 sum to 101.3%.
    quotes = [
        q("bookA", "home", american_to_prob(110), kind="spread", line=-7.5),
        q("bookB", "away", american_to_prob(-116), kind="spread", line=-7.5),
    ]
    assert Engine(cfg()).find(quotes) == []


def test_soccer_needs_draw_leg():
    quotes = [
        q("a", "home", american_to_prob(300), sport="soccer_epl"),
        q("b", "away", american_to_prob(300), sport="soccer_epl"),
    ]
    assert Engine(cfg()).find(quotes) == []
    quotes.append(q("c", "draw", american_to_prob(300), sport="soccer_epl"))
    [opp] = Engine(cfg()).find(quotes)
    assert {f.outcome for f in opp.fills} == {"home", "away", "draw"}


def test_disallowed_venue_ignored():
    quotes = [
        q("pinnacle", "home", american_to_prob(120)),
        q("bookB", "away", american_to_prob(-110)),
    ]
    assert Engine(cfg(allowed_venues={"bookB", "bookC"})).find(quotes) == []


def test_tennis_rule_warning():
    quotes = [
        q("bookA", "home", american_to_prob(120), sport="tennis_atp", home="Sinner", away="Alcaraz", neutral=True),
        q("bookB", "away", american_to_prob(-110), sport="tennis_atp", home="Sinner", away="Alcaraz", neutral=True),
    ]
    [opp] = Engine(cfg()).find(quotes)
    assert any("retirement" in w for w in opp.warnings)
    assert Engine(cfg(on_rule_mismatch="skip")).find(quotes) == []
    same = cfg(rules={"tennis_retirement": {"bookA": "void", "bookB": "void"}})
    [opp] = Engine(same).find(quotes)
    assert not any("retirement" in w for w in opp.warnings)


# --- matcher ----------------------------------------------------------------------

def test_normalize_and_alias():
    assert normalize("Ohio St.", {"ohio st": "ohio state"}) == "ohio state"
    assert normalize("Texas A&M") == "texas a and m"


def test_mascot_suffix_matches():
    assert similarity("texas tech", "texas tech red raiders") >= 0.82
    assert similarity("cincinnati", "cincinnati bearcats") >= 0.82


def test_neutral_source_gets_flipped():
    m = Matcher({}, 6, 0.82)
    book = q("bookA", "home", 0.5, home="Cincinnati", away="Texas Tech")
    kalshi = q("kalshi", "home", 0.5, home="Texas Tech", away="Cincinnati", start=None, neutral=True)
    (ev1, _), (ev2, k2) = m.assign_all([kalshi, book])  # neutral quote is processed last
    assert ev1 is ev2
    assert k2.outcome == "away" and k2.home == "Cincinnati"


def test_home_aware_sources_not_flipped_into_rematch():
    m = Matcher({}, 6, 0.82)
    a = q("bookA", "home", 0.5, home="Cincinnati", away="Texas Tech")
    b = q("bookB", "home", 0.5, home="Texas Tech", away="Cincinnati")
    (ev1, _), (ev2, _) = m.assign_all([a, b])
    assert ev1 is not ev2


def test_spread_flip_negates_line():
    r = q("x", "home", 0.5, kind="spread", line=-3.5).flipped()
    assert r.outcome == "away" and r.line == 3.5


# --- cli --------------------------------------------------------------------------

def test_calc_accepts_negative_odds(capsys):
    from arb.cli import main

    main(["calc", "+134@book", "-132@kalshi", "--stake", "500"])
    out = capsys.readouterr().out
    assert "no arb" not in out  # no config => no Kalshi fee => 0.37% arb
    main(["calc", "--config", "config.example.toml", "+134@book", "-132@kalshi"])
    assert "no arb" in capsys.readouterr().out
