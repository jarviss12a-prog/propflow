"""SQLite log of every opportunity seen, so we can measure how often real arbs show up,
how big they are, and how long they last before the market corrects."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from .models import Opportunity

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    key TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    sport TEXT NOT NULL,
    market TEXT NOT NULL,
    venues TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    scans INTEGER NOT NULL,
    best_roi REAL NOT NULL,
    best_profit REAL NOT NULL,
    best_cost REAL NOT NULL,
    last_legs TEXT NOT NULL,
    warnings TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def record(self, opp: Opportunity, now: datetime) -> bool:
        """Upsert; returns True if this opportunity is new (worth alerting on)."""
        legs = json.dumps(
            [
                {"venue": f.venue, "outcome": f.outcome, "price": f.price, "contracts": f.contracts,
                 "fee": f.fee, "ref": f.ref}
                for f in opp.fills
            ]
        )
        ts = now.isoformat()
        row = self.db.execute("SELECT best_roi FROM opportunities WHERE key = ?", (opp.key,)).fetchone()
        if row is None:
            self.db.execute(
                "INSERT INTO opportunities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (opp.key, opp.event_id, opp.sport, opp.describe_market(),
                 ",".join(sorted({f.venue for f in opp.fills})), ts, ts, 1, opp.roi, opp.profit,
                 opp.total_cost, legs, json.dumps(opp.warnings)),
            )
        else:
            self.db.execute(
                """UPDATE opportunities SET last_seen = ?, scans = scans + 1, last_legs = ?,
                   best_roi = MAX(best_roi, ?), best_profit = MAX(best_profit, ?),
                   best_cost = CASE WHEN ? > best_profit THEN ? ELSE best_cost END
                   WHERE key = ?""",
                (ts, legs, opp.roi, opp.profit, opp.profit, opp.total_cost, opp.key),
            )
        self.db.commit()
        return row is None

    def report(self, since_hours: float) -> dict:
        since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
        rows = self.db.execute(
            "SELECT sport, venues, first_seen, last_seen, best_roi, best_profit FROM opportunities "
            "WHERE first_seen >= ?",
            (since,),
        ).fetchall()
        durations = sorted(
            (datetime.fromisoformat(l) - datetime.fromisoformat(f)).total_seconds() for _, _, f, l, _, _ in rows
        )
        by_sport: dict[str, list[float]] = {}
        by_venues: dict[str, list[float]] = {}
        for sport, venues, _, _, _, profit in rows:
            by_sport.setdefault(sport, []).append(profit)
            by_venues.setdefault(venues, []).append(profit)
        return {
            "count": len(rows),
            "total_best_profit": sum(r[5] for r in rows),
            "avg_roi": sum(r[4] for r in rows) / len(rows) if rows else 0.0,
            "median_duration_s": durations[len(durations) // 2] if durations else 0.0,
            "by_sport": {k: (len(v), sum(v)) for k, v in sorted(by_sport.items())},
            "by_venues": {k: (len(v), sum(v)) for k, v in sorted(by_venues.items(), key=lambda kv: -sum(kv[1]))},
        }
