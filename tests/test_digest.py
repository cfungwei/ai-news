from datetime import datetime, timedelta, timezone

import pytest

from ainews import config, fetch, health, pages, render, telegram
from ainews.run import RunFailed, check_fetch

TAG_ORDER = ["models", "research", "agents", "tools", "open-source", "products", "industry",
             "policy", "hardware", "robotics", "other"]


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
    return render.order(stories, ITEMS, TAG_ORDER)


def saved_edition(day, stories, failed=(), edition="06:30"):
    return {"date": day, "edition": edition, "failed": [{"source": f, "name": f} for f in failed],
            "stories": ordered(stories)}


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

    def test_rejects_long_titles_and_summaries(self):
        long = story("T" * 91, ["models"], ["a1"]) | {"summary": "word " * 46}
        with pytest.raises(render.InvalidStories) as error:
            render.validate({"a1": {}}, [long])
        assert "title is over 90 characters" in str(error.value)
        assert "summary is over 45 words" in str(error.value)

    def test_accepts_limits_exactly(self):
        ok = story("T" * 90, ["models"], ["a1"]) | {"summary": "word " * 45}
        render.validate({"a1": {}}, [ok])


class TestOrder:
    def test_coverage_counts_distinct_sources(self):
        [s] = ordered([story("A", ["models"], ["a1", "a2", "a3", "d1"])])
        assert s["coverage"] == 3

    def test_groups_by_primary_tag_biggest_first_other_last(self):
        stories = ordered([
            story("other 1", ["other"], ["a1"]), story("other 2", ["other"], ["a2"]),
            story("other 3", ["other"], ["a3"]),
            story("policy", ["policy"], ["b1"]),
            story("agents 1", ["agents", "models"], ["c1"]), story("agents 2", ["agents"], ["c2"]),
            story("models", ["models"], ["d1"]),
        ])
        assert [tag for tag, _ in render.groups(stories, TAG_ORDER)] == [
            "agents", "models", "policy", "other"]  # Ties between models and policy: Tag order.

    def test_inside_a_group_coverage_then_newest(self):
        stories = ordered([
            story("coverage 1, older", ["models"], ["d1"]),
            story("coverage 1, newer", ["models"], ["b1"]),
            story("coverage 2", ["models"], ["c1", "c2"]),
        ])
        assert [s["title"] for s in stories] == [
            "coverage 2", "coverage 1, newer", "coverage 1, older"]


class TestMarkdown:
    def test_quiet_edition_with_unavailable_note(self):
        text = render.markdown("AI Digest", [], [{"source": "vb", "name": "VentureBeat AI"}],
                               TAG_ORDER)
        assert "Nothing new since the last Digest." in text
        assert "Unavailable this Edition: VentureBeat AI" in text

    def test_grouped_under_tag_headings(self):
        text = render.markdown("AI Digest", ordered([story("M", ["industry"], ["e1"])]), [],
                               TAG_ORDER)
        assert "## 💼 Industry" in text and "### M" in text


class TestTelegram:
    def messages(self, stories, failed=()):
        return telegram.edition_messages(
            "AI Digest · 2026-10-11 · 11:30", stories, list(failed), "https://x/2026/10/11/",
            lambda s: f"https://x/{s['title']}/", TAG_ORDER)

    def test_one_line_per_story_grouped_by_tag(self):
        [text] = self.messages(ordered([story("Sonnet 5.5 ships", ["models"], ["a1"]),
                                        story("Agents & <tools>", ["agents"], ["c1"])]))
        assert text.startswith("🗞 <b>AI Digest · 2026-10-11 · 11:30</b> · 2 Stories")
        assert "<b>🧠 Models</b>\n• <a href=\"https://x/Sonnet 5.5 ships/\">Sonnet 5.5 ships</a>" in text
        assert "Agents &amp; &lt;tools&gt;" in text
        assert "summary" not in text  # Summaries live on the Story page.
        assert text.endswith('<a href="https://x/2026/10/11/">Open the day\'s page →</a>')

    def test_long_editions_split_between_groups(self):
        tags = ["models", "agents", "tools", "policy", "industry"]
        items = {f"{tag}{n}": item(f"{tag}{n}", "verge") for tag in tags for n in range(12)}
        stories = render.order([story(f"{tag} {n} " + "x" * 70, [tag], [f"{tag}{n}"])
                                for tag in tags for n in range(12)], items, TAG_ORDER)
        messages = self.messages(stories)
        assert len(messages) > 1
        assert all(len(m) <= telegram.LIMIT for m in messages)
        for m in messages:  # Every message starts a group, never mid-group.
            assert m.startswith(("🗞", "<b>"))

    def test_quiet_edition(self):
        [text] = self.messages([])
        assert "nothing new" in text

    def test_failure_message_says_next_edition_catches_up(self):
        text = telegram.failure_message("AI Digest · 2026-09-30 · 11:30", "boom")
        assert "11:30 failed" in text and "next Edition" in text


