"""The GitHub Pages site: one page per Digest at /YYYY/MM/DD/ and an index of all Digests."""

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


def full_story(story):
    return f"""<article>
<h3>{escape(story['title'])}</h3>
<div class="meta">{tags_html(story)}</div>
<p>{escape(story['summary'])}</p>
<details><summary>More</summary><p>{escape(story['more'])}</p>{links_html(story)}</details>
</article>"""


def compact_story(story):
    return f"""<article class="compact"><details>
<summary><b>{escape(story['title'])}</b><span class="meta">{tags_html(story)}</span></summary>
<p>{escape(story['summary'])}</p><p>{escape(story['more'])}</p>{links_html(story)}
</details></article>"""


def digest_page(date, stories, failed):
    parts = [f"<header><h1>AI Digest · {date}</h1>"]
    if stories:
        sources = len({i["source"] for s in stories for i in s["items"]})
        parts.append(f"<p>{len(stories)} Stories from {sources} Sources</p>")
    parts.append("</header>")
    if failed:
        parts.append(f'<p class="warning">⚠️ {escape(unavailable_note(failed))}</p>')
    if not stories:
        parts.append("<p>Nothing new since the last Digest.</p>")
    for lvl in config.LEVELS:
        group = [s for s in stories if s["level"] == lvl]
        if group:
            parts.append(f"<h2>{HEADINGS[lvl]}</h2>")
            render_one = compact_story if lvl == "muted" else full_story
            parts.extend(render_one(s) for s in group)
    return page(f"AI Digest · {date}", "\n".join(parts), root="../../../")


def index_page(dates):
    items = "".join(f'<li><a href="{d.replace("-", "/")}/">{d}</a></li>' for d in dates)
    body = (f"<header><h1>AI Digest</h1><p>A daily digest of what's new in AI.</p></header>"
            f'<ol class="digests">{items}</ol>')
    return page("AI Digest", body, root="./")


def write(date, stories, failed):
    """Write today's page and rebuild the index from every Digest on the branch."""
    day = config.SITE / date.replace("-", "/")
    day.mkdir(parents=True, exist_ok=True)
    (day / "index.html").write_text(digest_page(date, stories, failed))
    dates = sorted((p.stem for p in config.DIGESTS.glob("*.md")
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)), reverse=True)
    (config.SITE / "index.html").write_text(index_page(dates))
    (config.SITE / ".nojekyll").touch()  # Serve files as-is; don't run Jekyll.
