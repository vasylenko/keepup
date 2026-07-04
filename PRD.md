# keepup — Weekly Tech Digest

One static page, rebuilt every Monday, that replaces my round of blogs, X, Reddit, and HN. Personal project. KISS: no servers, no DB, $0.

## Problem

Following N technologies = N blogs + X accounts + subreddits + release pages, checked manually. Scattered, repetitive, and the important stuff (a major release) looks the same size as noise (a minor blog post).

## Product principle — why this isn't another feed reader

A feed reader moves the pile; this shrinks it. The digest must do three things a reader doesn't:

1. **Cluster** — the same event (e.g. a Claude release) arrives via vendor blog, X, and HN as separate items. It is one story, told once.
2. **Rank** — multi-source echo is the significance signal. A story covered by 3 sources outranks a lone blog post. Lead with what matters; bury or drop the rest.
3. **Bound** — the whole digest reads in ≤10 minutes. A topic with nothing notable says "Quiet week." — never padded.

## Solution

GitHub Actions cron (Mon ~05:00 UTC, `workflow_dispatch` for reruns): fetch the week's items from curated sources per topic → one LLM call per topic clusters, ranks, and synthesizes → render static HTML → deploy to GitHub Pages. Index = latest week; archive at `/archive/2026-Wnn.html`.

## Non-goals

- Multi-user, auth, personalization, real-time/daily updates
- Databases, servers, queues — the repo and run date are the only state
- Guaranteed X coverage (best-effort by design)

## Anti-slop contract (acceptance criteria for the LLM output)

- **Grounded links only**: the LLM references items by ID from the provided list; the renderer resolves IDs to URLs. Any URL not in the fetched set cannot appear. Hallucinated stories have nowhere to attach.
- **Structured output**: LLM returns JSON (`stories[{headline, why_it_matters, item_ids[]}]`), not prose HTML. The renderer owns presentation.
- **Every story answers**: what changed + why I should care. Banned: hype filler ("exciting", "game-changing"), restating headlines without substance.
- **Honest gaps**: failed sources are listed in a footnote; a quiet topic says so in one line.
- The synthesis prompt lives in the repo (`keepup/prompts/`) and is versioned like code — it *is* the product.

## Functional requirements

**Topics & sources** — `config/topics.yml`, curated by hand:

```yaml
topics:
  - name: AI/LLM tooling
    feeds:
      - url: https://openai.com/news/rss.xml
      - url: https://rsshub.app/anthropic/news        # bridge: Anthropic has no official RSS
        fallbacks: [https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml]
    x_accounts: [simonw, …]
    subreddits: [LocalLLaMA]        # M3
    hn_keywords: [claude, mcp]      # M3
```

Seed topics: AI/LLM tooling · Cloud & IaC · DevOps/SRE tooling.

Seed feeds (M1), **verified to exist as of July 2026**:
- OpenAI: `https://openai.com/news/rss.xml` — official, working (old `/blog/rss.xml` is dead).
- AWS: `https://aws.amazon.com/about-aws/whats-new/recent/feed/` — official, long-standing.
- Anthropic: **no official RSS exists.** Bridge via RSSHub public route (`https://rsshub.app/anthropic/news`) with a community GitHub-raw feed as fallback (`taobojlen/anthropic-rss-feed`, daily-regenerated; GitHub raw is always reachable from Actions). Sites without RSS are a config concern, not a code concern: every feed entry may list `fallbacks` tried in order.

**Fetchers** — one per source type, all emitting `Item{id, title, url, source, published, excerpt}`; approaches verified against July-2026 platform behavior:
- **RSS/Atom**: `feedparser`. Covers blogs and GitHub release feeds (`/releases.atom`).
- **X (best-effort)**: Nitter-compatible RSS, instance list in config (`xcancel.com` direct + `twiiit.com` redirect discovery), custom User-Agent (required since 2026-01), per-account tolerance for failure. Honest caveat: Actions runners are datacenter IPs, the same class X/Reddit are blocking — this may work partially or not at all. Adapter interface so a paid API (or RSS-Bridge on other infra) slots in without pipeline changes.
- **Reddit (M3)**: official OAuth API, free "script" app, plain `requests` against `/r/X/new`. Public `.json`/`.rss` endpoints 403 datacenter IPs since ~Apr 2026 — not an option from Actions.
- **HN (M3)**: Algolia HN Search API — free, no auth, 10k req/hr, keyword + `created_at_i` week window.

**Pipeline** (single Python run):
1. Fetch all sources, 7-day window by published date; per-source timeout; a failing source never fails the run — it's skipped and footnoted.
2. Normalize; dedupe by canonical URL (strip tracking params).
3. Per topic: cap at ~40 items × ~500-char excerpts (fits free-tier context comfortably), one chat-completions call to GitHub Models (OpenAI-compatible, `https://models.github.ai/inference`). LLM failure ⇒ that topic renders links-only. 3–6 calls/week vs 50 RPD limit — ample headroom, and the OpenAI-compatible client makes provider swap a config change.
4. Render (Jinja2): per topic — ranked stories (headline, why-it-matters, source links) on top, collapsible full link list below. No JS required for reading. Deploy via `actions/deploy-pages`.

**Operations**:
- Public repo, public Pages URL (free-plan requirement; confirmed acceptable).
- Secrets: none for M1 beyond `GITHUB_TOKEN` (`permissions: models: read, pages: write, id-token: write`); M3 adds `REDDIT_CLIENT_ID`/`SECRET`.
- Budget: $0.

## Risks

| Risk | Stance |
|---|---|
| X fetch breaks (likely, eventually) | Best-effort by design; digest degrades gracefully, footnote shows the gap; adapter swap point is defined |
| Reddit tightens further | OAuth is the sanctioned path; if it dies, HN keywords cover much of the same ground |
| GitHub Models limits/product changes | Weekly volume is ~10% of free quota; OpenAI-compatible = trivial provider swap |
| Missing/garbage `published` dates in feeds | Items without a parseable date in-window are dropped; acceptable loss for statelessness |
| RSSHub public instance rate-limits or dies | Per-feed `fallbacks` list; RSSHub is also self-hostable if it ever matters |
| Digest drifts into slop | Anti-slop contract above is the review checklist for every prompt change |

## Tech decisions

- Python 3.14, deps: `feedparser`, `requests`, `jinja2`, `pyyaml`, `openai`
- No persistent state: week window computed from run date; dedupe within-run
- Layout: `keepup/` (package, incl. `prompts/`) · `config/topics.yml` · `templates/` · `.github/workflows/digest.yml`

## Milestones

1. **M1** (end-to-end): RSS fetcher (Anthropic, OpenAI, AWS feeds) + X best-effort adapter + LLM synthesis + renderer + Pages deploy. Ships the actual product for the AI topic.
2. **M2**: remaining seed topics fleshed out; archive polish; digest self-RSS feed (so a new week can ping my reader).
3. **M3**: Reddit + HN fetchers.

## Success & kill criteria

- **Success**: on Monday I read keepup instead of my bookmark round, and I stop feeling like I'm missing releases.
- **Kill/fix trigger**: two consecutive weeks where the digest told me nothing my old routine would have — revisit sources and prompt, or admit the experiment failed. This is a tool with a job, not a repo to tend.
