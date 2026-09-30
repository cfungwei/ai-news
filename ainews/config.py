"""Loads config/ and holds the paths shared by fetch, curate, render and publish."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
BUILD = ROOT / "build"

# A checkout of the `digests` branch. Runs write only here; see docs/adr/0001.
SITE = BUILD / "site"
STATE = SITE / "state"
DIGESTS = SITE / "digests"

ITEMS_FILE = BUILD / "items.json"
STORIES_FILE = BUILD / "stories.json"
SEEN_FILE = STATE / "seen.json"

LEVELS = ("preferred", "neutral", "muted")


def _load(name):
    return yaml.safe_load((CONFIG / name).read_text())


def settings():
    return _load("settings.yaml")


def sources():
    return [s for s in _load("sources.yaml")["sources"] if s.get("enabled", True)]


def tags():
    return _load("tags.yaml")["tags"]


def preferences():
    return _load("preferences.yaml")["preferences"]


def tz():
    sign, hhmm = settings()["timezone"][0], settings()["timezone"][1:]
    hours, minutes = (int(x) for x in hhmm.split(":"))
    offset = timedelta(hours=hours, minutes=minutes)
    return timezone(offset if sign == "+" else -offset)


def now():
    return datetime.now(tz())


def today():
    return now().date().isoformat()


def editions():
    return settings()["editions"]


def current_edition(now, times=None):
    """(date, "HH:MM") of the Edition a Run at `now` belongs to.

    That's the latest Edition time at or before now, with 15 minutes of slack for a Run
    that starts early. Before the day's first Edition, it's yesterday's last one.
    """
    times = sorted(times or editions())
    slack = timedelta(minutes=15)
    for time in reversed(times):
        hours, minutes = (int(x) for x in time.split(":"))
        if now >= now.replace(hour=hours, minute=minutes, second=0, microsecond=0) - slack:
            return now.date().isoformat(), time
    return (now.date() - timedelta(days=1)).isoformat(), times[-1]


def digest_key(date, edition):
    """Names one Edition's files, e.g. 2026-09-30-1130."""
    return f"{date}-{edition.replace(':', '')}"


def page_url(date):
    return settings()["site_url"].rstrip("/") + "/" + date.replace("-", "/") + "/"


def load_env():
    """Read KEY=VALUE lines from .env for local Runs. The routine sets real env vars instead."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
