"""Save and load RawQuote snapshots, for offline testing and later backtests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..models import Level, RawQuote
from . import parse_time


def to_dict(q: RawQuote) -> dict:
    return {
        "venue": q.venue,
        "sport": q.sport,
        "home": q.home,
        "away": q.away,
        "start": q.start.isoformat() if q.start else None,
        "kind": q.kind,
        "line": q.line,
        "outcome": q.outcome,
        "levels": [[l.price, l.size] for l in q.levels],
        "url": q.url,
        "ref": q.ref,
        "neutral": q.neutral,
    }


def from_dict(d: dict) -> RawQuote:
    return RawQuote(
        venue=d["venue"],
        sport=d["sport"],
        home=d["home"],
        away=d["away"],
        start=parse_time(d.get("start")),
        kind=d["kind"],
        line=d.get("line"),
        outcome=d["outcome"],
        levels=[Level(p, s) for p, s in d["levels"]],
        url=d.get("url"),
        ref=d.get("ref"),
        neutral=d.get("neutral", False),
    )


def load(path: str | Path) -> list[RawQuote]:
    data = json.loads(Path(path).read_text())
    return [from_dict(d) for d in data["quotes"]]


def append_snapshot(path: str | Path, quotes: list[RawQuote]) -> None:
    line = {"ts": datetime.now(timezone.utc).isoformat(), "quotes": [to_dict(q) for q in quotes]}
    with open(path, "a") as f:
        f.write(json.dumps(line) + "\n")
