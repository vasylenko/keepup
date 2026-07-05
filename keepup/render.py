"""Render layer: TopicDigest[] → static site in docs/.

The same page is written twice — docs/index.html (always the latest week) and
docs/archive/<week>.html (accumulates) — rendered per location because
relative links differ between the two.
"""

import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from keepup.models import TopicDigest


def first_sentence(text: str, limit: int = 220) -> str:
    """One-line description from a feed summary, which may be a whole post body."""
    match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    return (match.group(1) if match else text)[:limit]


def render(
    digests: list[TopicDigest],
    week: str,
    generated: datetime,
    docs: str | Path = "docs",
    templates: str | Path = "templates",
) -> None:
    docs = Path(docs)
    archive_dir = docs / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    past_weeks = sorted(
        (p.stem for p in archive_dir.glob("*.html") if p.stem != week), reverse=True
    )
    # Every topic renders as source-grouped content (h2 topic → h3 source):
    # stories group by their lead item's source with LLM rank order preserved;
    # verbatim items group by source, groups ordered by their newest item.
    stories_by_vendor: dict[str, dict[str, list]] = {}
    items_by_source: dict[str, dict[str, list]] = {}
    for t in digests:
        by_id = {i.id: i for i in t.items}
        story_groups: dict[str, list] = {}
        for story in t.stories or []:
            story_groups.setdefault(by_id[story.item_ids[0]].source, []).append(story)
        stories_by_vendor[t.name] = story_groups
        item_groups: dict[str, list] = {}
        for item in t.items:  # already newest-first
            item_groups.setdefault(item.source, []).append(item)
        # Quiet sources still get a group (rendered as a one-line note) —
        # unless they outright failed, which the footnote already covers.
        failed_names = {f.split(" (")[0] for f in t.failed_sources}
        for name in t.sources:
            present = any(name in group.split(" + ") for group in item_groups)
            if not present and name not in failed_names:
                item_groups[name] = []
        items_by_source[t.name] = item_groups
    env = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    env.filters["first_sentence"] = first_sentence
    template = env.get_template("digest.html.j2")

    for target, root in ((docs / "index.html", ""), (archive_dir / f"{week}.html", "../")):
        target.write_text(
            template.render(
                digests=digests,
                week=week,
                generated=generated,
                past_weeks=past_weeks,
                items_by_id={t.name: {i.id: i for i in t.items} for t in digests},
                stories_by_vendor=stories_by_vendor,
                items_by_source=items_by_source,
                root=root,
            )
        )
    # Pages must serve docs/ as-is, without a Jekyll build.
    (docs / ".nojekyll").touch()
