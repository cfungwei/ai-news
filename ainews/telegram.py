"""The Telegram message: the top Stories, with a link to the full Digest page."""

import os
import time
from html import escape as _escape

import httpx

from ainews import config
from ainews.render import unavailable_note

LIMIT = 4096  # Telegram's maximum message length.


def escape(text):
    return _escape(text, quote=False)


def digest_message(date, stories, top_stories, failed, url):
    head = [f"<b>AI Digest · {date}</b>"]
    if failed:
        head.append(f"⚠️ {escape(unavailable_note(failed))}")
    if not stories:
        head.append("Nothing new since the last Digest.")
        return "\n\n".join(head)

    footer = f'<a href="{_escape(url)}">Read all {len(stories)} Stories →</a>'
    # Drop Summaries from the bottom up until the message fits.
    for with_summary in range(len(top_stories), -1, -1):
        lines = []
        for n, story in enumerate(top_stories, 1):
            line = f"{n}. <b>{escape(story['title'])}</b>"
            if n <= with_summary:
                line += f"\n{escape(story['summary'])}"
            lines.append(line)
        body = "<b>Top stories</b>\n\n" + "\n\n".join(lines) if lines else ""
        text = "\n\n".join([*head, body, footer]) if body else "\n\n".join([*head, footer])
        if len(text) <= LIMIT:
            return text
    return text[:LIMIT]


def failure_message(date, runs, reason):
    return (f"❌ <b>AI Digest · {date} failed</b>\n\n"
            f"All {runs} Runs failed. Last error:\n<code>{escape(reason[:1500])}</code>")


def send(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    attempts = config.settings()["fetch_attempts"]
    for attempt in range(attempts):
        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=30)
            if response.status_code == 200:
                return
            error = RuntimeError(f"Telegram {response.status_code}: {response.text[:300]}")
        except httpx.HTTPError as http_error:
            error = RuntimeError(f"Telegram request failed: {type(http_error).__name__}")
        if attempt == attempts - 1:
            raise error  # Never include the token in the message.
        time.sleep(2**attempt)
