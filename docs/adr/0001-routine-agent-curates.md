---
status: accepted
---

# The routine agent curates; Runs write only to the `digests` branch

Each Run is a Claude Code cloud routine on the owner's Pro subscription, not a GitHub Actions job calling an LLM API. The routine agent does the curate step itself: it groups Items into Stories, assigns Tags (until Jev replaces it), and writes Summaries, following `routine/PROMPT.md`. There are no LLM API calls in the code. We chose this for $0 running cost and fast iteration: changing how curation works means editing a prompt, not code. The price is output that is not fully deterministic or unit-testable.

To contain an autonomous agent, Runs push only to the `digests` branch, which holds Digests and the record of seen Items and is served by GitHub Pages. `main` holds the code, Sources, Tags, Preferences and the prompt, and only the owner changes it.

## Considered Options

- **GitHub Actions + Claude Haiku API** (~$4–5/month): deterministic and testable. Rejected for now on cost and iteration speed. The fetch → curate → publish split keeps it a drop-in replacement for the curate step if routine output proves too inconsistent.
- **Claude Desktop scheduled tasks**: rejected because they require the Mac to be awake with the app open at 07:00.

## Consequences

- Routines are a research preview with no published reliability guarantee. The Digest is published as four Editions a day (4 of Pro's 5 routine runs), so a failed Run is covered by the next Edition rather than by backup Runs, and the Telegram failure notice goes out straight away. (Superseded the original 07:00 Digest with 08:00 and 09:00 backup Runs, 2026-09-30.)
- The routine needs a custom cloud environment with network access to every Source, Telegram, and later Jev.
