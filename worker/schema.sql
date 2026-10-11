-- One row per (Story, browser). vote is 1 for 👍, -1 for 👎; removing a vote deletes the row.
CREATE TABLE IF NOT EXISTS votes (
  story TEXT NOT NULL,
  voter TEXT NOT NULL,
  vote INTEGER NOT NULL CHECK (vote IN (-1, 1)),
  at TEXT NOT NULL,
  PRIMARY KEY (story, voter)
);
