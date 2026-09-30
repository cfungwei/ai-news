"""Source health: how each Source has done over the last 7 and 30 days.

Built from the saved Digests (data/<date>.json) and the owner's Feedback. A Source is
flagged, never dropped: the owner decides by editing config/sources.yaml.
"""

import json
from datetime import date as Date, timedelta
from html import escape

from ainews import config

SILENT_DAYS = 7
FAILING_DAYS = 3  # Flag a Source that failed on this many of the last 7 days.


def digests():
    """Every saved Edition as {key: data}."""
    return {p.stem: json.loads(p.read_text())
            for p in sorted((config.SITE / "data").glob("*.json"))}


def rows(saved, feedback, sources, today):
    today = Date.fromisoformat(today)
    week, month = today - timedelta(days=6), today - timedelta(days=29)
    first = min((Date.fromisoformat(d["date"]) for d in saved.values()), default=today)
    result = []
    for source in sources:
        row = {"id": source["id"], "name": source["name"], "items7": 0, "items30": 0,
               "preferred7": 0, "preferred30": 0, "failed7": 0, "last_item": None,
               "up": 0, "down": 0, "flags": []}
        failed_days = set()
        for data in saved.values():
            day = data["date"]
            when = Date.fromisoformat(day)
            if when < month:
                continue
            recent = when >= week
            if recent and any(f["source"] == source["id"] for f in data["failed"]):
                failed_days.add(day)  # Days, not Editions: several Editions run each day.
            for story in data["stories"]:
                count = sum(1 for i in story["items"] if i["source"] == source["id"])
                if not count:
                    continue
                row["last_item"] = max(row["last_item"] or day, day)
                row["items30"] += count
                row["items7"] += count if recent else 0
                if story["level"] == "preferred":
                    row["preferred30"] += count
                    row["preferred7"] += count if recent else 0
        row["failed7"] = len(failed_days)
        for entry in feedback.values():
            if Date.fromisoformat(entry["date"]) >= month and source["id"] in entry["sources"]:
                row["up"] += entry["up"]
                row["down"] += entry["down"]

        if row["items7"] == 0 and first <= week:
            row["flags"].append(f"no Items in {SILENT_DAYS} days")
        if row["failed7"] >= FAILING_DAYS:
            row["flags"].append(f"failed on {row['failed7']} of the last 7 days")
        if row["down"] > row["up"]:
            row["flags"].append("more 👎 than 👍")
        result.append(row)
    return sorted(result, key=lambda r: (not r["flags"], -r["items30"]))


def page(report, today, tracked_since):
    from ainews.pages import page as layout

    def cell(value):
        return f"<td>{value}</td>"

    body_rows = "".join(
        "<tr>" + f'<td class="name">{escape(r["name"])}'
        + (f'<div class="flag">⚑ {escape("; ".join(r["flags"]))}</div>' if r["flags"] else "")
        + "</td>" + cell(r["items7"]) + cell(r["items30"]) + cell(r["preferred30"])
        + cell(r["failed7"]) + cell(f"{r['up']} / {r['down']}") + cell(r["last_item"] or "—")
        + "</tr>" for r in report)
    body = f"""<header><h1>Source health</h1>
<p>Updated {today}. Tracking since {tracked_since}. Flags are suggestions; Sources are only
added or dropped by editing <code>config/sources.yaml</code>.</p></header>
<div class="table"><table>
<thead><tr><th>Source</th><th>Items 7d</th><th>Items 30d</th><th>Preferred 30d</th>
<th>Failed 7d</th><th>👍 / 👎 30d</th><th>Last Item</th></tr></thead>
<tbody>{body_rows}</tbody></table></div>"""
    return layout("Source health", body, root="../")


def write(state):
    """Rebuild /health/ and return the report rows."""
    saved = digests()
    today = config.today()
    report = rows(saved, state.get("feedback", {}), config.sources(), today)
    out = config.SITE / "health"
    out.mkdir(exist_ok=True)
    tracked_since = min((d["date"] for d in saved.values()), default=today)
    (out / "index.html").write_text(page(report, today, tracked_since))
    return report


def url():
    return config.settings()["site_url"].rstrip("/") + "/health/"
