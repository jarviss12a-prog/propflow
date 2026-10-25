"""Arbitrage detection with fees and order-book depth.

For each matched market we build, per outcome, one ladder that merges every allowed
venue's price levels, cheapest first. Buying N $1-payout contracts on every outcome pays
exactly N whatever happens, so profit(N) = N - sum(cost of walking each ladder to N).
Marginal cost only rises as we walk deeper, so the best N sits on a ladder breakpoint
or on the bankroll cap; we evaluate those candidates and keep the most profitable.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .config import Config
from .fees import FeeFn
from .matcher import CanonicalEvent, Matcher
from .models import Fill, Opportunity, RawQuote, required_outcomes, sport_family

SPORTSBOOK_STAKE_STEP = 0.01


@dataclass
class _Piece:
    venue: str
    price: float
    size: float
    fee_fn: FeeFn
    integer: bool  # exchanges trade whole contracts; sportsbooks take cents
    url: str | None
    ref: str | None


def _unit_cost(piece: _Piece) -> float:
    # Fee per contract at a typical size; used only to order the merged ladder.
    sample = min(piece.size, 100.0) or 1.0
    return piece.price + piece.fee_fn(sample, piece.price) / sample


def _walk(ladder: list[_Piece], n: float) -> tuple[float, list[Fill]] | None:
    remaining = n
    total = 0.0
    fills: list[Fill] = []
    for piece in ladder:
        if remaining <= 1e-9:
            break
        take = min(remaining, piece.size)
        if piece.integer:
            take = math.floor(take + 1e-9)
        else:
            stake = math.floor(take * piece.price / SPORTSBOOK_STAKE_STEP) * SPORTSBOOK_STAKE_STEP
            take = stake / piece.price
        if take <= 0:
            continue
        fee = piece.fee_fn(take, piece.price)
        fills.append(Fill(piece.venue, "", piece.price, take, fee, piece.url, piece.ref))
        total += take * piece.price + fee
        remaining -= take
    if remaining > 1.0:  # couldn't fill within a contract of the target
        return None
    return total, fills


class Engine:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def _ladder(self, quotes: list[RawQuote]) -> list[_Piece]:
        pieces: list[_Piece] = []
        for q in quotes:
            fee_fn = self.cfg.fee_fn(q.venue)
            # Exchanges report depth and trade whole contracts; sportsbooks don't.
            is_exchange = any(l.size is not None for l in q.levels)
            for lvl in q.levels:
                if not 0 < lvl.price < 1:
                    continue
                size = lvl.size
                if size is None:
                    size = self.cfg.sportsbook_max_stake / lvl.price
                if size <= 0:
                    continue
                pieces.append(
                    _Piece(q.venue, lvl.price, size, fee_fn, is_exchange, q.url, q.ref)
                )
        pieces.sort(key=_unit_cost)
        return pieces

    def _rule_warnings(self, sport: str, venues: set[str]) -> list[str]:
        warnings = []
        if sport_family(sport) == "tennis":
            policies = self.cfg.rules.get("tennis_retirement", {})
            seen = {v: policies.get(v, "unknown") for v in sorted(venues)}
            if "unknown" in seen.values() or len(set(seen.values())) > 1:
                desc = ", ".join(f"{v}={p}" for v, p in seen.items())
                warnings.append(f"tennis retirement rules differ or unknown ({desc})")
        return warnings

    def _best(self, ladders: dict[str, list[_Piece]]) -> tuple[float, dict[str, list[Fill]]] | None:
        depth = min(sum(p.size for p in lad) for lad in ladders.values())
        candidates: set[float] = set()
        for lad in ladders.values():
            cum = 0.0
            for p in lad:
                cum += p.size
                if cum <= depth:
                    candidates.add(cum)
        candidates.add(depth)

        # Largest N whose total cost fits the bankroll (cost is monotonic in N).
        lo, hi = 0.0, depth
        for _ in range(40):
            mid = (lo + hi) / 2
            walked = [_walk(lad, mid) for lad in ladders.values()]
            if all(walked) and sum(w[0] for w in walked) <= self.cfg.bankroll:
                lo = mid
            else:
                hi = mid
        candidates = {min(c, lo) for c in candidates}

        best: tuple[float, float, dict[str, list[Fill]]] | None = None
        for n in sorted(candidates):
            n = math.floor(n)
            if n < 1:
                continue
            fills_by_outcome: dict[str, list[Fill]] = {}
            total = 0.0
            ok = True
            for outcome, lad in ladders.items():
                walked = _walk(lad, n)
                if walked is None:
                    ok = False
                    break
                cost, fills = walked
                for f in fills:
                    f.outcome = outcome
                fills_by_outcome[outcome] = fills
                total += cost
            if not ok or total > self.cfg.bankroll + 1e-6:
                continue
            payout = min(sum(f.contracts for f in fs) for fs in fills_by_outcome.values())
            profit = payout - total
            if best is None or profit > best[0]:
                best = (profit, total, fills_by_outcome)
        if best is None:
            return None
        return best[1], best[2]

    def find(self, quotes: list[RawQuote]) -> list[Opportunity]:
        matcher = Matcher(
            self.cfg.aliases, self.cfg.event_time_window_hours, self.cfg.match_threshold
        )
        markets: dict[tuple, dict[str, list[RawQuote]]] = defaultdict(lambda: defaultdict(list))
        events: dict[str, CanonicalEvent] = {}
        for ev, q in matcher.assign_all([q for q in quotes if self.cfg.venue_allowed(q.venue)]):
            events[ev.id] = ev
            markets[(ev.id, q.kind, q.line)][q.outcome].append(q)

        opps: list[Opportunity] = []
        for (event_id, kind, line), by_outcome in markets.items():
            ev = events[event_id]
            outcomes = required_outcomes(ev.sport, kind)
            if any(o not in by_outcome for o in outcomes):
                continue
            ladders = {o: self._ladder(by_outcome[o]) for o in outcomes}
            if any(not lad for lad in ladders.values()):
                continue
            top = sum(_unit_cost(lad[0]) for lad in ladders.values())
            if top >= 1.0:
                continue
            result = self._best(ladders)
            if result is None:
                continue
            total, fills_by_outcome = result
            fills = [f for fs in fills_by_outcome.values() for f in fs]
            payout = min(sum(f.contracts for f in fs) for fs in fills_by_outcome.values())
            venues = {f.venue for f in fills}
            # An "arb" whose legs all sit on one venue is that venue's own mispricing
            # (common on Kalshi YES-vs-NO); keep it, it's real, but say so.
            warnings = self._rule_warnings(ev.sport, venues)
            if len(venues) == 1:
                warnings.append("single-venue arb: verify the prices are live")
            if ev.start is None:
                warnings.append("no start time from any venue: verify it's the same game")
            if warnings and self.cfg.on_rule_mismatch == "skip" and any(
                "rules" in w for w in warnings
            ):
                continue
            opp = Opportunity(
                event_id=event_id,
                sport=ev.sport,
                home=ev.display_home,
                away=ev.display_away,
                start=ev.start,
                kind=kind,
                line=line,
                fills=fills,
                total_cost=total,
                min_payout=payout,
                top_book_sum=top,
                warnings=warnings,
            )
            if opp.roi >= self.cfg.min_roi and opp.profit >= self.cfg.min_profit:
                opps.append(opp)
        opps.sort(key=lambda o: o.profit, reverse=True)
        return opps
