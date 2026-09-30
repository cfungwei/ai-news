"""The GitHub Pages site: one page per day at /YYYY/MM/DD/ holding its Editions, and an index."""

import json
import re
from html import escape

from ainews import config
from ainews.render import HEADINGS, coverage_note, unavailable_note

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
header p, .meta, footer { color:var(--muted); font-size:14px; }
h1 { font-size:28px; margin:0 0 4px; }
h2 { font-size:13px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted);
     border-bottom:1px solid var(--line); padding-bottom:6px; margin:40px 0 8px; }
article { padding:16px 0; border-bottom:1px solid var(--line); }
article h3 { font-size:18px; line-height:1.35; margin:0 0 4px; }
.tag { display:inline-block; background:var(--tag-bg); border-radius:4px; padding:0 6px;
       font-size:12px; margin-right:4px; }
details summary { cursor:pointer; color:var(--accent); font-size:14px; margin-top:6px; }
details ul { padding-left:20px; font-size:14px; }
.compact summary { color:var(--fg); font-size:15px; }
.compact summary .meta { margin-left:4px; }
.warning { background:var(--card); border:1px solid var(--line); border-radius:6px;
           padding:10px 14px; font-size:14px; }
ol.digests { list-style:none; padding:0; }
ol.digests li { padding:10px 0; border-bottom:1px solid var(--line); }
article:target { background:var(--card); outline:2px solid var(--accent); outline-offset:6px;
                 border-radius:4px; }
.table { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th, td { text-align:right; padding:8px 6px; border-bottom:1px solid var(--line);
         white-space:nowrap; }
th { color:var(--muted); font-weight:600; font-size:12px; }
th:first-child, td.name { text-align:left; white-space:normal; }
.flag { color:var(--accent); font-size:12px; }
.edition h2 { font-size:20px; letter-spacing:0; text-transform:none; color:var(--fg);
              border-bottom:2px solid var(--fg); margin-top:48px; }
h3.level { font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted);
           margin:24px 0 4px; }
"""


def page(title, body, root):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><style>{STYLE}</style></head>
<body><main>{body}
<footer><p><a href="{root}">All Digests</a></p></footer></main></body></html>
"""


def tags_html(story):
    tags = "".join(f'<span class="tag">{escape(t)}</span>' for t in story["tags"])
    fallback = "" if story["tagged_by"] == "jev" else " (tagged by fallback)"
    return f"{tags}{fallback} · {coverage_note(story)}"


def links_html(story):
    return "<ul>" + "".join(
        f'<li><a href="{escape(i["url"])}">{escape(i["source_name"])}: {escape(i["title"])}</a></li>'
        for i in story["items"]) + "</ul>"


def anchor(edition, index):
    """Unique on the day's page, e.g. e1130-3 for the 3rd Story of the 11:30 Edition."""
    return f"e{edition.replace(':', '')}-{index + 1}"


def full_story(story, story_id):
    return f"""<article id="{story_id}">
<h3>{escape(story['title'])}</h3>
<div class="meta">{tags_html(story)}</div>
<p>{escape(story['summary'])}</p>
<details><summary>More</summary><p>{escape(story['more'])}</p>{links_html(story)}</details>
</article>"""


def compact_story(story, story_id):
    return f"""<article class="compact" id="{story_id}"><details>
<summary><b>{escape(story['title'])}</b><span class="meta">{tags_html(story)}</span></summary>
<p>{escape(story['summary'])}</p><p>{escape(story['more'])}</p>{links_html(story)}
</details></article>"""


def edition_section(saved):
    stories, failed, edition = saved["stories"], saved["failed"], saved["edition"]
    count = f"{len(stories)} Stories" if stories else "Nothing new"
    parts = [f'<section class="edition" id="e{edition.replace(":", "")}">'
             f"<h2>{edition} Edition · {count}</h2>"]
    if failed:
        parts.append(f'<p class="warning">⚠️ {escape(unavailable_note(failed))}</p>')
    for lvl in config.LEVELS:
        group = [s for s in stories if s["level"] == lvl]
        if group:
            parts.append(f'<h3 class="level">{HEADINGS[lvl]}</h3>')
            render_one = compact_story if lvl == "muted" else full_story
            parts.extend(render_one(s, anchor(edition, stories.index(s))) for s in group)
    return "\n".join(parts) + "</section>"


def digest_page(date, editions):
    """The day's page: every Edition published that day, newest first."""
    total = sum(len(e["stories"]) for e in editions)
    head = (f"<header><h1>AI Digest · {date}</h1>"
            f"<p>{len(editions)} Edition{'s' if len(editions) != 1 else ''} · "
            f"{total} Stories</p></header>")
    body = head + "\n".join(edition_section(e) for e in editions)
    return page(f"AI Digest · {date}", body, root="../../../")


def index_page(dates):
    items = "".join(f'<li><a href="{d.replace("-", "/")}/">{d}</a></li>' for d in dates)
    body = (f"<header><h1>AI Digest</h1><p>What's new in AI, four Editions a day. "
            f'<a href="health/">Source health</a></p></header>'
            f'<ol class="digests">{items}</ol>')
    return page("AI Digest", body, root="./")


def day_editions(date):
    saved = [json.loads(p.read_text()) for p in (config.SITE / "data").glob(f"{date}-*.json")]
    return sorted(saved, key=lambda e: e["edition"], reverse=True)


def write(date):
    """Rebuild the day's page from its Editions, and the index from every day."""
    day = config.SITE / date.replace("-", "/")
    day.mkdir(parents=True, exist_ok=True)
    (day / "index.html").write_text(digest_page(date, day_editions(date)))
    dates = sorted({p.stem[:10] for p in config.DIGESTS.glob("*.md")
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}", p.stem)}, reverse=True)
    (config.SITE / "index.html").write_text(index_page(dates))
    (config.SITE / ".nojekyll").touch()  # Serve files as-is; don't run Jekyll.
