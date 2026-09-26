# ai-news

A daily digest of anything new from sources the owner chooses, filtered by the owner's preferences. Today it has one reader, but it may grow into a newsletter shared on Telegram or a webpage.

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

### Selecting

**Tag**:
A category from a fixed, owner-defined list that describes what a Story is about. A Story can have several Tags; one that fits none gets `other`.
_Avoid_: Label, topic, category (as a separate concept)

**Preference**:
The owner's stance on a Tag: **preferred**, **neutral** or **muted**. Preferences only order Stories in a Digest, never hide them; muted Stories sink to the bottom.
_Avoid_: Filter, rule, setting

### Publishing

**Summary**:
A 1–2 sentence description of a Story, written for the Digest rather than copied from a Source.
_Avoid_: Excerpt, blurb, TL;DR

**Digest**:
The single Markdown document produced each morning, listing every Story that is new since the previous successful Digest, ordered by Preference and then by Coverage.
_Avoid_: Report, newsletter (until a Newsletter exists)

**Run**:
One scheduled attempt to produce a Digest. A Run succeeds if it publishes a Digest, even one with some Sources unavailable; it fails only if nothing can be published.
_Avoid_: Job, execution, build

**Reader**:
A person who receives a Digest. Currently only the owner.
_Avoid_: User, subscriber
