from __future__ import annotations

from datetime import datetime


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip().replace(" ", "T", 1)
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    elif v.endswith("+00"):
        v += ":00"
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None
