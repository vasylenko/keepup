"""Data shapes passed between pipeline layers — these are the layer contracts."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query params that vary per visitor/campaign but not per document; stripping
# them lets the same article fetched via RSS and HN collapse into one item.
_TRACKING_PARAMS = re.compile(r"^(utm_|ref_|fbclid$|gclid$|mc_)")


@dataclass
class Item:
    """One fetched piece of content, normalized across all source types."""

    id: str  # short hash of the canonical URL — the LLM references this
    title: str
    url: str
    source: str  # origin name; multi-source echoes join with " + "
    published: datetime  # timezone-aware UTC
    excerpt: str = ""


@dataclass
class Story:
    """One synthesized digest story; item_ids may only reference fetched Items."""

    headline: str
    why_it_matters: str
    item_ids: list[str]


@dataclass
class TopicDigest:
    """Everything the renderer needs for one topic section."""

    name: str
    items: list[Item]  # selected items, newest first
    stories: list[Story] | None  # None ⇒ synthesis failed ⇒ links-only
    failed_sources: list[str] = field(default_factory=list)
    synthesize: bool = True  # False ⇒ headlines verbatim, by design not by failure


def canonical_url(url: str) -> str:
    """Normalize a URL so duplicates across sources share one identity."""
    scheme, netloc, path, query, _ = urlsplit(url.strip())
    kept = [(k, v) for k, v in parse_qsl(query) if not _TRACKING_PARAMS.match(k)]
    return urlunsplit(
        (scheme.lower(), netloc.lower(), path.rstrip("/") or "/", urlencode(kept), "")
    )


def make_item(title: str, url: str, source: str, published: datetime, excerpt: str = "") -> Item:
    """Single constructor for all fetchers, so item identity is defined once."""
    canon = canonical_url(url)
    item_id = hashlib.sha1(canon.encode()).hexdigest()[:8]
    return Item(item_id, title.strip(), canon, source, published, excerpt.strip())
