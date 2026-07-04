"""Hacker News fetcher — Algolia HN Search API, keyword search in the week window."""

from datetime import UTC, datetime

import requests

from keepup.fetchers.common import TIMEOUT
from keepup.models import Item, make_item

API = "https://hn.algolia.com/api/v1/search_by_date"


def fetch_keywords(keywords: list[str], since: datetime) -> list[Item]:
    """One API call per keyword; stories deduped across keywords by HN id.

    Points/comments go into the excerpt — community traction is exactly the
    significance signal the ranker looks for.
    """
    seen: dict[str, Item] = {}
    for kw in keywords:
        resp = requests.get(
            API,
            params={
                "query": kw,
                "tags": "story",
                "numericFilters": f"created_at_i>{int(since.timestamp())}",
                "hitsPerPage": 50,
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        for hit in resp.json()["hits"]:
            hn_id = hit["objectID"]
            if hn_id in seen or not hit.get("title"):
                continue
            seen[hn_id] = make_item(
                title=hit["title"],
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={hn_id}",
                source="Hacker News",
                published=datetime.fromtimestamp(hit["created_at_i"], tz=UTC),
                excerpt=f"{hit.get('points') or 0} points, "
                f"{hit.get('num_comments') or 0} comments on HN",
            )
    return list(seen.values())
