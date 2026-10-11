---
status: accepted
---

# Story votes live on a Cloudflare Worker, not in Telegram or the repo

Feedback is a 👍/👎 on each Story's page. The site is static GitHub Pages, so votes go to a small Cloudflare Worker backed by D1 (`worker/`), on Cloudflare's free plan. Each Run reads the totals from the Worker's `/export` and copies them into the `digests` branch state for Source health. We chose this because it is the only free option where voting is one tap on the page you're already reading, and it keeps working if the Digest gets more readers.

## Considered Options

- **Telegram reactions, one message per Story** (what we had): 517 Story messages over two weeks drew 12 reactions, and the message volume made the channel unpleasant to read.
- **A poll per Edition**: one tap per Story but only 10 options, and no 👎.
- **Google Form or a Telegram bot deep link from the page**: no new platform, but two taps and you leave the page.

## Consequences

- The project now depends on a second platform. If the Worker is down, the vote buttons hide themselves and Source health keeps the last totals it read; no Run fails because of it.
- Anyone who can open a page can vote, once per browser. That's fine for one reader; a public newsletter would need rate limiting.
