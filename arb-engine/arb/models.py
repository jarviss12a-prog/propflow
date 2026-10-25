from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Outcomes per market kind. Spread lines are stored from the home side's perspective
# (home -7.5 => line -7.5; the away outcome on that key is away +7.5).
TWO_WAY = {
    "moneyline": ("home", "away"),
    "spread": ("home", "away"),
    "total": ("over", "under"),
}
THREE_WAY_MONEYLINE = ("home", "away", "draw")

FLIP = {"home": "away", "away": "home"}


def sport_family(sport: str) -> str:
    return sport.split("_", 1)[0]


def required_outcomes(sport: str, kind: str) -> tuple[str, ...]:
    if kind == "moneyline" and sport_family(sport) == "soccer":
        return THREE_WAY_MONEYLINE
    return TWO_WAY[kind]


@dataclass
class Level:
    """`size` is the max payout (number of $1 contracts) available at `price`; None = unknown."""

    price: float
    size: float | None = None


@dataclass
class RawQuote:
    """One venue's price ladder for one outcome, before cross-venue event matching."""

    venue: str
    sport: str
    home: str
    away: str
    start: datetime | None
    kind: str
    line: float | None
    outcome: str
    levels: list[Level]
    url: str | None = None
    ref: str | None = None
    # True when the source can't say which team is home (tennis, Kalshi titles, ...).
    neutral: bool = False

    def flipped(self) -> "RawQuote":
        line = self.line
        if self.kind == "spread" and line is not None:
            line = -line
        return RawQuote(
            venue=self.venue,
            sport=self.sport,
            home=self.away,
            away=self.home,
            start=self.start,
            kind=self.kind,
            line=line,
            outcome=FLIP.get(self.outcome, self.outcome),
            levels=self.levels,
            url=self.url,
            ref=self.ref,
            neutral=self.neutral,
        )


@dataclass
class Fill:
    venue: str
    outcome: str
    price: float
    contracts: float
    fee: float
    url: str | None = None
    ref: str | None = None

    @property
    def cost(self) -> float:
        return self.contracts * self.price + self.fee


@dataclass
class Opportunity:
    event_id: str
    sport: str
    home: str
    away: str
    start: datetime | None
    kind: str
    line: float | None
    fills: list[Fill]
    total_cost: float
    min_payout: float
    # Best-price sum of implied probabilities after fees at the top of each ladder.
    top_book_sum: float
    warnings: list[str] = field(default_factory=list)

    @property
    def profit(self) -> float:
        return self.min_payout - self.total_cost

    @property
    def roi(self) -> float:
        return self.profit / self.total_cost if self.total_cost else 0.0

    @property
    def key(self) -> str:
        venues = ",".join(sorted({f"{f.outcome}:{f.venue}" for f in self.fills}))
        return f"{self.event_id}|{self.kind}|{self.line}|{venues}"

    def describe_market(self) -> str:
        if self.kind == "moneyline":
            return "Moneyline"
        if self.kind == "total":
            return f"Total {self.line:g}"
        return f"Spread {self.home} {self.line:+g}"
