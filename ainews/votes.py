"""Read 👍/👎 vote totals from the Cloudflare Worker (worker/, docs/adr/0002)."""

import httpx

from ainews import config


def fetch_all():
    """{story id: {"up": n, "down": n}}, or None if votes aren't set up or can't be read."""
    url = config.settings().get("votes_url")
    if not url:
        return None
    try:
        response = httpx.get(url.rstrip("/") + "/export", timeout=30)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as error:
        print(f"Could not read votes: {type(error).__name__}")  # Never fails the Run.
        return None
