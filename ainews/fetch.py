"""fetch: collect new Items from every Source into build/items.json.

An Item is new if it has not been seen in a previous Digest and, for Sources that
give publish dates, was published since the previous successful Digest (or within
`first_run_lookback_hours` on the first Run). A Source that fails after
`fetch_attempts` tries is recorded under `sources_failed`; the Run carries on.
"""

import calendar
import html
import json
import re
import time
from datetime import datetime, timedelta, timezone

import feedparser
import httpx

from ainews import config

USER_AGENT = "Mozilla/5.0 (compatible; ai-news digest; +https://github.com/)"
EXCERPT_CHARS = 500


def load_state():
    if config.SEEN_FILE.exists():
        return json.loads(config.SEEN_FILE.read_text())
    return {"last_digest": None, "source_ok": {}, "seen": {}, "baselined": []}


def save_state(state):
    config.STATE.mkdir(exist_ok=True)
    config.SEEN_FILE.write_text(json.dumps(state, indent=1, sort_keys=True))


def get(client, url, params=None):
    attempts = config.settings()["fetch_attempts"]
    for attempt in range(attempts):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPError:
            if attempt == attempts - 1:
                raise
            time.sleep(2**attempt)


def clean(text):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:EXCERPT_CHARS]


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def item(source, key, title, url, published, excerpt):
    return {
        "id": f"{source['id']}:{key}",
        "source": source["id"],
        "source_name": source["name"],
        "title": clean(title),
        "url": url,
        "published": iso(published),
        "excerpt": clean(excerpt),
    }


def fetch_feed(client, source, since, state):
    parsed = feedparser.parse(get(client, source["url"]).content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"unparseable feed: {parsed.bozo_exception}")
    # `limit` keeps only the first entries, for feeds already sorted by rank (e.g. Reddit top).
    for entry in parsed.entries[: source.get("limit")]:
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = datetime.fromtimestamp(calendar.timegm(stamp), timezone.utc) if stamp else None
        if published and published < since:
            continue
        key = entry.get("id") or entry.get("link")
        yield item(source, key, entry.get("title"), entry.get("link"), published,
                   entry.get("summary"))


def fetch_hf_papers(client, source, since, state):
    papers = [p["paper"] for p in get(client, source["url"]).json()]
    for paper in papers:
        paper["daily"] = datetime.fromisoformat(paper["submittedOnDailyAt"].replace("Z", "+00:00"))
    # Daily Papers are stamped at midnight UTC, so compare dates rather than times.
    recent = [p for p in papers if p["daily"].date() >= since.date()]
    recent.sort(key=lambda p: p.get("upvotes", 0), reverse=True)
    for paper in recent[: source.get("limit", 15)]:
        yield item(source, paper["id"], paper["title"],
                   f"https://huggingface.co/papers/{paper['id']}",
                   paper["daily"], paper.get("summary"))


def fetch_hf_trending(client, source, since, state):
    for model in get(client, source["url"]).json()[: source.get("limit", 10)]:
        created = model.get("createdAt")
        details = ", ".join(filter(None, [model.get("pipeline_tag"),
                                          f"{model.get('likes', 0)} likes",
                                          f"{model.get('downloads', 0)} downloads"]))
        yield item(source, model["id"], f"Trending model: {model['id']}",
                   f"https://huggingface.co/{model['id']}",
                   datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
                   f"{details}. Tags: {', '.join(model.get('tags', [])[:12])}")


def fetch_hn(client, source, since, state):
    params = {
        "tags": "story",
        "numericFilters": f"created_at_i>{int(since.timestamp())},points>{source['min_points']}",
        "hitsPerPage": 500,
    }
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in source["keywords"]) + r")\b",
                         re.IGNORECASE)
    for hit in get(client, source["url"], params).json()["hits"]:
        title = hit.get("title") or ""
        if not pattern.search(title):
            continue
        discussion = f"https://news.ycombinator.com/item?id={hit['objectID']}"
        yield item(source, hit["objectID"], title, hit.get("url") or discussion,
                   datetime.fromtimestamp(hit["created_at_i"], timezone.utc),
                   f"{hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments. "
                   f"Discussion: {discussion}")


def baseline_key(source):
    return f"{source['id']} {source['link_pattern']}"


def fetch_page(client, source, since, state):
    links = dict.fromkeys(re.findall(source["link_pattern"], get(client, source["url"]).text))
    urls = [source.get("base_url", "") + link for link in links]
    key = baseline_key(source)
    if key not in state["baselined"]:
        # No publish dates: record the links already on the page as seen instead of emitting
        # them. Keyed by pattern, so widening a pattern doesn't flood the Digest with old links.
        seen = state["seen"].setdefault(source["id"], [])
        seen.extend(i for i in (f"{source['id']}:{u}" for u in urls) if i not in seen)
        state["baselined"] = [k for k in state["baselined"]
                              if k.split(" ", 1)[0] != source["id"]] + [key]
        return
    for url in urls:
        slug = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
        yield item(source, url, slug.capitalize(), url, None, "")


FETCHERS = {
    "feed": fetch_feed,
    "hf_papers": fetch_hf_papers,
    "hf_trending": fetch_hf_trending,
    "hn": fetch_hn,
    "page": fetch_page,
}


def main():
    started = datetime.now(timezone.utc)
    state = load_state()
    lookback = timedelta(hours=config.settings()["first_run_lookback_hours"])
    default_since = (datetime.fromisoformat(state["last_digest"]) if state["last_digest"]
                     else started - lookback)

    items, failed = [], []
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30,
                      follow_redirects=True) as client:
        for source in config.sources():
            seen = set(state["seen"].get(source["id"], []))
            # A Source that failed in earlier Runs keeps its window open until it succeeds.
            last_ok = state.get("source_ok", {}).get(source["id"])
            since = min(default_since, datetime.fromisoformat(last_ok)) if last_ok else default_since
            try:
                found = list(FETCHERS[source["kind"]](client, source, since, state))
            except Exception as error:
                failed.append({"source": source["id"], "name": source["name"],
                               "error": f"{type(error).__name__}: {error}"[:300]})
                print(f"FAILED  {source['name']}: {error}")
                continue
            new = [i for i in found if i["id"] not in seen]
            items.extend(new)
            print(f"{len(new):4d}  {source['name']}")

    save_state(state)  # Persists page baselines only; seen Items are recorded by render.
    config.BUILD.mkdir(exist_ok=True)
    config.ITEMS_FILE.write_text(json.dumps({
        "fetched_at": iso(started),
        "since": iso(default_since),
        "sources_failed": failed,
        "items": items,
    }, indent=1, ensure_ascii=False))
    print(f"{len(items)} new Items, {len(failed)} Sources failed -> {config.ITEMS_FILE}")


if __name__ == "__main__":
    main()
