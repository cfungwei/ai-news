"""render: turn build/items.json + build/stories.json into digests/<date>.md.

Stories are ordered by Preference level (preferred, neutral, muted), then by
Coverage, then newest first. Muted Stories are rendered compactly. With
--record, the Items are marked as seen and this Digest becomes the start of the
next Digest's window.
"""

import argparse
import json
from datetime import datetime

from ainews import config
from ainews.fetch import load_state, save_state


class InvalidStories(ValueError):
    pass


def validate(items, stories):
    problems = []
    known_tags = set(config.tags())
    assigned = {}
    for n, story in enumerate(stories, 1):
        for field in ("title", "tags", "tagged_by", "summary", "more", "item_ids"):
            if not story.get(field):
                problems.append(f"Story {n} has no {field}")
        for tag in story.get("tags", []):
            if tag not in known_tags:
                problems.append(f"Story {n} has unknown Tag {tag!r}")
        for item_id in story.get("item_ids", []):
            if item_id in assigned:
                problems.append(f"Item {item_id} is in Stories {assigned[item_id]} and {n}")
            assigned[item_id] = n
    for item_id in set(items) - set(assigned):
        problems.append(f"Item {item_id} is in no Story")
    for item_id in set(assigned) - set(items):
        problems.append(f"Story {assigned[item_id]} lists unknown Item {item_id}")
    if problems:
        raise InvalidStories("\n".join(problems))


def level(story, preferences):
    ranks = [config.LEVELS.index(preferences.get(tag, "neutral")) for tag in story["tags"]]
    return config.LEVELS[min(ranks)]


def enrich(stories, items):
    preferences = config.preferences()
    for story in stories:
        story["items"] = [items[i] for i in story["item_ids"]]
        story["coverage"] = len({i["source"] for i in story["items"]})
        story["level"] = level(story, preferences)
        story["newest"] = max((i["published"] or "" for i in story["items"]), default="")
    return sorted(stories, key=lambda s: (config.LEVELS.index(s["level"]), -s["coverage"],
                                          _desc(s["newest"])))


def _desc(text):
    # Sort key that orders ISO timestamps newest first.
    return [-ord(c) for c in text]


def tag_list(story):
    marker = "" if story["tagged_by"] == "jev" else " (tagged by fallback)"
    return " ".join(f"`{t}`" for t in story["tags"]) + marker


def links(story):
    return "\n".join(f"- [{i['source_name']}: {i['title']}]({i['url']})" for i in story["items"])


def coverage_note(story):
    n = story["coverage"]
    return f"{n} source{'s' if n != 1 else ''}"


def full_story(story):
    return (f"### {story['title']}\n"
            f"{tag_list(story)} · {coverage_note(story)}\n\n"
            f"{story['summary']}\n\n"
            f"<details><summary>More</summary>\n\n{story['more']}\n\n{links(story)}\n\n"
            f"</details>\n")


def compact_story(story):
    return (f"<details><summary><b>{story['title']}</b> · {tag_list(story)} · "
            f"{coverage_note(story)}</summary>\n\n{story['summary']}\n\n{story['more']}\n\n"
            f"{links(story)}\n\n</details>\n")


def digest(date, stories, fetched):
    lines = [f"# AI Digest · {date}\n"]
    failed = fetched["sources_failed"]
    if failed:
        names = ", ".join(f["name"] for f in failed)
        lines.append(f"> ⚠️ Unavailable today: {names}. Their news will appear in a later Digest.\n")
    if not stories:
        lines.append("Nothing new since the last Digest.\n")
        return "\n".join(lines)

    sources = len({i["source"] for s in stories for i in s["items"]})
    lines.append(f"_{len(stories)} Stories from {sources} Sources._\n")
    headings = {"preferred": "Preferred", "neutral": "Also new", "muted": "Muted"}
    for lvl in config.LEVELS:
        group = [s for s in stories if s["level"] == lvl]
        if not group:
            continue
        lines.append(f"## {headings[lvl]}\n")
        render_one = compact_story if lvl == "muted" else full_story
        lines.extend(render_one(s) for s in group)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true",
                        help="mark Items as seen and start the next window from this fetch")
    args = parser.parse_args()

    fetched = json.loads(config.ITEMS_FILE.read_text())
    items = {i["id"]: i for i in fetched["items"]}
    stories = json.loads(config.STORIES_FILE.read_text())["stories"] if items else []
    validate(items, stories)

    date = config.today()
    config.DIGESTS.mkdir(exist_ok=True)
    path = config.DIGESTS / f"{date}.md"
    path.write_text(digest(date, enrich(stories, items), fetched))
    print(f"{len(stories)} Stories -> {path}")

    if args.record:
        state = load_state()
        for item in fetched["items"]:
            state["seen"].setdefault(item["source"], []).append(item["id"])
        failed = {f["source"] for f in fetched["sources_failed"]}
        for source in config.sources():
            if source["id"] not in failed:
                state.setdefault("source_ok", {})[source["id"]] = fetched["fetched_at"]
        state["last_digest"] = fetched["fetched_at"]
        save_state(state)
        print(f"Recorded {len(items)} Items as seen; next window starts {fetched['fetched_at']}")


if __name__ == "__main__":
    main()
