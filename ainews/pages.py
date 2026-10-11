"""The GitHub Pages site.

    /                        index of days
    /YYYY/MM/DD/             the day's Editions, newest first, Stories grouped by primary Tag
    /YYYY/MM/DD/HHMM-N/      one Story: 👍/👎 at the top, then Summary, detail and Sources
    /health/                 Source health (see health.py)

Votes are stored by the Cloudflare Worker in worker/ (docs/adr/0002).
"""

import json
import re
from html import escape

from ainews import config
from ainews.render import coverage_note, group_heading, groups, unavailable_note

STYLE = """
:root { --bg:#fbfaf7; --fg:#1f1d1a; --muted:#6b665e; --line:#e4e0d8; --accent:#9a4d12;
        --tag-bg:#f0ebe2; --card:#ffffff; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161513; --fg:#ebe7df; --muted:#9d978c; --line:#2e2b27; --accent:#f0a35e;
          --tag-bg:#26231f; --card:#1d1b18; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font:16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width:720px; margin:0 auto; padding:32px 16px 64px; }
a { color:var(--accent); }
header p, .meta, footer, nav { color:var(--muted); font-size:14px; }
h1 { font-size:28px; line-height:1.25; margin:0 0 6px; }
h2 { font-size:20px; border-bottom:2px solid var(--fg); padding-bottom:4px; margin:44px 0 8px; }
h3 { font-size:13px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted);
     margin:22px 0 4px; }
ul.stories { list-style:none; padding:0; margin:0; }
ul.stories li { padding:8px 0; border-bottom:1px solid var(--line); }
ul.stories a { color:var(--fg); text-decoration:none; font-weight:600; }
ul.stories a:hover { color:var(--accent); }
ul.stories .meta { margin-left:6px; font-weight:400; }
.tag { display:inline-block; background:var(--tag-bg); border-radius:4px; padding:0 6px;
       font-size:12px; margin-right:4px; }
.summary { font-size:18px; }
.sources { padding-left:20px; font-size:14px; }
.warning { background:var(--card); border:1px solid var(--line); border-radius:6px;
           padding:10px 14px; font-size:14px; }
.votes { display:flex; gap:8px; margin:16px 0 20px; }
.votes button { font:inherit; font-size:16px; padding:6px 14px; border-radius:999px;
                border:1px solid var(--line); background:var(--card); color:var(--fg);
                cursor:pointer; min-width:72px; }
.votes button[aria-pressed="true"] { border-color:var(--accent); outline:1px solid var(--accent); }
.votes button:disabled { opacity:.5; cursor:default; }
ol.days { list-style:none; padding:0; }
ol.days li { padding:10px 0; border-bottom:1px solid var(--line); }
.table { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th, td { text-align:right; padding:8px 6px; border-bottom:1px solid var(--line);
         white-space:nowrap; }
th { color:var(--muted); font-weight:600; font-size:12px; }
th:first-child, td.name { text-align:left; white-space:normal; }
.flag { color:var(--accent); font-size:12px; }
"""


def page(title, body, root, script=""):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><style>{STYLE}</style></head>
<body><main>{body}
<footer><p><a href="{root}">All Digests</a></p></footer></main>{script}</body></html>
"""


# Story ids and paths

def story_id(saved, index):
    """e.g. 2026-10-11-1130-3: the 3rd Story of the 11:30 Edition on 11 October."""
    return f"{config.digest_key(saved['date'], saved['edition'])}-{index + 1}"


def story_path(sid):
    """2026-10-11-1130-3 -> 2026/10/11/1130-3/"""
    return f"{sid[:10].replace('-', '/')}/{sid[11:]}/"


def story_url(sid):
    return config.settings()["site_url"].rstrip("/") + "/" + story_path(sid)


# Story page

VOTE_SCRIPT = """<script>
(() => {
  const api = %(api)s, story = %(story)s;
  const bar = document.querySelector(".votes");
  if (!api) { bar.hidden = true; return; }
  let voter;
  try {
    voter = localStorage.getItem("ai-news-voter");
    if (!voter) { voter = crypto.randomUUID(); localStorage.setItem("ai-news-voter", voter); }
  } catch (e) { voter = crypto.randomUUID(); }
  const up = document.getElementById("up"), down = document.getElementById("down");
  let mine = 0;
  function show(c) {
    mine = c.mine;
    up.querySelector("span").textContent = c.up;
    down.querySelector("span").textContent = c.down;
    up.setAttribute("aria-pressed", mine === 1);
    down.setAttribute("aria-pressed", mine === -1);
    up.disabled = down.disabled = false;
  }
  async function call(path, options) {
    try { const r = await fetch(api + path, options); if (r.ok) show(await r.json()); }
    catch (e) { /* Votes are optional; the page works without them. */ }
  }
  function vote(v) {
    up.disabled = down.disabled = true;
    call("/vote", { method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ story, voter, vote: mine === v ? 0 : v }) });
  }
  up.onclick = () => vote(1);
  down.onclick = () => vote(-1);
  call("/votes?story=" + encodeURIComponent(story) + "&voter=" + encodeURIComponent(voter));
})();
</script>"""


def story_page(story, sid, saved):
    tags = "".join(f'<span class="tag">{escape(t)}</span>' for t in story["tags"])
    fallback = "" if story["tagged_by"] == "jev" else " (tagged by fallback)"
    sources = "".join(
        f'<li><a href="{escape(i["url"])}">{escape(i["source_name"])}: {escape(i["title"])}</a></li>'
        for i in story["items"])
    body = f"""<nav><a href="../">← AI Digest · {saved['date']}</a> · {saved['edition']} Edition</nav>