class TestPages:
    def test_story_id_and_path(self):
        saved = {"date": "2026-10-11", "edition": "11:30"}
        assert pages.story_id(saved, 2) == "2026-10-11-1130-3"
        assert pages.story_path("2026-10-11-1130-3") == "2026/10/11/1130-3/"

    def test_day_page_lists_editions_newest_first_linking_story_pages(self):
        morning = saved_edition("2026-10-11", [story("A", ["models"], ["a1"])])
        noon = saved_edition("2026-10-11", [story("B", ["agents"], ["b1"])], edition="11:30")
        html = pages.day_page("2026-10-11", [noon, morning], TAG_ORDER)
        assert html.index("11:30 Edition") < html.index("06:30 Edition")
        assert '<a href="1130-1/">B</a>' in html and '<a href="0630-1/">A</a>' in html

    def test_story_page_has_votes_then_the_story(self):
        saved = saved_edition("2026-10-11", [story("A <b>", ["models"], ["a1", "a2"])],
                              edition="11:30")
        html = pages.story_page(saved["stories"][0], "2026-10-11-1130-1", saved)
        assert html.index('class="votes"') < html.index("<h1>A &lt;b&gt;</h1>")
        assert 'story = "2026-10-11-1130-1"' in html
        assert "A &lt;b&gt; summary." in html and "Verge: a1" in html


class TestHealth:
    SOURCES = [{"id": "verge", "name": "Verge"}, {"id": "hn", "name": "HN"},
               {"id": "techcrunch", "name": "TechCrunch"}]

    def report(self, saved, votes=None, today="2026-10-08"):
        return {r["id"]: r for r in health.rows(saved, votes or {}, self.SOURCES, today)}

    def test_counts_items(self):
        saved = {"2026-10-08-0630": saved_edition("2026-10-08", [
            story("P", ["models"], ["a1", "a2"]), story("M", ["industry"], ["f1"])])}
        rows = self.report(saved)
        assert rows["verge"]["items7"] == 2
        assert rows["techcrunch"]["items30"] == 1

    def test_votes_count_for_every_source_behind_a_story(self):
        saved = {"2026-10-08-0630": saved_edition("2026-10-08", [
            story("P", ["models"], ["a1", "a2"])])}
        rows = self.report(saved, {"2026-10-08-0630-1": {"up": 2, "down": 1}})
        assert (rows["verge"]["up"], rows["verge"]["down"]) == (2, 1)
        assert (rows["techcrunch"]["up"], rows["techcrunch"]["down"]) == (2, 1)
        assert rows["hn"]["up"] == 0

    def test_silent_flag_needs_a_week_of_history(self):
        recent = {"a": saved_edition("2026-10-06", [story("P", ["models"], ["a1"])])}
        assert self.report(recent)["hn"]["flags"] == []
        older = recent | {"b": saved_edition("2026-10-01", [])}
        assert self.report(older)["hn"]["flags"] == ["no Items in 7 days"]

    def test_failing_days_and_disliked_flags(self):
        saved = {f"d{d}": saved_edition(f"2026-10-0{d}", [story("P", ["models"], ["a3"])],
                                        failed=["verge"]) for d in (6, 7, 8)}
        votes = {"2026-10-07-0630-1": {"up": 1, "down": 3}}
        rows = self.report(saved, votes)
        assert "failed on 3 of the last 7 days" in rows["verge"]["flags"]
        assert rows["hn"]["flags"] == ["more 👎 than 👍"]
        # A second failed Edition on the same day doesn't count as another day.
        saved["x"] = saved_edition("2026-10-08", [], failed=["hn"], edition="11:30")
        saved["y"] = saved_edition("2026-10-08", [], failed=["hn"], edition="16:30")
        assert self.report(saved, votes)["hn"]["failed7"] == 1


class TestEditions:
    TZ = timezone(timedelta(hours=8))
    TIMES = ["06:30", "11:30", "16:30", "21:30"]

    @pytest.mark.parametrize("hhmm, expected", [
        ("06:34", ("2026-09-30", "06:30")),   # A routine that starts a few minutes late.
        ("06:20", ("2026-09-30", "06:30")),   # Or a few minutes early.
        ("11:29", ("2026-09-30", "11:30")),
        ("14:00", ("2026-09-30", "11:30")),   # A manual Run now between Editions.
        ("23:59", ("2026-09-30", "21:30")),
        ("03:00", ("2026-09-29", "21:30")),   # After midnight: yesterday's last Edition.
    ])
    def test_run_time_picks_its_edition(self, hhmm, expected):
        hours, minutes = map(int, hhmm.split(":"))
        now = datetime(2026, 9, 30, hours, minutes, tzinfo=self.TZ)
        assert config.current_edition(now, self.TIMES) == expected

    def test_digest_key(self):
        assert config.digest_key("2026-09-30", "11:30") == "2026-09-30-1130"


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
              "link_pattern": 'href="(/news/[a-z-]+)"', "base_url": "https://lab.example"}
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
        state = {"seen": {"lab": ["lab:https://lab.example/news/old-post"]}, "baselined": ["lab"]}
        assert self.fetch(self.WIDER, self.PAGE, state) == []
        assert "lab:https://lab.example/model-one" in state["seen"]["lab"]
        assert state["baselined"] == [fetch.baseline_key(self.WIDER)]
        assert len(state["seen"]["lab"]) == 2  # No duplicates.
