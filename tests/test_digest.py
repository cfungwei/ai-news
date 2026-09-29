from datetime import datetime, timedelta, timezone

import pytest

from ainews import fetch, render, telegram
from ainews.run import RunFailed, check_fetch, is_last_run

PREFERENCES = {"models": "preferred", "agents": "preferred", "products": "neutral",
               "policy": "neutral", "industry": "muted", "other": "muted"}


def item(item_id, source, published="2026-09-26T01:00:00+00:00"):
    return {"id": item_id, "source": source, "source_name": source.title(), "title": item_id,
            "url": f"https://example.com/{item_id}", "published": published, "excerpt": ""}


def story(title, tags, item_ids):
    return {"title": title, "tags": tags, "tagged_by": "agent", "summary": f"{title} summary.",
            "more": f"{title} more.", "item_ids": item_ids}


ITEMS = {i["id"]: i for i in [
    item("a1", "verge"), item("a2", "techcrunch"), item("a3", "hn"),
    item("b1", "verge", "2026-09-26T05:00:00+00:00"),
    item("c1", "techcrunch"), item("c2", "hn"),
    item("d1", "verge"), item("e1", "hn"), item("f1", "verge"),
]}


def ordered(stories):
    return render.order(stories, ITEMS, PREFERENCES)


class TestValidate:
    def test_accepts_every_item_in_exactly_one_story(self):
        render.validate({"a1": {}, "a2": {}}, [story("A", ["models"], ["a1", "a2"])])

    def test_lists_every_problem(self):
        stories = [story("A", ["crypto"], ["a1"]), story("B", ["models"], ["a1", "zz"])]
        with pytest.raises(render.InvalidStories) as error:
            render.validate({"a1": {}, "a2": {}}, stories)
        message = str(error.value)
        assert "unknown Tag 'crypto'" in message
        assert "Item a1 is in Stories 1 and 2" in message
        assert "Item a2 is in no Story" in message
        assert "unknown Item zz" in message

    def test_rejects_missing_fields(self):
        broken = story("A", ["models"], ["a1"]) | {"summary": ""}
        with pytest.raises(render.InvalidStories, match="has no summary"):
            render.validate({"a1": {}}, [broken])


class TestOrder:
    def test_story_takes_its_highest_preference_level(self):
        [s] = ordered([story("A", ["industry", "agents"], ["a1"])])
        assert s["level"] == "preferred"

    def test_unknown_preference_counts_as_neutral(self):
        [s] = ordered([story("A", ["hardware"], ["a1"])])
        assert s["level"] == "neutral"

    def test_coverage_counts_distinct_sources(self):
        [s] = ordered([story("A", ["models"], ["a1", "a2", "a3", "d1"])])
        assert s["coverage"] == 3

    def test_level_then_coverage_then_newest(self):
        stories = ordered([
            story("muted, big", ["industry"], ["a1", "a2", "a3"]),
            story("neutral", ["products"], ["f1"]),
            story("preferred, coverage 1, older", ["models"], ["d1"]),
            story("preferred, coverage 1, newer", ["models"], ["b1"]),
            story("preferred, coverage 2", ["agents"], ["c1", "c2"]),
        ])
        assert [s["title"] for s in stories] == [
            "preferred, coverage 2", "preferred, coverage 1, newer",
            "preferred, coverage 1, older", "neutral", "muted, big"]


class TestTop:
    def test_tops_up_from_neutral_and_never_uses_muted(self):
        stories = ordered([
            story("P", ["models"], ["a1"]),
            story("N1", ["products"], ["c1", "c2"]),
            story("N2", ["policy"], ["d1"]),
            story("M", ["industry"], ["e1"]),
        ])
        assert [s["title"] for s in render.top(stories, 5)] == ["P", "N1", "N2"]


class TestMarkdown:
    def test_quiet_day_is_one_line_with_unavailable_note(self):
        text = render.markdown("2026-09-27", [], [{"source": "vb", "name": "VentureBeat AI"}])
        assert "Nothing new since the last Digest." in text
        assert "Unavailable today: VentureBeat AI" in text

    def test_muted_stories_are_compact(self):
        text = render.markdown("2026-09-27", ordered([story("M", ["industry"], ["e1"])]), [])
        assert "## Muted" in text
        assert "<summary><b>M</b>" in text
        assert "### M" not in text


