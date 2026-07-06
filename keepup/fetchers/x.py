"""X author-timeline fetcher — the one source that bypasses markfetch.

X offers no unauthenticated read path (the free API tier died in Feb 2026),
so this fetcher talks to the v2 API via tweepy, billed pay-per-use per post
read. `X_BEARER_TOKEN` must be set; without it every account lands in the
failed-sources footnote and the rest of the digest builds normally.
"""

import os
from datetime import datetime
from textwrap import shorten

import tweepy

from keepup.models import Item, make_item

_TITLE_WIDTH = 120  # tweets have no title; the opening words serve as one


def _expand_urls(text: str, entities: dict | None) -> str:
    """Swap t.co wrappers for real URLs so excerpts read like the tweet did."""
    for url in (entities or {}).get("urls", []):
        text = text.replace(url["url"], url.get("expanded_url") or url["url"])
    return text


def fetch_account(handle: str, since: datetime, name: str = "") -> list[Item]:
    """Return one author's original posts and thread heads inside the window.

    Retweets and replies are excluded server-side: a thread's continuations
    are self-replies, so excluding replies collapses each thread to its head
    tweet — and every excluded post is a post we aren't billed for reading.
    """
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        raise RuntimeError("X_BEARER_TOKEN not set")
    client = tweepy.Client(bearer_token=token)

    try:
        user = client.get_user(username=handle).data
        if user is None:
            raise RuntimeError("user not found")
        response = client.get_users_tweets(
            user.id,
            start_time=since,
            max_results=100,  # covers a week of originals for any human author
            exclude=["retweets", "replies"],
            tweet_fields=["created_at", "entities"],
        )
    except tweepy.HTTPException as exc:
        # Full tweepy messages are multi-line; the footnote wants one code.
        raise RuntimeError(f"HTTP {exc.response.status_code}") from exc

    source = name or f"@{handle}"
    items = []
    for tweet in response.data or []:
        text = _expand_urls(tweet.text, tweet.entities)
        items.append(
            make_item(
                title=shorten(text, _TITLE_WIDTH, placeholder="…"),
                url=f"https://x.com/{handle}/status/{tweet.id}",
                source=source,
                published=tweet.created_at,
                excerpt=text,
            )
        )
    return items
