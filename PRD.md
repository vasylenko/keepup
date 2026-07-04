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

GitHub Actions cron (Mon ~05:00 UTC, `workflow_dispatch` for reruns): fetch the week's items from curated sources per topic → deterministic per-topic selection → one LLM call per topic clusters, ranks, and synthesizes → render static HTML into `docs/` → commit to `main`. GitHub Pages serves the branch (`/docs` folder, `.nojekyll`): the commit is the deploy, the archive, and the repo activity that keeps the schedule enabled. Index = latest week; past weeks accumulate at `/archive/2026-Wnn.html`.

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
    sitemaps:
      - url: https://www.anthropic.com/sitemap.xml   # Anthropic has no RSS
        path_prefix: /news/
    x_accounts: [simonw, …]         # M3
    subreddits: [LocalLLaMA]        # M3
    hn_keywords: [claude, mcp]
```

Seed topics: AI/LLM tooling · Cloud & IaC · DevOps/SRE tooling.

Seed sources (M1):
- OpenAI: `https://openai.com/news/rss.xml`
- AWS: `https://aws.amazon.com/about-aws/whats-new/recent/feed/`
- Anthropic: no RSS — sitemap fetcher against `https://www.anthropic.com/sitemap.xml`, `/news/` prefix

**Fetchers** — one per source type, all emitting `Item{id, title, url, source, published, excerpt}`:
- **RSS/Atom**: `feedparser`. Covers blogs and GitHub release feeds (`/releases.atom`).
- **Sitemap (RSS-less sites)**: discover URLs via the site's `sitemap.xml` (`requests`; filter by `path_prefix`, window by `lastmod`), then fetch each candidate page with the `markfetch` CLI (markdown on stdout, `[code]` on stderr, non-zero exit). The on-page publish date wins over `lastmod` (modified ≠ published); the same fetch yields the excerpt.
- **X (best-effort, M3)**: Nitter-compatible RSS, instance list in config (`xcancel.com` direct + `twiiit.com` redirect discovery), custom User-Agent, per-account tolerance for failure. Adapter interface so a paid API slots in without pipeline changes.
- **Reddit (M3)**: official OAuth API, free "script" app, plain `requests` against `/r/X/new`.
- **HN**: Algolia HN Search API — free, no auth, keyword + `created_at_i` week window.

**Pipeline** (single Python run):
1. Fetch all sources, 7-day window by published date (undated items are dropped); per-source timeout; a failing source never fails the run — it's skipped and footnoted.
2. Normalize; dedupe by canonical URL (strip tracking params).
3. Per topic: **select** ≤40 items by newest-first round-robin across sources, so a single high-volume feed can't crowd out the cross-source echoes ranking depends on. One chat-completions call to GitHub Models (OpenAI-compatible, `https://models.github.ai/inference`); excerpt budget derives from the free tier's 8k-in/4k-out per-request cap. LLM failure ⇒ that topic renders links-only.
4. Render (Jinja2) into `docs/`: per topic — ranked stories (headline, why-it-matters, source links) on top, collapsible full link list below. No JS required for reading. Publish = commit `docs/` to `main`; Pages serves from the branch.

**Operations**:
- Public repo, public Pages URL (free plan).
- Secrets: none for M1 beyond `GITHUB_TOKEN` (`permissions: models: read, contents: write`); M3 adds `REDDIT_CLIENT_ID`/`SECRET`.
- Budget: $0.

## Tech decisions

- Python 3.14, deps: `feedparser`, `requests`, `jinja2`, `pyyaml`, `openai`; plus the `markfetch` CLI (npm) as a subprocess for page→markdown.
- State = the repo, nothing else: rendered weeks are committed (archive + Pages source + schedule keepalive). Week window computed from run date; dedupe within-run.
- Layout: `keepup/` (package, incl. `prompts/`) · `config/topics.yml` · `templates/` · `docs/` (published site) · `.github/workflows/digest.yml`

### Layers & contracts

Five layers, each swappable behind its contract; prototype bindings in parentheses:

1. **Fetch**: source config → `Item[]` (feedparser, Algolia, sitemap + markfetch; one adapter per source type)
2. **Select**: `Item[]` → ≤N per topic, deterministic and source-diverse (newest-first round-robin)
3. **Synthesize**: selected items → `stories[]` JSON (GitHub Models behind the OpenAI-compatible client; provider + model are config)
4. **Render**: stories + items → directory of static files (Jinja2)
5. **Publish**: static dir → public URL (git commit + Pages-from-branch; any static host — S3, Cloudflare, Netlify — consumes the same directory)

## Milestones

1. **M1** (end-to-end): RSS fetcher (OpenAI, AWS) + sitemap fetcher (Anthropic) + HN keyword fetcher + selection + LLM synthesis + renderer + branch publish. Ships the actual product for the AI topic.
2. **M2**: remaining seed topics fleshed out; archive polish; digest self-RSS feed (so a new week can ping my reader).
3. **M3**: Reddit fetcher + X best-effort adapter.

## Success & kill criteria

- **Success**: on Monday I read keepup instead of my bookmark round, and I stop feeling like I'm missing releases.
- **Kill/fix trigger**: two consecutive weeks where the digest told me nothing my old routine would have — revisit sources and prompt, or admit the experiment failed. This is a tool with a job, not a repo to tend.
