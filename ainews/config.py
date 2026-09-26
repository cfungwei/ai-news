"""Loads config/ and holds the paths shared by fetch, curate and render."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
BUILD = ROOT / "build"
STATE = ROOT / "state"
DIGESTS = ROOT / "digests"

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


def today():
    return datetime.now(tz()).date().isoformat()
