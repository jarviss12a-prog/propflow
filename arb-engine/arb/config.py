from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .fees import FeeFn, FeeSpec, no_fee


@dataclass
class Config:
    interval_seconds: float = 30
    min_roi: float = 0.002
    min_profit: float = 1.0
    bankroll: float = 2000.0
    sportsbook_max_stake: float = 500.0
    on_rule_mismatch: str = "warn"
    event_time_window_hours: float = 6.0
    match_threshold: float = 0.82
    allowed_venues: set[str] = field(default_factory=set)
    fees: dict[str, FeeSpec] = field(default_factory=dict)
    rules: dict[str, dict[str, str]] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    db_path: str = "arb.db"

    def fee_fn(self, venue: str) -> FeeFn:
        spec = self.fees.get(venue)
        return spec.build() if spec else no_fee

    def venue_allowed(self, venue: str) -> bool:
        return not self.allowed_venues or venue in self.allowed_venues


def load(path: str | Path) -> Config:
    raw = tomllib.loads(Path(path).read_text())
    scan = raw.get("scan", {})
    cfg = Config(
        interval_seconds=scan.get("interval_seconds", 30),
        min_roi=scan.get("min_roi", 0.002),
        min_profit=scan.get("min_profit", 1.0),
        bankroll=scan.get("bankroll", 2000.0),
        sportsbook_max_stake=scan.get("sportsbook_max_stake", 500.0),
        on_rule_mismatch=scan.get("on_rule_mismatch", "warn"),
        event_time_window_hours=scan.get("event_time_window_hours", 6.0),
        match_threshold=scan.get("match_threshold", 0.82),
        db_path=scan.get("db_path", "arb.db"),
        allowed_venues=set(raw.get("venues", {}).get("allowed", [])),
        fees={k: FeeSpec(**v) for k, v in raw.get("fees", {}).items()},
        rules=raw.get("rules", {}),
        aliases={k.lower(): v.lower() for k, v in raw.get("aliases", {}).items()},
        sources=raw.get("sources", {}),
    )
    if cfg.on_rule_mismatch not in ("warn", "skip"):
        raise ValueError("scan.on_rule_mismatch must be 'warn' or 'skip'")
    return cfg
