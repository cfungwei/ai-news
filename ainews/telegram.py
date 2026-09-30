"""Telegram: a header message, one message per Story, and 👍/👎 Feedback collection.

Each Story gets its own message so the owner can react to it. Reactions in a channel
are anonymous, so the bot reads their totals (`message_reaction_count` updates) at the
start of each Run. Telegram keeps updates for about 24 hours.
"""

import os
import time
from html import escape as _escape

import httpx

from ainews import config
from ainews.render import coverage_note, top, unavailable_note

LIMIT = 4096  # Telegram's maximum message length.
ENV = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
UP, DOWN = "👍", "👎"

EMOJI = {"models": "🧠", "research": "📄", "agents": "🤖", "tools": "🛠", "open-source": "🔓",
         "products": "📱", "industry": "💼", "policy": "⚖️", "hardware": "🔌", "robotics": "🦾",
         "other": "📰"}


def escape(text):
    return _escape(text, quote=False)


def check_env():
    missing = [name for name in ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"{' and '.join(missing)} not set. Add them to the routine's cloud "
                           "environment variables (or .env when running locally).")


# Messages

def header_message(title, stories, failed, url):
    lines = [f"<b>{escape(title)}</b>"]
    if failed:
        lines.append(f"⚠️ {escape(unavailable_note(failed))}")
    if not stories:
        lines.append("Nothing new since the last Digest.")
        return "\n\n".join(lines)
    preferred = sum(1 for s in stories if s["level"] == "preferred")
    lines.append(f"{len(stories)} Stories · {preferred} preferred")
    lines.append(f"React {UP} or {DOWN} to any Story below. It feeds the Source health report.")
    lines.append(f'<a href="{_escape(url)}">Open the full Digest →</a>')
    return "\n\n".join(lines)


def story_message(story, url):
    emoji = EMOJI.get(story["tags"][0], "📰")
    meta = f"<i>{escape(' · '.join(story['tags']))} · {coverage_note(story)}</i>"
    link = f'<a href="{_escape(url)}">Read more →</a>'
    title = f"{emoji} <b>{escape(story['title'])}</b>"
    if story["level"] == "muted":  # Muted Stories stay compact, as on the page.
        return f"{title}\n{meta} · {link}"
    return f"{title}\n{escape(story['summary'])}\n{meta} · {link}"


def failure_message(title, reason):
    return (f"❌ <b>{escape(title)} failed</b>\n\n"
            "Its news will be in the next Edition. Error:\n"
            f"<code>{escape(reason[:1500])}</code>")


def health_message(rows, url):
    lines = ["<b>Weekly Source health</b>", ""]
    flagged = [r for r in rows if r["flags"]]
    if flagged:
        lines.append("Flagged:")
        lines.extend(f"• {escape(r['name'])}: {escape(', '.join(r['flags']))}" for r in flagged)
    else:
        lines.append("No Sources flagged this week.")
    rated = sorted((r for r in rows if r["up"] or r["down"]), key=lambda r: r["down"] - r["up"])
    if rated:
        lines += ["", "Feedback, last 30 days:"]
        lines.extend(f"• {escape(r['name'])}: {r['up']} {UP} / {r['down']} {DOWN}"
                     for r in rated[:8])
    lines += ["", f'<a href="{_escape(url)}">Full report →</a>']
    return "\n".join(lines)


# Bot API

def api(method, payload):
    """Call the Bot API with retries. Honours 429 retry_after. Never leaks the token."""
    check_env()
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    attempts = config.settings()["fetch_attempts"]
    for attempt in range(attempts):
        wait = 2**attempt
        try:
            response = httpx.post(f"https://api.telegram.org/bot{token}/{method}",
                                  json=payload, timeout=30)
            body = response.json()
            if body.get("ok"):
                return body["result"]
            wait = body.get("parameters", {}).get("retry_after", wait)
            error = RuntimeError(f"Telegram {method} {response.status_code}: "
                                 f"{body.get('description', '')[:300]}")
        except (httpx.HTTPError, ValueError) as http_error:
            error = RuntimeError(f"Telegram {method} failed: {type(http_error).__name__}")
        if attempt == attempts - 1:
            raise error
        time.sleep(wait)


def send(text, silent=False):
    result = api("sendMessage", {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text,
                                 "parse_mode": "HTML", "disable_web_page_preview": True,
                                 "disable_notification": silent})
    return result["message_id"]


def chosen(stories, settings):
    """Which Stories get their own message: all, or the top N (topped up from neutral)."""
    if settings["telegram_story_messages"] == "all":
        return list(stories)
    return top(stories, settings["telegram_top_n"])


def send_digest(title, stories, failed, url, story_url):
    """Send the header, then one silent message per chosen Story. Returns {index: message id}."""
    settings = config.settings()
    send(header_message(title, stories, failed, url))
    sent = {}
    for story in chosen(stories, settings):
        time.sleep(settings["telegram_gap_seconds"])  # Channels allow about 20 messages a minute.
        index = stories.index(story)
        sent[index] = send(story_message(story, story_url(index)), silent=True)
    return sent


# Feedback

def reaction_counts(update, chat_id):
    """(message_id, 👍 count, 👎 count) from a message_reaction_count update, else None."""
    counts = update.get("message_reaction_count")
    if not counts or str(counts["chat"]["id"]) != str(chat_id):
        return None
    totals = {r["type"].get("emoji"): r["total_count"] for r in counts["reactions"]
              if r["type"].get("type") == "emoji"}
    return counts["message_id"], totals.get(UP, 0), totals.get(DOWN, 0)


def apply_updates(state, updates, chat_id):
    """Record the latest 👍/👎 totals for Story messages. Returns True if state changed."""
    for update in updates:
        state["telegram_offset"] = update["update_id"] + 1
        counts = reaction_counts(update, chat_id)
        entry = state.get("feedback", {}).get(str(counts[0])) if counts else None
        if entry:
            entry["up"], entry["down"] = counts[1], counts[2]
    return bool(updates)


def collect_feedback(state):
    updates = api("getUpdates", {"offset": state.get("telegram_offset", 0), "timeout": 0,
                                 "allowed_updates": ["message_reaction_count"]})
    return apply_updates(state, updates, os.environ["TELEGRAM_CHAT_ID"])
