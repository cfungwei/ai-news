# ai-news

A digest of anything new from sources the owner chooses, published four times a day. Today it has one reader, but it may grow into a newsletter shared on Telegram or a webpage.

## Language

### Collecting

**Source**:
A place the owner has chosen to watch for new things (e.g. a Hugging Face listing, an AI news site).
_Avoid_: Feed, channel, provider

**Item**:
One new thing published by one Source.
_Avoid_: Post, article, entry

**Story**:
One real-world event or release, made up of one or more Items that cover it. Overlapping Items collapse into a single Story. Each Story belongs to exactly one Digest; later coverage becomes a new Story.
_Avoid_: Cluster, topic, merged item

**Coverage**:
The number of distinct Sources with an Item in a Story. Used as the measure of a Story's importance.
_Avoid_: Popularity, score, mentions

### Grouping

**Tag**:
A category from a fixed list that describes what a Story is about. A Story can have several Tags; its first is the **primary Tag**, which the Digest groups it under. One that fits none gets `other`.
_Avoid_: Label, topic, category (as a separate concept)

### Publishing

**Summary**:
A 1–2 sentence description of a Story, written for the Digest rather than copied from a Source.
_Avoid_: Excerpt, blurb, TL;DR

**Digest**:
What one Run publishes: every Story that is new since the previous successful Digest, grouped by primary Tag (biggest group first, `other` last) and ordered by Coverage within a group.
_Avoid_: Report, newsletter (until a Newsletter exists)

**Edition**:
A Digest named by its scheduled time (06:30, 11:30, 16:30, 21:30 GMT+8). A day's Editions share one page, newest first. A failed Edition's news arrives in the next Edition.
_Avoid_: Batch, issue, slot

**Run**:
One scheduled attempt to publish an Edition. A Run succeeds if it publishes a Digest, even one with some Sources unavailable; it fails only if nothing can be published.
_Avoid_: Job, execution, build

### Feedback

**Feedback**:
A 👍 or 👎 vote on a Story's page, one per browser, credited to every Source with an Item in that Story. Feedback informs Source health; it does not change a Digest's order.
_Avoid_: Rating, like, reaction

**Source health**:
How a Source has performed over the last 7 and 30 days: Items, failed fetches and Feedback. A Source is *flagged* when it is silent for 7 days, fails on 3 of the last 7 days, or gets more 👎 than 👍. Flags are suggestions; only the owner adds or drops Sources.
_Avoid_: Credibility score, source quality

**Reader**:
A person who receives a Digest. Currently only the owner.
_Avoid_: User, subscriber
