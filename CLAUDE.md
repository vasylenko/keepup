# keepup

Personal weekly tech digest — one static page rebuilt every Monday by GitHub Actions and served by Pages at https://vasylenko.github.io/keepup/. Curating sources in `config/topics.yml` is most of the work here.

## All HTTP goes through markfetch — don't add a Python HTTP client

Every fetch runs through the `markfetch` CLI via `fetch_raw()` in `keepup/fetchers/markfetch.py` (`markfetch --raw`). Don't add `requests`, `httpx`, or `urllib` — markfetch (Serhii's own npm tool) owns the wire, including the HTTP/1.1 trick that gets past Cloudflare. Consequences: it must be installed to run locally (`npm i -g markfetch`, then `uv run python -m keepup`), and the AWS bucketing call needs `GITHUB_TOKEN` — without it that section falls back to a flat, unsorted list.

## Source filters match publishers' own tag strings, not concepts

`categories:` in `config/topics.yml` is compared verbatim against each feed's `<category>` values — `kubernetes` matches nothing unless the feed literally emits that string. Read a feed's real category values before filtering on them. AWS is the trap: it tags some items with only a product slug (`general:products/aws-secrets-manager`) and no `marchitecture` area, so an area-only filter silently drops them.

## Adding a sitemap source: confirm the page's date format

`fetchers/sitemap.py` dates each item from an h1-adjacent `Mon DD, YYYY` string in the raw HTML. `lastmod` only shortlists candidates, it never dates them — a redeploy bumps it sitewide. Pages with no matching date are dropped, so a new RSS-less site that formats dates differently yields nothing until you extend the date patterns.

## The weekly commit is both the deploy and the keepalive

Each run re-renders `docs/` (the generated timestamp always changes) and commits to `main`; Pages serves `main`/`docs`. That commit also counts as the repo activity GitHub needs to avoid auto-disabling the cron after 60 days idle — so don't make the output deterministic-per-week to "skip empty commits." The churn is load-bearing.
