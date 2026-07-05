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
_DATE = re.compile(r"[A-Z][a-z]{2,8} \d{1,2}, \d{4}")
# lastmod means modified, not published: a site redeploy can bump every URL.
# The cap bounds page fetches in that case; on-page dates re-filter below.
_MAX_PAGES = 25


def _parse_date(text: str) -> datetime | None:
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _h1_date(html: str) -> datetime | None:
    """Publish date rendered next to the page's h1 (anthropic.com style).

    Read from raw HTML because Readability strips the title header block,
    so the date never survives into markfetch's markdown.
    """
    match = re.search(r"</h1>.{0,300}?(" + _DATE.pattern + ")", html, re.S)
    return _parse_date(match.group(1)) if match else None


def _page_date(markdown: str) -> datetime | None:
    """Fallback for pages whose extracted body still opens with the date."""
    match = _DATE.search(markdown[:600])
    return _parse_date(match.group(0)) if match else None


def _meta_description(html: str) -> str:
    """The publisher's own summary (og:description / meta description) —
    hand-written to be the one-line pitch, so it beats anything we derive."""
    import html as html_entities

    for tag in re.finditer(r"<meta\s[^>]*>", html[:20000], re.I):
        if not re.search(r"""(?:name|property)=["'](?:og:)?description["']""", tag.group(0), re.I):
            continue
        content = re.search(r"""content=["']([^"']+)""", tag.group(0))
        if content:
            return html_entities.unescape(content.group(1)).strip()
    return ""


def _markfetch(url: str) -> str | None:
    """Run the markfetch CLI: markdown on stdout, non-zero exit on failure.

    A missing binary is a source-level failure (raise); a single bad page is
    not (None) — one broken article must not hide the rest of the week.
    """
    result = subprocess.run(
        ["markfetch", url], capture_output=True, text=True, timeout=60
    )
    return result.stdout if result.returncode == 0 else None


def fetch_sitemap(url: str, path_prefix: str, since: datetime, name: str = "") -> list[Item]:
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
    for _, loc in candidates[:_MAX_PAGES]:
        # The page's own date is required; lastmod only shortlists candidates.
        # Trusting lastmod resurfaces years-old posts after a site redeploy.
        page = requests.get(loc, headers={"User-Agent": CHROME_UA}, timeout=TIMEOUT)
        page_html = page.text if page.ok else ""
        published = _h1_date(page_html)
        if published and published < since:
            continue
        markdown = _markfetch(loc)
        if not markdown:
            continue
        published = published or _page_date(markdown)
        if not published or published < since:
            continue
        lines = [l.strip() for l in markdown.splitlines() if l.strip()]
        title = next((l.lstrip("# ") for l in lines if l.startswith("# ")), loc)
        body = " ".join(l for l in lines if not l.startswith("#"))
        items.append(
            make_item(
                title=title,
                url=loc,
                source=name or urlsplit(url).netloc.removeprefix("www."),
                published=published,
                excerpt=_meta_description(page_html) or body[:500],
            )
        )
    return items
