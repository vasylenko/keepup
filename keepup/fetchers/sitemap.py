"""Sitemap fetcher for sites without RSS (e.g. anthropic.com).

Two steps: sitemap.xml discovers candidate URLs, the markfetch CLI turns each
page into markdown for the title, publish date, and excerpt.
"""

import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from urllib.parse import urlsplit

import requests

from keepup.fetchers.common import CHROME_UA, TIMEOUT
from keepup.models import Item, make_item

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
# "Jun 30, 2026" / "June 30, 2026" — the publish-date style on article pages.
_DATE = re.compile(r"([A-Z][a-z]{2,8}) (\d{1,2}), (\d{4})")
# lastmod means modified, not published: a site redeploy can bump every URL.
# The cap bounds markfetch calls in that case; on-page dates re-filter below.
_MAX_PAGES = 25


def _page_date(markdown: str) -> datetime | None:
    """Publish date printed on the page — authoritative over sitemap lastmod."""
    match = _DATE.search(markdown[:600])
    if not match:
        return None
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(match.group(0), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _markfetch(url: str) -> str | None:
    """Run the markfetch CLI: markdown on stdout, non-zero exit on failure.

    A missing binary is a source-level failure (raise); a single bad page is
    not (None) — one broken article must not hide the rest of the week.
    """
    result = subprocess.run(
        ["markfetch", url], capture_output=True, text=True, timeout=60
    )
    return result.stdout if result.returncode == 0 else None


def fetch_sitemap(url: str, path_prefix: str, since: datetime) -> list[Item]:
    """Fetch pages under path_prefix whose content is inside the week window."""
    resp = requests.get(url, headers={"User-Agent": CHROME_UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    candidates = []
    for node in root.findall("sm:url", _NS):
        loc = node.findtext("sm:loc", "", _NS)
        lastmod_raw = node.findtext("sm:lastmod", "", _NS)
        if not loc or not lastmod_raw or not urlsplit(loc).path.startswith(path_prefix):
            continue
        lastmod = datetime.fromisoformat(lastmod_raw.replace("Z", "+00:00"))
        if lastmod.tzinfo is None:
            lastmod = lastmod.replace(tzinfo=UTC)
        if lastmod >= since:
            candidates.append((lastmod, loc))
    candidates.sort(reverse=True)

    items = []
    for lastmod, loc in candidates[:_MAX_PAGES]:
        markdown = _markfetch(loc)
        if not markdown:
            continue
        published = _page_date(markdown) or lastmod
        if published < since:
            continue
        lines = [l.strip() for l in markdown.splitlines() if l.strip()]
        title = next((l.lstrip("# ") for l in lines if l.startswith("# ")), loc)
        body = " ".join(l for l in lines if not l.startswith("#"))
        items.append(
            make_item(
                title=title,
                url=loc,
                source=urlsplit(url).netloc.removeprefix("www."),
                published=published,
                excerpt=body[:500],
            )
        )
    return items
