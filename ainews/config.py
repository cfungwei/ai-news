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
