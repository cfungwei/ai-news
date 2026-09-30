"""One Run publishes one Edition, in the steps the routine follows (see routine/PROMPT.md).

    python -m ainews.run prepare   exit 0: curate next.  exit 10: this Edition is done, stop.
    (curate: the routine agent writes build/stories.json)
    python -m ainews.run publish   render, push to the `digests` branch, post to Telegram.
    python -m ainews.run fail --reason "..."   tell Telegram this Edition failed.

The Edition is worked out from the clock (config.current_edition). `publish --local`
renders into build/site without pushing or posting.
"""

import argparse
import json
import sys

from ainews import config, fetch, health, pages, render, site, telegram

DONE = 10


class RunFailed(RuntimeError):
    pass


class Edition:
    def __init__(self, now=None):
        self.date, self.time = config.current_edition(now or config.now())
        self.key = config.digest_key(self.date, self.time)
        self.title = f"AI Digest · {self.date} · {self.time}"
        self.markdown = config.DIGESTS / f"{self.key}.md"
        self.data = config.SITE / "data" / f"{self.key}.json"
        self.url = config.page_url(self.date)

    def exists(self):
        return self.markdown.exists()

    def sent(self):
        return fetch.load_state().get("telegram_sent") == self.key

    def is_first_of_week(self):
        """The first Edition on the health summary day sends the weekly Source health."""
        weekday = config.now().strftime("%A")
        return (weekday == config.settings()["health_summary_day"]
                and self.time == sorted(config.editions())[0])


def load(path):
    return json.loads(path.read_text())


def check_fetch(fetched, source_count):
    """An Edition can still go out with some Sources down, but not with all of them."""
    if source_count and len(fetched["sources_failed"]) >= source_count:
        errors = "; ".join(f"{f['name']}: {f['error']}" for f in fetched["sources_failed"][:3])
        raise RunFailed(f"Every Source failed, so there is nothing to publish. First errors: {errors}")


def send(edition):
    """Post the Edition, remember which message is which Story for Feedback, mark it sent."""
    saved = load(edition.data)
    stories = saved["stories"]
    sent = telegram.send_digest(edition.title, stories, saved["failed"], edition.url,
                                lambda index: f"{edition.url}#{pages.anchor(edition.time, index)}")
    state = fetch.load_state()
    feedback = state.setdefault("feedback", {})
    for index, message_id in sent.items():
        story = stories[index]
        feedback[str(message_id)] = {
            "date": edition.date, "title": story["title"], "up": 0, "down": 0,
            "sources": sorted({i["source"] for i in story["items"]})}
    state["telegram_sent"] = edition.key
    fetch.save_state(state)
    if edition.is_first_of_week():
        telegram.send(telegram.health_message(health.write(state), health.url()))


def collect_feedback():
    """Read new 👍/👎 totals. A Telegram hiccup here never fails the Run."""
    state = fetch.load_state()
    try:
        changed = telegram.collect_feedback(state)
    except RuntimeError as error:
        print(f"Could not collect Feedback: {error}")
        return False
    fetch.save_state(state)
    if changed:
        health.write(state)
    return changed


def prepare(args):
    edition = Edition()
    telegram.check_env()
    site.checkout()
    feedback_changed = collect_feedback()
    if edition.exists():
        if edition.sent():
            if feedback_changed:
                site.publish(f"Feedback {edition.key}")
            print(f"{edition.title} is already published and sent. Nothing to do.")
            return DONE
        # An earlier Run pushed this Edition but could not post it.
        send(edition)
        site.publish(f"Digest {edition.key}")
        print(f"{edition.title} was published earlier; sent it to Telegram now.")
        return DONE

    fetch.main()
    check_fetch(load(config.ITEMS_FILE), len(config.sources()))
    if not load(config.ITEMS_FILE)["items"]:
        config.STORIES_FILE.write_text(json.dumps({"stories": []}))
        print("No new Items: skip curate and run publish.")
    return 0


def publish(args):
    edition = Edition()
    fetched = load(config.ITEMS_FILE)
    items = {i["id"]: i for i in fetched["items"]}
    stories = load(config.STORIES_FILE)["stories"] if items else []
    render.validate(items, stories)
    stories = render.order(stories, items, config.preferences())
    failed = fetched["sources_failed"]

    config.DIGESTS.mkdir(parents=True, exist_ok=True)
    edition.markdown.write_text(render.markdown(edition.title, stories, failed))
    edition.data.parent.mkdir(exist_ok=True)
    edition.data.write_text(json.dumps(
        {"date": edition.date, "edition": edition.time, "failed": failed, "stories": stories},
        indent=1, ensure_ascii=False))
    pages.write(edition.date)
    record(fetched)
    health.write(fetch.load_state())
    print(f"Rendered {len(stories)} Stories for {edition.title} into {config.SITE}")
    if args.local:
        return 0

    site.publish(f"Digest {edition.key}")
    send(edition)
    site.publish(f"Digest {edition.key}")
    print(f"Published {edition.url} and posted to Telegram.")
    return 0


def record(fetched):
    """Mark Items as seen and move each successful Source's window forward."""
    state = fetch.load_state()
    for item in fetched["items"]:
        state["seen"].setdefault(item["source"], []).append(item["id"])
    failed = {f["source"] for f in fetched["sources_failed"]}
    for source in config.sources():
        if source["id"] not in failed:
            state.setdefault("source_ok", {})[source["id"]] = fetched["fetched_at"]
    state["last_digest"] = fetched["fetched_at"]
    fetch.save_state(state)


def fail(args):
    """No backup Runs: the next Edition picks up this one's news, so just say so now."""
    edition = Edition()
    if edition.exists() and edition.sent():
        print(f"{edition.title} was already sent; not reporting a failure.")
        return 0
    telegram.send(telegram.failure_message(edition.title, args.reason))
    print("Sent the failure notice to Telegram.")
    return 0


def main():
    config.load_env()
    parser = argparse.ArgumentParser(prog="python -m ainews.run")
    steps = parser.add_subparsers(dest="step", required=True)
    steps.add_parser("prepare").set_defaults(func=prepare)
    publish_parser = steps.add_parser("publish")
    publish_parser.add_argument("--local", action="store_true",
                                help="render into build/site only; don't push or post")
    publish_parser.set_defaults(func=publish)
    fail_parser = steps.add_parser("fail")
    fail_parser.add_argument("--reason", required=True)
    fail_parser.set_defaults(func=fail)
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