<div class="votes">
<button id="up" aria-label="Thumbs up" disabled>👍 <span>–</span></button>
<button id="down" aria-label="Thumbs down" disabled>👎 <span>–</span></button>
</div>
<h1>{escape(story['title'])}</h1>
<p class="meta">{tags}{fallback} · {coverage_note(story)}</p>
<p class="summary">{escape(story['summary'])}</p>
<p>{escape(story['more'])}</p>
<h3>Sources</h3>
<ul class="sources">{sources}</ul>"""
    script = VOTE_SCRIPT % {"api": json.dumps(config.settings().get("votes_url") or ""),
                            "story": json.dumps(sid)}
    return page(story["title"], body, root="../../../../", script=script)


# Day page and index

def edition_section(saved, tag_order):
    stories = saved["stories"]
    count = f"{len(stories)} Stories" if stories else "Nothing new"
    parts = [f"<section><h2>{saved['edition']} Edition · {count}</h2>"]
    if saved["failed"]:
        parts.append(f'<p class="warning">⚠️ {escape(unavailable_note(saved["failed"]))}</p>')
    for tag, group in groups(stories, tag_order):
        parts.append(f"<h3>{group_heading(tag)}</h3><ul class=\"stories\">")
        for story in group:
            sid = story_id(saved, stories.index(story))
            parts.append(f'<li><a href="{sid[11:]}/">{escape(story["title"])}</a>'
                         f'<span class="meta">{coverage_note(story)}</span></li>')
        parts.append("</ul>")
    return "\n".join(parts) + "</section>"


def day_page(date, editions, tag_order):
    total = sum(len(e["stories"]) for e in editions)
    head = (f"<header><h1>AI Digest · {date}</h1>"
            f"<p>{len(editions)} Edition{'s' if len(editions) != 1 else ''} · "
            f"{total} Stories</p></header>")
    body = head + "\n".join(edition_section(e, tag_order) for e in editions)
    return page(f"AI Digest · {date}", body, root="../../../")


def index_page(dates):
    items = "".join(f'<li><a href="{d.replace("-", "/")}/">{d}</a></li>' for d in dates)
    body = (f"<header><h1>AI Digest</h1><p>What's new in AI, four Editions a day. "
            f'<a href="health/">Source health</a></p></header>'
            f'<ol class="days">{items}</ol>')
    return page("AI Digest", body, root="./")


def day_editions(date):
    saved = [json.loads(p.read_text()) for p in (config.SITE / "data").glob(f"{date}-*.json")]
    return sorted(saved, key=lambda e: e["edition"], reverse=True)


def all_dates():
    return sorted({p.stem[:10] for p in (config.SITE / "data").glob("*.json")
                   if re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}", p.stem)}, reverse=True)


def write(date):
    """Rebuild the day's page and its Story pages, and the index of days."""
    tag_order = list(config.tags())
    editions = day_editions(date)
    day = config.SITE / date.replace("-", "/")
    day.mkdir(parents=True, exist_ok=True)
    (day / "index.html").write_text(day_page(date, editions, tag_order))
    for saved in editions:
        for index, story in enumerate(saved["stories"]):
            sid = story_id(saved, index)
            out = config.SITE / story_path(sid)
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(story_page(story, sid, saved))
    (config.SITE / "index.html").write_text(index_page(all_dates()))
    (config.SITE / ".nojekyll").touch()  # Serve files as-is; don't run Jekyll.


def write_all():
    for date in all_dates():
        write(date)