class TestTelegram:
    def test_fits_the_limit_by_dropping_summaries(self):
        long = [story(f"S{n}", ["models"], [f"a{n}"]) | {"summary": "x" * 1500}
                for n in range(1, 4)]
        for s in long:
            s["items"] = []
        text = telegram.digest_message("2026-09-27", long, long, [], "https://x/")
        assert len(text) <= telegram.LIMIT
        assert "1. <b>S1</b>" in text and "3. <b>S3</b>" in text
        assert "Read all 3 Stories" in text

    def test_escapes_html(self):
        [s] = ordered([story("A <b> & B", ["models"], ["a1"])])
        text = telegram.digest_message("2026-09-27", [s], [s], [], "https://x/")
        assert "A &lt;b&gt; &amp; B" in text

    def test_quiet_day(self):
        text = telegram.digest_message("2026-09-27", [], [], [], "https://x/")
        assert "Nothing new since the last Digest." in text


class TestLastRun:
    SETTINGS = {"schedule": "07:00", "backup_runs": 2}
    TZ = timezone(timedelta(hours=8))

    @pytest.mark.parametrize("hhmm, expected", [
        ("07:03", False), ("08:05", False), ("08:35", True), ("09:04", True), ("14:00", True)])
    def test_only_the_last_scheduled_run_reports_failure(self, hhmm, expected):
        hours, minutes = map(int, hhmm.split(":"))
        now = datetime(2026, 9, 27, hours, minutes, tzinfo=self.TZ)
        assert is_last_run(now, self.SETTINGS) is expected

    def test_no_backups_means_the_first_run_is_last(self):
        now = datetime(2026, 9, 27, 7, 2, tzinfo=self.TZ)
        assert is_last_run(now, {"schedule": "07:00", "backup_runs": 0})


class TestRunChecks:
    FAILED = {"source": "x", "name": "X", "error": "403 Forbidden"}

    def test_all_sources_failing_fails_the_run(self):
        with pytest.raises(RunFailed, match="Every Source failed"):
            check_fetch({"sources_failed": [self.FAILED] * 3, "items": []}, 3)

    def test_some_sources_failing_still_publishes(self):
        check_fetch({"sources_failed": [self.FAILED], "items": []}, 3)

    def test_missing_telegram_env_names_the_variables(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
        with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN not set"):
            telegram.check_env()


class TestStoryLimits:
    def test_rejects_long_titles_and_summaries(self):
        long = story("T" * 91, ["models"], ["a1"]) | {"summary": "word " * 46}
        with pytest.raises(render.InvalidStories) as error:
            render.validate({"a1": {}}, [long])
        assert "title is over 90 characters" in str(error.value)
        assert "summary is over 45 words" in str(error.value)

    def test_accepts_limits_exactly(self):
        ok = story("T" * 90, ["models"], ["a1"]) | {"summary": "word " * 45}
        render.validate({"a1": {}}, [ok])


class FakePage:
    def __init__(self, html):
        self.text = html

    def raise_for_status(self):
        pass


class FakeClient:
    def __init__(self, html):
        self.html = html

    def get(self, url, params=None):
        return FakePage(self.html)


class TestPageSource:
    SOURCE = {"id": "lab", "name": "Lab", "url": "https://lab.example/news",
              "link_pattern": 'href="(/news/[a-z-]+)"',
              "base_url": "https://lab.example"}
    WIDER = SOURCE | {"link_pattern": 'href="(/news/[a-z-]+|/model-[a-z0-9-]+)"'}
    PAGE = '<a href="/news/old-post"></a><a href="/model-one"></a>'

    def fetch(self, source, html, state):
        return list(fetch.fetch_page(FakeClient(html), source, None, state))

    def test_first_fetch_baselines_without_emitting(self):
        state = {"seen": {}, "baselined": []}
        assert self.fetch(self.SOURCE, self.PAGE, state) == []
        assert state["seen"]["lab"] == ["lab:https://lab.example/news/old-post"]

    def test_new_links_after_baseline_are_items(self):
        state = {"seen": {}, "baselined": []}
        self.fetch(self.SOURCE, self.PAGE, state)
        found = self.fetch(self.SOURCE, self.PAGE + '<a href="/news/new-post"></a>', state)
        assert "lab:https://lab.example/news/new-post" in [i["id"] for i in found]

    def test_changing_the_pattern_rebaselines_instead_of_flooding(self):
        state = {"seen": {}, "baselined": ["lab"]}  # Legacy entry, from before keys had patterns.
        state["seen"]["lab"] = ["lab:https://lab.example/news/old-post"]
        assert self.fetch(self.WIDER, self.PAGE, state) == []
        assert "lab:https://lab.example/model-one" in state["seen"]["lab"]
        assert state["baselined"] == [fetch.baseline_key(self.WIDER)]
        assert len(state["seen"]["lab"]) == 2  # No duplicates.
