"""Jinja filters and globals used by the templates."""
from flask import request

from .constants import CATEGORY_BY_KEY, KIND_BY_KEY
from .utils import cents_plain, fmt_date, fmt_money, local_today, month_label, ym_of

STATUS_LABELS = {"paid": "Paid", "partial": "Partial", "late": "Late", "due": "Due", "upcoming": "Upcoming"}


def register(app):
    app.jinja_env.filters.update(
        money=fmt_money,
        money0=lambda c: fmt_money(c, whole=True),
        plain=cents_plain,
        d=fmt_date,
        dshort=lambda s: fmt_date(s, short=True),
        month=month_label,
        mshort=lambda s: month_label(s, short=True),
        cat=lambda k: CATEGORY_BY_KEY.get(k, {}).get("label", k),
        catline=lambda k: CATEGORY_BY_KEY.get(k, {}).get("line"),
        kind=lambda k: KIND_BY_KEY.get(k, {}).get("label", k),
        status=lambda s: STATUS_LABELS.get(s, s),
        tel=lambda p: "".join(ch for ch in (p or "") if ch.isdigit() or ch == "+"),
        pairs=lambda rows, v, l: [(r[v], r[l]) for r in rows],
        same=lambda items: [(i, i) for i in items],
        filesize=lambda n: f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB",
    )

    @app.context_processor
    def globals_():
        return {"today_iso": local_today().isoformat(), "this_month": ym_of(local_today()),
                "nav": request.endpoint or ""}
