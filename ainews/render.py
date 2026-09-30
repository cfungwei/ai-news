"""render: validate curated Stories, order them, and write the Markdown Digest.

Stories are ordered by Preference level (preferred, neutral, muted), then by
Coverage, then newest first. Muted Stories are rendered compactly.
"""

from ainews import config


# Limits from routine/PROMPT.md, enforced so the routine rewrites Stories that break them.
TITLE_CHARS = 90
SUMMARY_WORDS = 45


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
        if len(story.get("title") or "") > TITLE_CHARS:
            problems.append(f"Story {n} title is over {TITLE_CHARS} characters")
        if len((story.get("summary") or "").split()) > SUMMARY_WORDS:
            problems.append(f"Story {n} summary is over {SUMMARY_WORDS} words")
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
    """A Story takes the highest level among its Tags."""
    ranks = [config.LEVELS.index(preferences.get(tag, "neutral")) for tag in story["tags"]]
    return config.LEVELS[min(ranks)]


def order(stories, items, preferences):
    """Attach Items, Coverage and level to each Story and return them in Digest order."""
    for story in stories:
        story["items"] = [items[i] for i in story["item_ids"]]
        story["coverage"] = len({i["source"] for i in story["items"]})
        story["level"] = level(story, preferences)
        story["newest"] = max((i["published"] or "" for i in story["items"]), default="")
    by_newest = sorted(stories, key=lambda s: s["newest"], reverse=True)
    return sorted(by_newest, key=lambda s: (config.LEVELS.index(s["level"]), -s["coverage"]))


def top(stories, n):
    """The Telegram top N: preferred first, topped up from neutral, never muted."""
    return [s for s in stories if s["level"] != "muted"][:n]


HEADINGS = {"preferred": "Preferred", "neutral": "Also new", "muted": "Muted"}


def tag_list(story):
    marker = "" if story["tagged_by"] == "jev" else " (tagged by fallback)"
    return " ".join(f"`{t}`" for t in story["tags"]) + marker


def coverage_note(story):
    n = story["coverage"]
    return f"{n} source{'s' if n != 1 else ''}"


def links(story):
    return "\n".join(f"- [{i['source_name']}: {i['title']}]({i['url']})" for i in story["items"])


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


def unavailable_note(failed):
    names = ", ".join(f["name"] for f in failed)
    return f"Unavailable today: {names}. Their news will appear in a later Digest."


def markdown(title, stories, failed):
    lines = [f"# {title}\n"]
    if failed:
        lines.append(f"> ⚠️ {unavailable_note(failed)}\n")
    if not stories:
        lines.append("Nothing new since the last Digest.\n")
        return "\n".join(lines)

    sources = len({i["source"] for s in stories for i in s["items"]})
    lines.append(f"_{len(stories)} Stories from {sources} Sources._\n")
    for lvl in config.LEVELS:
        group = [s for s in stories if s["level"] == lvl]
        if group:
            lines.append(f"## {HEADINGS[lvl]}\n")
            render_one = compact_story if lvl == "muted" else full_story
            lines.extend(render_one(s) for s in group)
    return "\n".join(lines)
