"""One Run, in the steps the routine follows (see routine/PROMPT.md).

    python -m ainews.run prepare   exit 0: curate next.  exit 10: today is done, stop.
    (curate: the routine agent writes build/stories.json)
    python -m ainews.run publish   render, push to the `digests` branch, post to Telegram.
    python -m ainews.run fail --reason "..."   on the day's last Run, tell Telegram.

`publish --local` renders into build/site without pushing or posting.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

from ainews import config, fetch, pages, render, site, telegram

DONE = 10


def load(path):
    return json.loads(path.read_text())


def digest_exists(date):
    return (config.DIGESTS / f"{date}.md").exists()


def data_file(date):
    return config.SITE / "data" / f"{date}.json"


def send_digest(date):
    saved = load(data_file(date))
    stories = saved["stories"]
    top = render.top(stories, config.settings()["telegram_top_n"])
    telegram.send(telegram.digest_message(date, stories, top, saved["failed"],
                                          config.page_url(date)))


def mark_sent(date):
    state = fetch.load_state()
    state["telegram_sent"] = date
    fetch.save_state(state)


def prepare(args):
    date = config.today()
    site.checkout()
    if digest_exists(date):
        if fetch.load_state().get("telegram_sent") == date:
            print(f"Digest {date} is already published and sent. Nothing to do.")
            return DONE
        # An earlier Run pushed the Digest but could not post it.
        send_digest(date)
        mark_sent(date)
        site.publish(date)
        print(f"Digest {date} was published earlier; sent it to Telegram now.")
        return DONE

    fetch.main()
    if not load(config.ITEMS_FILE)["items"]:
        config.STORIES_FILE.write_text(json.dumps({"stories": []}))
        print("No new Items: skip curate and run publish.")
    return 0


def publish(args):
    date = config.today()
    fetched = load(config.ITEMS_FILE)
    items = {i["id"]: i for i in fetched["items"]}
    stories = load(config.STORIES_FILE)["stories"] if items else []
    render.validate(items, stories)
    stories = render.order(stories, items, config.preferences())
    failed = fetched["sources_failed"]

    config.DIGESTS.mkdir(parents=True, exist_ok=True)
    (config.DIGESTS / f"{date}.md").write_text(render.markdown(date, stories, failed))
    data_file(date).parent.mkdir(exist_ok=True)
    data_file(date).write_text(json.dumps({"date": date, "failed": failed, "stories": stories},
                                          indent=1, ensure_ascii=False))
    pages.write(date, stories, failed)
    record(fetched)
    print(f"Rendered {len(stories)} Stories for {date} into {config.SITE}")
    if args.local:
        return 0

    site.publish(date)
    send_digest(date)
    mark_sent(date)
    site.publish(date)
    print(f"Published {config.page_url(date)} and posted to Telegram.")
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


def is_last_run(now, settings):
    hours, minutes = (int(x) for x in settings["schedule"].split(":"))
    first = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    last = first + timedelta(hours=settings["backup_runs"])
    return now >= last - timedelta(minutes=30)  # Routines start a few minutes late.


def fail(args):
    date = config.today()
    settings = config.settings()
    if digest_exists(date) and fetch.load_state().get("telegram_sent") == date:
        print("Today's Digest was already sent; not reporting a failure.")
        return 0
    if not is_last_run(config.now(), settings):
        print("A backup Run will retry later; not reporting yet.")
        return 0
    telegram.send(telegram.failure_message(date, settings["backup_runs"] + 1, args.reason))
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
