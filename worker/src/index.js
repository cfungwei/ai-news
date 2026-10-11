// Feedback votes for ai-news Story pages (see docs/adr/0002-votes-on-a-cloudflare-worker.md).
//
//   GET  /votes?story=<id>&voter=<id>   counts for one Story, plus this browser's vote
//   POST /vote  {story, voter, vote}    vote: 1 (👍), -1 (👎) or 0 (remove); returns counts
//   GET  /export                        {story: {up, down}} for every Story, read by each Run

const STORY = /^\d{4}-\d{2}-\d{2}-\d{4}-\d{1,3}$/; // e.g. 2026-10-11-1130-3
const VOTER = /^[A-Za-z0-9-]{8,64}$/;               // random id kept in the browser

export default {
  async fetch(request, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN,
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Vary": "Origin",
    };
    const json = (body, status = 200) =>
      new Response(JSON.stringify(body), {
        status, headers: { ...cors, "Content-Type": "application/json" } });
    const { pathname, searchParams } = new URL(request.url);

    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    if (request.method === "GET" && pathname === "/votes") {
      const story = searchParams.get("story") || "";
      const voter = searchParams.get("voter") || "";
      if (!STORY.test(story)) return json({ error: "bad story" }, 400);
      return json(await counts(env, story, VOTER.test(voter) ? voter : null));
    }

    if (request.method === "POST" && pathname === "/vote") {
      const body = await request.json().catch(() => ({}));
      const { story, voter, vote } = body;
      if (!STORY.test(story || "") || !VOTER.test(voter || "") || ![1, -1, 0].includes(vote)) {
        return json({ error: "bad vote" }, 400);
      }
      if (vote === 0) {
        await env.DB.prepare("DELETE FROM votes WHERE story = ? AND voter = ?")
          .bind(story, voter).run();
      } else {
        await env.DB.prepare(
          `INSERT INTO votes (story, voter, vote, at) VALUES (?, ?, ?, ?)
           ON CONFLICT (story, voter) DO UPDATE SET vote = excluded.vote, at = excluded.at`)
          .bind(story, voter, vote, new Date().toISOString()).run();
      }
      return json(await counts(env, story, voter));
    }

    if (request.method === "GET" && pathname === "/export") {
      const { results } = await env.DB.prepare(
        `SELECT story, SUM(vote = 1) AS up, SUM(vote = -1) AS down FROM votes GROUP BY story`).all();
      return json(Object.fromEntries(results.map((r) => [r.story, { up: r.up, down: r.down }])));
    }

    return json({ error: "not found" }, 404);
  },
};

async function counts(env, story, voter) {
  const totals = await env.DB.prepare(
    "SELECT SUM(vote = 1) AS up, SUM(vote = -1) AS down FROM votes WHERE story = ?")
    .bind(story).first();
  const mine = voter
    ? await env.DB.prepare("SELECT vote FROM votes WHERE story = ? AND voter = ?")
        .bind(story, voter).first()
    : null;
  return { up: totals.up || 0, down: totals.down || 0, mine: mine ? mine.vote : 0 };
}
