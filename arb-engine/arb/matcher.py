"""Cross-venue event matching.

Every venue names teams differently ("Ohio St." / "Ohio State Buckeyes" / "OSU"), and some
venues don't say which side is home. The matcher assigns each RawQuote to a canonical
event and flips its orientation (home/away, spread sign) to agree with that event.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from .models import RawQuote

_STOPWORDS = {"the", "fc", "cf", "sc", "afc", "university", "univ", "of"}


def normalize(name: str, aliases: dict[str, str] | None = None) -> str:
    n = name.lower().replace("&", " and ")
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    n = " ".join(t for t in n.split() if t not in _STOPWORDS)
    if aliases and n in aliases:
        n = aliases[n]
    return n


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    ta, tb = a.split(), b.split()
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    # "texas tech" vs "texas tech red raiders": a leading-token match is strong evidence
    # (mascot suffix), but less than exact so a true exact match always wins.
    if short and long_[: len(short)] == short:
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class CanonicalEvent:
    id: str
    sport: str
    home: str
    away: str
    start: datetime | None
    neutral: bool
    display_home: str = ""
    display_away: str = ""


class Matcher:
    def __init__(self, aliases: dict[str, str], window_hours: float, threshold: float):
        self.aliases = aliases
        self.window = timedelta(hours=window_hours)
        self.threshold = threshold
        self.events: list[CanonicalEvent] = []

    def _time_ok(self, a: datetime | None, b: datetime | None) -> bool:
        if a is None or b is None:
            return True
        return abs(a - b) <= self.window

    def _score(self, ev: CanonicalEvent, home: str, away: str) -> float:
        return min(similarity(ev.home, home), similarity(ev.away, away))

    def assign(self, q: RawQuote) -> tuple[CanonicalEvent, RawQuote]:
        """Return the canonical event for q and q re-oriented to that event."""
        home, away = normalize(q.home, self.aliases), normalize(q.away, self.aliases)
        best: tuple[float, CanonicalEvent, bool] | None = None
        for ev in self.events:
            if ev.sport != q.sport or not self._time_ok(ev.start, q.start):
                continue
            straight = self._score(ev, home, away)
            swapped = self._score(ev, away, home)
            # A swapped match is only trusted if one side lacks real home/away info;
            # otherwise "A at B" and "B at A" are different games (e.g. a rematch).
            if not (q.neutral or ev.neutral):
                swapped = 0.0
            score, swap = (straight, False) if straight >= swapped else (swapped, True)
            if score >= self.threshold and (best is None or score > best[0]):
                best = (score, ev, swap)
        if best is None:
            ev = CanonicalEvent(
                id=f"{q.sport}:{home}@{away}:{q.start.date() if q.start else 'nodate'}",
                sport=q.sport,
                home=home,
                away=away,
                start=q.start,
                neutral=q.neutral,
                display_home=q.home,
                display_away=q.away,
            )
            self.events.append(ev)
            return ev, q
        _, ev, swap = best
        if ev.start is None and q.start is not None:
            ev.start = q.start
        return ev, (q.flipped() if swap else q)

    def assign_all(self, quotes: list[RawQuote]) -> list[tuple[CanonicalEvent, RawQuote]]:
        # Home-aware quotes go first so canonical events take their orientation,
        # and neutral sources (tennis, Kalshi) get flipped onto it.
        ordered = sorted(quotes, key=lambda q: q.neutral)
        return [self.assign(q) for q in ordered]
