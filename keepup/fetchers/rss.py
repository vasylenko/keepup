"""RSS/Atom fetcher — covers blogs and GitHub /releases.atom feeds."""

import html
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

import feedparser
import requests

from keepup.fetchers.common import CHROME_UA, TIMEOUT
from keepup.models import Item, make_item

_TAGS = re.compile(r"<[^>]+>")


def _clean(text: str, limit: int = 500) -> str:
    """Feed summaries arrive as HTML; the pipeline works in plain text."""
    return " ".join(html.unescape(_TAGS.sub(" ", text)).split())[:limit]


def fetch_feed(url: str, since: datetime) -> list[Item]:
    """Fetch one feed and return items published inside the window.

    Fetched via requests (feedparser has no timeout control), then parsed
    from bytes. Undated entries are dropped — the week window is the product.
    """
    resp = requests.get(url, headers={"User-Agent": CHROME_UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"unparseable feed: {parsed.bozo_exception}")

    source = parsed.feed.get("title") or urlsplit(url).netloc
    items = []
    for entry in parsed.entries:
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if not stamp or not entry.get("link"):
            continue
        published = datetime(*stamp[:6], tzinfo=UTC)
        if published < since:
            continue
        items.append(
            make_item(
                title=entry.get("title", "(untitled)"),
                url=entry.link,
                source=source,
                published=published,
                excerpt=_clean(entry.get("summary", "")),
            )
        )
    return items
