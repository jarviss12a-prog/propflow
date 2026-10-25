from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

import httpx

from . import config as config_mod
from .alerts import Alerter, format_opp
from .engine import Engine
from .models import Level, RawQuote
from .odds import parse_price
from .sources import kalshi, oddsapi, polymarket, replay
from .store import Store

log = logging.getLogger("arb")

SOURCES = {"oddsapi": oddsapi.fetch, "kalshi": kalshi.fetch, "polymarket": polymarket.fetch}


async def gather_quotes(client: httpx.AsyncClient, cfg: config_mod.Config) -> list[RawQuote]:
    enabled = [(name, scfg) for name, scfg in cfg.sources.items() if scfg.get("enabled") and name in SOURCES]
    results = await asyncio.gather(*(SOURCES[n](client, s) for n, s in enabled), return_exceptions=True)
    quotes: list[RawQuote] = []
    for (name, _), res in zip(enabled, results):
        if isinstance(res, BaseException):
            log.warning("source %s failed: %s", name, res)
            continue
        log.info("source %s: %d quotes", name, len(res))
        quotes += res
    return quotes


async def scan(args: argparse.Namespace) -> None:
    cfg = config_mod.load(args.config)
    engine = Engine(cfg)
    store = Store(cfg.db_path)
    alerter = Alerter()
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "arb-engine/0.1"}) as client:
        while True:
            started = datetime.now(timezone.utc)
            quotes = replay.load(args.replay) if args.replay else await gather_quotes(client, cfg)
            if args.record:
                replay.append_snapshot(args.record, quotes)
            opps = engine.find(quotes)
            for o in opps:
                if store.record(o, started):
                    await alerter.send(client, o)
            log.info("scan: %d quotes, %d opportunities", len(quotes), len(opps))
            if args.once or args.replay:
                return
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            await asyncio.sleep(max(0.0, cfg.interval_seconds - elapsed))


def report(args: argparse.Namespace) -> None:
    cfg = config_mod.load(args.config)
    r = Store(cfg.db_path).report(args.hours)
    print(f"Last {args.hours:g}h: {r['count']} opportunities, "
          f"theoretical best-case profit ${r['total_best_profit']:,.2f}, avg ROI {r['avg_roi'] * 100:.2f}%, "
          f"median lifetime {r['median_duration_s']:.0f}s")
    print("\nBy sport:")
    for k, (n, p) in r["by_sport"].items():
        print(f"  {k:<16} {n:>5}  ${p:,.2f}")
    print("\nBy venue combination:")
    for k, (n, p) in r["by_venues"].items():
        print(f"  {k:<40} {n:>5}  ${p:,.2f}")


def calc(args: argparse.Namespace) -> None:
    """Manual calculator for arbs spotted on an odds screen: `calc +100@novig +104@kalshi`."""
    cfg = config_mod.load(args.config) if args.config else config_mod.Config()
    cfg.bankroll = args.stake
    cfg.sportsbook_max_stake = args.stake * 10
    cfg.min_roi = -1.0
    cfg.min_profit = -1e9
    cfg.allowed_venues = set()
    outcomes = ("home", "away") if len(args.legs) == 2 else ("home", "away", "draw")
    sport = "calc" if len(args.legs) == 2 else "soccer_calc"
    quotes, total = [], 0.0
    for leg, outcome in zip(args.legs, outcomes):
        price_txt, _, venue = leg.partition("@")
        venue = venue or f"book{len(quotes) + 1}"
        p = parse_price(price_txt)
        fee_per = cfg.fee_fn(venue)(100, p) / 100
        total += p + fee_per
        print(f"  {venue:<12} {price_txt:>6}  implied {p * 100:.2f}%  +fee {fee_per * 100:.2f}%")
        name = f"leg {len(quotes) + 1}"
        quotes.append(RawQuote(venue, sport, "leg 1", "leg 2", datetime.now(timezone.utc), "moneyline", None,
                               outcome, [Level(p)], url=None, ref=name))
    print(f"  sum {total * 100:.2f}%  ->  {'ARB' if total < 1 else 'no arb'} ({(1 / total - 1) * 100:+.2f}% ROI)")
    if total < 1:
        for o in Engine(cfg).find(quotes):
            print()
            print(format_opp(o))


def _calc_argv(argv: list[str]) -> list[str]:
    # Odds like -132@kalshi look like options to argparse; move legs behind "--".
    if not argv or argv[0] != "calc":
        return argv
    opts, legs, i = [], [], 1
    while i < len(argv):
        t = argv[i]
        if t in ("--stake", "--config"):
            opts += argv[i : i + 2]
            i += 2
            continue
        (opts if t.startswith("--") or t in ("-h", "-v") else legs).append(t)
        i += 1
    return ["calc", *opts, "--", *legs]


def main(argv: list[str] | None = None) -> None:
    argv = _calc_argv(list(sys.argv[1:] if argv is None else argv))
    ap = argparse.ArgumentParser(prog="arb", description="Cross-venue sports arbitrage scanner")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan venues for arbs")
    s.add_argument("--config", default="config.toml")
    s.add_argument("--once", action="store_true", help="run one scan and exit")
    s.add_argument("--record", metavar="FILE", help="append every scan's quotes to a JSONL file")
    s.add_argument("--replay", metavar="FILE", help="scan a saved snapshot instead of live APIs")

    r = sub.add_parser("report", help="summarize logged opportunities")
    r.add_argument("--config", default="config.toml")
    r.add_argument("--hours", type=float, default=24)

    c = sub.add_parser("calc", help="check an arb by hand, e.g. calc +100@novig +104@kalshi")
    c.add_argument("legs", nargs="+", help="price[@venue]; price is +110, -132, 2.10, 0.57 or 57c")
    c.add_argument("--stake", type=float, default=1000, help="total stake (default 1000)")
    c.add_argument("--config", default=None, help="config.toml for venue fees")

    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if args.cmd == "scan":
        asyncio.run(scan(args))
    elif args.cmd == "report":
        report(args)
    elif args.cmd == "calc":
        if len(args.legs) not in (2, 3):
            ap.error("calc takes 2 legs (or 3 for a soccer 1X2 market)")
        calc(args)
