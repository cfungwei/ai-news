# The daily Run

You are running one Run of the ai-news Digest. Read `CONTEXT.md` first and use its terms exactly.

Do these steps in order, from the repo root. Do not edit, commit or push anything on `main`. The scripts write only to the `digests` branch, checked out at `build/site`.

1. `pip install -q -r requirements.txt`
2. `python -m ainews.run prepare`
   - Exit code **10**: today's Digest is already done. Stop here; the Run succeeded.
   - Exit code **0**: continue. If it printed "skip curate", go straight to step 4.
3. **Curate**: follow the instructions below to turn `build/items.json` into `build/stories.json`.
4. `python -m ainews.run publish`
   - If it fails with `InvalidStories`, fix `build/stories.json` using the problems it lists, then run `publish` again. Do this at most twice.
5. If any step still fails, run `python -m ainews.run fail --reason "<step>: <the error, one line>"` and stop. This tells Telegram only if no backup Run is left today.

Never print or echo the environment variables `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID`.

# Curate: turn Items into Stories

**Input:** `build/items.json`, the new Items from `fetch`.
**Output:** `build/stories.json`, in the schema below. Write nothing else, and do not edit any other file.

## 1. Group Items into Stories

A Story is **one real-world event or release**. Put Items in the same Story only when they report the *same* event: the same model launch, the same paper, the same funding round, the same product announcement.

- A lab's own announcement and news coverage of it → one Story.
- A Hugging Face trending model and the lab post that released it → one Story.
- A Hacker News submission of an article that another Source also published → one Story.
- Two different releases from the same company on the same day → two Stories.
- Two articles on the same broad theme (e.g. "AI and jobs") but about different events → two Stories.

When unsure, keep them separate. A wrongly merged Story hides news; a missed merge only costs a line.

Every Item must belong to **exactly one** Story. Most Stories will have one Item.

## 2. Tag each Story

Assign 1–3 Tags from `config/tags.yaml`, most relevant first. Use only Tags from that file, and use `other` only if nothing else fits. Choose Tags from what the Story *is about*, not from which Source it came from. A trending model is `models`, and also `open-source` if its weights are open.

Set `"tagged_by": "agent"`. (Jev will later tag Stories instead, and the Digest marks which tagger was used.)

## 3. Write the Story text

- **title**: a plain, specific headline for the event, in your own words, 90 characters or fewer. Name the actor and the thing: "Mistral releases Magistral 2 with open weights", not "A new model".
- **summary**: 1–2 sentences, 45 words or fewer. Say what happened and why it matters. Write it in your own words; never copy a Source's text.
- **more**: one paragraph of 4–6 sentences that adds detail beyond the summary: specifics, numbers, context, and what's still unknown. Use only facts from the Items' excerpts and titles. If the excerpts are too thin for 4 sentences, write fewer rather than inventing details.

No hype words ("groundbreaking", "revolutionary", "game-changer"). No speculation presented as fact.

## Output schema

```json
{
  "stories": [
    {
      "title": "string",
      "tags": ["models", "open-source"],
      "tagged_by": "agent",
      "summary": "string",
      "more": "string",
      "item_ids": ["hf-trending:org/model", "hn:12345"]
    }
  ]
}
```

Do not add fields for coverage, preference or order. `render` computes those from `item_ids` and `config/preferences.yaml`.

## Check before finishing

- Every `id` in `build/items.json` appears in exactly one Story's `item_ids`, and no other ids appear.
- Every tag is a key in `config/tags.yaml`.
- The file is valid JSON.

`render` rejects the file if any check fails.
