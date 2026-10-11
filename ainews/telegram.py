"""Telegram: one message per Edition, one line per Story, grouped by primary Tag.

Each line links to the Story's page, where the Summary, detail and 👍/👎 live. An Edition
too long for one message is split between Tag groups, never inside one.
"""

import os
import time
from html import escape as _escape

import httpx

from ainews import config
from ainews.render import group_heading, groups, unavailable_note

LIMIT = 4096  # Telegram's maximum message length.
ENV = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def escape(text):
    return _escape(text, quote=False)


def check_env():
    missing = [name for name in ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"{' and '.join(missing)} not set. Add them to the routine's cloud "
                           "environment variables (or .env when running locally).")


# Messages

def edition_messages(title, stories, failed, page_url, story_url, tag_order):
    """The Edition as one or more messages. story_url(story) gives each Story's page."""
    head = [f"🗞 <b>{escape(title)}</b> · "
            + (f"{len(stories)} Stories" if stories else "nothing new")]
    if failed:
        head.append(f"⚠️ {escape(unavailable_note(failed))}")
    footer = f'<a href="{_escape(page_url)}">Open the day\'s page →</a>'

    blocks = []
    for tag, group in groups(stories, tag_order):
        lines = [f"<b>{group_heading(tag)}</b>"]
        lines += [f'• <a href="{_escape(story_url(s))}">{escape(s["title"])}</a>' for s in group]
        blocks.append("\n".join(lines))

    messages, current = [], "\n".join(head)
    for block in blocks + [footer]:
        candidate = f"{current}\n\n{block}"
        if len(candidate) > LIMIT and current:
            messages.append(current)
            candidate = block
        current = candidate
    messages.append(current)
    return messages


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
        lines += ["", "Votes, last 30 days:"]
        lines.extend(f"• {escape(r['name'])}: {r['up']} 👍 / {r['down']} 👎" for r in rated[:8])
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


def send_all(messages):
    """Only the first message notifies; the rest of a long Edition arrives silently."""
    for n, text in enumerate(messages):
        if n:
            time.sleep(1)
        send(text, silent=n > 0)
