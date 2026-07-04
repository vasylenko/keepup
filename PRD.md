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

GitHub Actions cron (Mon ~05:00 UTC, `workflow_dispatch` for reruns): fetch the week's items from curated sources per topic → deterministic per-topic selection → one LLM call per topic clusters, ranks, and synthesizes → render static HTML into `docs/` → commit to `main`. GitHub Pages serves the branch (`/docs` folder, `.nojekyll`), so the commit **is** the deploy, the archive, and the cron keepalive — GitHub auto-disables schedules in public repos after 60 days without repository activity, and the weekly output commit resets that clock. Index = latest week; past weeks accumulate at `/archive/2026-Wnn.html`.

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

Seed sources (M1), **verified working as of July 2026**:
- OpenAI: `https://openai.com/news/rss.xml` — official, working (old `/blog/rss.xml` is dead).
- AWS: `https://aws.amazon.com/about-aws/whats-new/recent/feed/` — official, long-standing.
- Anthropic: **no official RSS exists** — covered by the sitemap fetcher against `https://www.anthropic.com/sitemap.xml` with `/news/` prefix. Verified: 482 URLs, real per-page `lastmod` timestamps, and deploy-time `lastmod` bumps don't touch `/news/` pages, so the week window stays clean.

**Fetchers** — one per source type, all emitting `Item{id, title, url, source, published, excerpt}`; approaches verified against July-2026 platform behavior:
- **RSS/Atom**: `feedparser`. Covers blogs and GitHub release feeds (`/releases.atom`).
- **Sitemap (RSS-less sites)**: discover via the site's own `sitemap.xml` (`requests`; filter by configured `path_prefix`, window by `lastmod`), then fetch each candidate page with the `markfetch` CLI — subprocess contract: markdown on stdout, `[code] message` on stderr, non-zero exit on failure. The on-page publish date is authoritative because `lastmod` means modified, not published — edited old posts are filtered at this step, which also yields the excerpt. Candidate volume is a handful of pages/week per site; markfetch's real-Chrome fingerprint is what gets them past bot protection from datacenter IPs.
- **X (best-effort, M3)**: Nitter-compatible RSS, instance list in config (`xcancel.com` direct + `twiiit.com` redirect discovery), custom User-Agent (required since 2026-01), per-account tolerance for failure. Honest caveat: Actions runners are datacenter IPs, the same class X/Reddit are blocking — this may work partially or not at all. Adapter interface so a paid API (or RSS-Bridge on other infra) slots in without pipeline changes.
- **Reddit (M3)**: official OAuth API, free "script" app, plain `requests` against `/r/X/new`. Public `.json`/`.rss` endpoints 403 datacenter IPs since ~Apr 2026 — not an option from Actions.
- **HN**: Algolia HN Search API — free, no auth, 10k req/hr, keyword + `created_at_i` week window. The cheapest reliable second source class, which is why it ships in M1: without it there is no cross-source echo to rank by.

**Pipeline** (single Python run):
1. Fetch all sources, 7-day window by published date; per-source timeout; a failing source never fails the run — it's skipped and footnoted.
2. Normalize; dedupe by canonical URL (strip tracking params).
3. Per topic: **select** ≤40 items by newest-first round-robin across sources — a single high-volume feed (AWS What's New alone ships 50–100 items/week) must never crowd out the cross-source echoes ranking depends on. Selection is deterministic and versioned like the prompt: it decides what the LLM never sees, so it is the ranker's front half. Then one chat-completions call to GitHub Models (OpenAI-compatible, `https://models.github.ai/inference`). The binding free-tier constraint is per-request tokens (8k in / 4k out), not the 50 RPD (3–6 calls/week): 40 items × ~500-char excerpts ≈ 6–7k tokens with prompt, so the excerpt budget is derived from that cap. LLM failure ⇒ that topic renders links-only.
4. Render (Jinja2) into `docs/`: per topic — ranked stories (headline, why-it-matters, source links) on top, collapsible full link list below. No JS required for reading. Publish = commit `docs/` to `main`; Pages serves from the branch.

**Operations**:
- Public repo, public Pages URL (free-plan requirement; confirmed acceptable).
- Secrets: none for M1 beyond `GITHUB_TOKEN` (`permissions: models: read, contents: write`); M3 adds `REDDIT_CLIENT_ID`/`SECRET`.
- Budget: $0.

## Risks

| Risk | Stance |
|---|---|
| X fetch breaks (likely, eventually) | Best-effort by design; digest degrades gracefully, footnote shows the gap; adapter swap point is defined |
| Reddit tightens further | OAuth is the sanctioned path; if it dies, HN keywords cover much of the same ground |
| GitHub Models limits/product changes | Weekly volume is ~10% of free quota; OpenAI-compatible = trivial provider swap |
| Public-repo cron auto-disabled after 60 days of repo inactivity | Designed out: the weekly output commit is repository activity |
| Missing/garbage `published` dates in feeds | Items without a parseable date in-window are dropped; acceptable loss for statelessness |
| Bot protection blocks sitemap/article fetches from Actions datacenter IPs | markfetch sends a real-Chrome fingerprint; smoke-test from a runner early in M1; a blocked source degrades to a footnote like any other |
| Digest drifts into slop | Anti-slop contract above is the review checklist for every prompt change |

## Tech decisions

- Python 3.14, deps: `feedparser`, `requests`, `jinja2`, `pyyaml`, `openai`. One external CLI: `markfetch` (npm, self-contained; Node is preinstalled on GitHub runners, `npm i -g markfetch` in the workflow). Python orchestrates everything — markfetch is a leaf tool at a subprocess boundary, never an orchestrator.
- State = the repo, nothing else: rendered weeks are committed — they are the archive, the Pages source, and the cron keepalive at once. Week window computed from run date; dedupe within-run.
- Layout: `keepup/` (package, incl. `prompts/`) · `config/topics.yml` · `templates/` · `docs/` (published site) · `.github/workflows/digest.yml`

### Layers & contracts

The pipeline is five layers; each is swappable behind its contract, so the prototype bindings (in parentheses) are conveniences, not commitments — model and host in particular are expected to change without touching neighboring layers:

1. **Fetch**: source config → `Item[]` (feedparser, Algolia, sitemap + markfetch; one adapter per source type)
2. **Select**: `Item[]` → ≤N per topic, deterministic and source-diverse (newest-first round-robin)
3. **Synthesize**: selected items → `stories[]` JSON (GitHub Models behind the OpenAI-compatible client; provider + model are config)
4. **Render**: stories + items → directory of static files (Jinja2)
5. **Publish**: static dir → public URL (git commit + Pages-from-branch; any static host — S3, Cloudflare, Netlify — consumes the same directory)

## Milestones

1. **M1** (end-to-end): RSS fetcher (OpenAI, AWS) + sitemap fetcher (Anthropic) + HN keyword fetcher + selection + LLM synthesis + renderer + branch publish. Ships the actual product for the AI topic with a real multi-source echo signal — vendor blog + HN thread is the canonical cluster.
2. **M2**: remaining seed topics fleshed out; archive polish; digest self-RSS feed (so a new week can ping my reader).
3. **M3**: Reddit fetcher + X best-effort adapter — the most fragile source goes last, so its (expected) failure can't block proving the concept.

## Success & kill criteria

- **Success**: on Monday I read keepup instead of my bookmark round, and I stop feeling like I'm missing releases.
- **Kill/fix trigger**: two consecutive weeks where the digest told me nothing my old routine would have — revisit sources and prompt, or admit the experiment failed. This is a tool with a job, not a repo to tend.
