"""Venue fee models.

Each model returns the fee in dollars for buying `contracts` $1-payout contracts at
probability price `p` in a single order. Sportsbooks bake their margin into the price,
so they use the "none" model.

The coefficients live in config.toml because venues change them. Verify them against
each venue's current fee schedule before trusting a result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

FeeFn = Callable[[float, float], float]


def _ceil_cent(x: float) -> float:
    # Small epsilon so 0.0700000001 from float error doesn't round up a full cent.
    return math.ceil(round(x * 100, 6)) / 100.0


def no_fee(contracts: float, p: float) -> float:
    return 0.0


def kalshi_fee(coef: float) -> FeeFn:
    """Kalshi: ceil_to_cent(coef * C * P * (1 - P)). Taker coef has been 0.07."""

    def fn(contracts: float, p: float) -> float:
        if contracts <= 0:
            return 0.0
        return _ceil_cent(coef * contracts * p * (1 - p))

    return fn


def min_side_fee(rate: float) -> FeeFn:
    """rate * C * min(P, 1 - P): the shape Polymarket uses on fee-enabled markets."""

    def fn(contracts: float, p: float) -> float:
        return rate * contracts * min(p, 1 - p)

    return fn


def pct_of_stake(rate: float) -> FeeFn:
    def fn(contracts: float, p: float) -> float:
        return rate * contracts * p

    return fn


@dataclass(frozen=True)
class FeeSpec:
    model: str = "none"
    coef: float = 0.0

    def build(self) -> FeeFn:
        if self.model == "none":
            return no_fee
        if self.model == "kalshi":
            return kalshi_fee(self.coef)
        if self.model == "min_side":
            return min_side_fee(self.coef)
        if self.model == "pct_of_stake":
            return pct_of_stake(self.coef)
        raise ValueError(f"unknown fee model: {self.model}")
