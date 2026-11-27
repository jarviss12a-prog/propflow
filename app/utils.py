"""Small helpers: money in cents, dates, months."""
import calendar
import os
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo


# ---------- money (always stored as integer cents) ----------

def parse_money(value, allow_blank=False):
    """'$1,250.50' -> 125050. '(40)' and '-40' are negative."""
    s = "" if value is None else str(value).strip()
    if not s:
        if allow_blank:
            return None
        raise ValueError("Enter an amount.")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    s = s.replace("$", "").replace(",", "").replace(" ", "")
    if s.startswith("-"):
        neg, s = (not neg), s[1:]
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"“{value}” isn't an amount.")
    if not d.is_finite():
        raise ValueError(f"“{value}” isn't an amount.")
    cents = int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return -cents if neg else cents


def fmt_money(cents, dash_zero=False, whole=False):
    if cents is None:
        return ""
    cents = int(cents)
    if dash_zero and cents == 0:
        return "–"
    neg, c = cents < 0, abs(cents)
    if whole:
        s = f"${round(c / 100):,}"
    else:
        s = f"${c // 100:,}.{c % 100:02d}"
    return f"−{s}" if neg else s


def cents_plain(cents):
    """For CSV and form inputs: 125050 -> '1250.50'."""
    if cents is None:
        return ""
    cents = int(cents)
    neg, c = cents < 0, abs(cents)
    return f"{'-' if neg else ''}{c // 100}.{c % 100:02d}"


# ---------- dates ----------

def local_today():
    tz = os.environ.get("PROPFLOW_TZ", "America/Indiana/Indianapolis")
    try:
        return datetime.now(ZoneInfo(tz)).date()
    except Exception:
        return date.today()


_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y", "%b %d %Y", "%B %d %Y",
                 "%b %d, %Y", "%B %d, %Y"]


def parse_date(value, allow_blank=False):
    """Accepts 2026-03-01, 3/1/2026, 3/1/26, Mar 1 2026. Returns ISO string."""
    s = "" if value is None else str(value).strip()
    if not s:
        if allow_blank:
            return None
        raise ValueError("Enter a date.")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"“{value}” isn't a date. Use 2026-03-01 or 3/1/2026.")


def to_date(iso):
    return date.fromisoformat(iso) if iso else None


def fmt_date(iso, short=False):
    if not iso:
        return ""
    d = to_date(iso) if isinstance(iso, str) else iso
    if short:
        return f"{d.strftime('%b')} {d.day}"
    return f"{d.strftime('%b')} {d.day}, {d.year}"


# ---------- months (YYYY-MM strings) ----------

_YM = re.compile(r"^(\d{4})-(\d{2})$")


def ym_of(d):
    if isinstance(d, str):
        d = to_date(d)
    return f"{d.year:04d}-{d.month:02d}"


def parse_ym(value, allow_blank=False):
    s = "" if value is None else str(value).strip()
    if not s:
        if allow_blank:
            return None
        raise ValueError("Enter a month.")
    m = _YM.match(s)
    if m and 1 <= int(m.group(2)) <= 12:
        return s
    for fmt in ("%m/%Y", "%m/%y", "%b %Y", "%B %Y", "%b-%Y", "%b-%y", "%Y/%m"):
        try:
            d = datetime.strptime(s, fmt)
            return f"{d.year:04d}-{d.month:02d}"
        except ValueError:
            continue
    try:  # a full date works too
        return ym_of(parse_date(s))
    except ValueError:
        raise ValueError(f"“{value}” isn't a month. Use 2026-03.")


def ym_parts(ym):
    y, m = ym.split("-")
    return int(y), int(m)


def month_first(ym):
    y, m = ym_parts(ym)
    return date(y, m, 1)


def month_last(ym):
    y, m = ym_parts(ym)
    return date(y, m, calendar.monthrange(y, m)[1])


def add_months(ym, n):
    y, m = ym_parts(ym)
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def months_between(start_ym, end_ym):
    """Inclusive list of months. Empty if start > end."""
    out, cur = [], start_ym
    while cur <= end_ym:
        out.append(cur)
        cur = add_months(cur, 1)
    return out


def month_label(ym, short=False):
    d = month_first(ym)
    return d.strftime("%b %Y" if short else "%B %Y")
