"""Price conversions. Internally every price is a probability: the cost of a $1 payout."""

from __future__ import annotations


def american_to_prob(american: float) -> float:
    if american == 0 or -100 < american < 100:
        raise ValueError(f"invalid American odds: {american}")
    if american > 0:
        return 100.0 / (american + 100.0)
    return -american / (-american + 100.0)


def prob_to_american(prob: float) -> float:
    if not 0 < prob < 1:
        raise ValueError(f"probability out of range: {prob}")
    if prob <= 0.5:
        return (1 - prob) / prob * 100.0
    return -prob / (1 - prob) * 100.0


def decimal_to_prob(decimal: float) -> float:
    if decimal <= 1:
        raise ValueError(f"invalid decimal odds: {decimal}")
    return 1.0 / decimal


def prob_to_decimal(prob: float) -> float:
    return 1.0 / prob


def parse_price(text: str) -> float:
    """Parse '+110', '-132', '2.10' (decimal) or '57c' / '0.57' (contract price) into a probability."""
    t = text.strip().lower()
    if t.endswith("c"):
        return float(t[:-1]) / 100.0
    if t.startswith(("+", "-")):
        return american_to_prob(float(t))
    v = float(t)
    if 0 < v < 1:
        return v
    if v >= 100:
        return american_to_prob(v)
    return decimal_to_prob(v)


def fmt_american(prob: float) -> str:
    a = prob_to_american(prob)
    return f"{a:+.0f}"
