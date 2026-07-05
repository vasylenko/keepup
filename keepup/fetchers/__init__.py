"""Fetch layer: source config in, normalized Item[] out.

A failing source never fails the run — it lands in failed_sources and the
renderer footnotes it.
"""

from datetime import datetime
from urllib.parse import urlsplit

from keepup.config import Topic
from keepup.fetchers import hn, rss, sitemap
from keepup.models import Item


def fetch_topic(topic: Topic, since: datetime) -> tuple[list[Item], list[str]]:
    """Run every configured source for one topic, isolating failures."""
    items: list[Item] = []
    failed: list[str] = []

    for feed in topic.feeds:
        try:
            items += rss.fetch_feed(feed.url, since, feed.categories, feed.name)
        except Exception as exc:
            failed.append(f"{urlsplit(feed.url).netloc} ({exc.__class__.__name__})")

    for source in topic.sitemaps:
        try:
            items += sitemap.fetch_sitemap(source.url, source.path_prefix, since, source.name)
        except Exception as exc:
            failed.append(f"{urlsplit(source.url).netloc} ({exc.__class__.__name__})")

    if topic.hn_keywords:
        try:
            items += hn.fetch_keywords(topic.hn_keywords, since)
        except Exception as exc:
            failed.append(f"Hacker News ({exc.__class__.__name__})")

    return items, failed
