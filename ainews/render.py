"""render: validate curated Stories, order them, and write the Markdown Digest.

Stories are grouped by their primary (first) Tag. The biggest group comes first and
`other` always last; inside a group, Stories are ordered by Coverage, then newest first.
"""

from ainews import config

# Limits from routine/PROMPT.md, enforced so the routine rewrites Stories that break them.
TITLE_CHARS = 90
SUMMARY_WORDS = 45

EMOJI = {"models": "🧠", "research": "📄", "agents": "🤖", "tools": "🛠", "open-source": "🔓",
         "products": "📱", "industry": "💼", "policy": "⚖️", "hardware": "🔌", "robotics": "🦾",
         "other": "📰"}


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


def groups(stories, tag_order):
    """[(tag, Stories)] by primary Tag: biggest group first, `other` last, ties in Tag order."""
    by_tag = {}
    for story in stories:
        by_tag.setdefault(story["tags"][0], []).append(story)
    rank = {tag: n for n, tag in enumerate(tag_order)}
    return sorted(by_tag.items(),
                  key=lambda g: (g[0] == "other", -len(g[1]), rank.get(g[0], len(rank))))


def order(stories, items, tag_order):
    """Attach Items and Coverage to each Story and return them in Digest order."""
    for story in stories:
        story["items"] = [items[i] for i in story["item_ids"]]
        story["coverage"] = len({i["source"] for i in story["items"]})
        story["newest"] = max((i["published"] or "" for i in story["items"]), default="")
    by_newest = sorted(stories, key=lambda s: s["newest"], reverse=True)
    by_coverage = sorted(by_newest, key=lambda s: -s["coverage"])
    return [s for _, group in groups(by_coverage, tag_order) for s in group]


def group_heading(tag):
    return f"{EMOJI.get(tag, '📰')} {tag.replace('-', ' ').capitalize()}"


def tag_list(story):
    marker = "" if story["tagged_by"] == "jev" else " (tagged by fallback)"
    return " ".join(f"`{t}`" for t in story["tags"]) + marker


def coverage_note(story):
    n = story["coverage"]
    return f"{n} source{'s' if n != 1 else ''}"


def links(story):
    return "\n".join(f"- [{i['source_name']}: {i['title']}]({i['url']})" for i in story["items"])


def story_markdown(story):
    return (f"### {story['title']}\n"
            f"{tag_list(story)} · {coverage_note(story)}\n\n"
            f"{story['summary']}\n\n"
            f"<details><summary>More</summary>\n\n{story['more']}\n\n{links(story)}\n\n"
            f"</details>\n")


def unavailable_note(failed):
    names = ", ".join(f["name"] for f in failed)
    return f"Unavailable this Edition: {names}. Their news will appear in a later Edition."


def markdown(title, stories, failed, tag_order):
    lines = [f"# {title}\n"]
    if failed:
        lines.append(f"> ⚠️ {unavailable_note(failed)}\n")
    if not stories:
        lines.append("Nothing new since the last Digest.\n")
        return "\n".join(lines)

    sources = len({i["source"] for s in stories for i in s["items"]})
    lines.append(f"_{len(stories)} Stories from {sources} Sources._\n")
    for tag, group in groups(stories, tag_order):
        lines.append(f"## {group_heading(tag)}\n")
        lines.extend(story_markdown(s) for s in group)
    return "\n".join(lines)
