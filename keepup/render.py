"""Render layer: TopicDigest[] → static site in docs/.

The same page is written twice — docs/index.html (always the latest week) and
docs/archive/<week>.html (accumulates) — rendered per location because
relative links differ between the two.
"""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from keepup.models import TopicDigest


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
    env = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    template = env.get_template("digest.html.j2")

    for target, root in ((docs / "index.html", ""), (archive_dir / f"{week}.html", "../")):
        target.write_text(
            template.render(
                digests=digests,
                week=week,
                generated=generated,
                past_weeks=past_weeks,
                items_by_id={t.name: {i.id: i for i in t.items} for t in digests},
                root=root,
            )
        )
    # Pages must serve docs/ as-is, without a Jekyll build.
    (docs / ".nojekyll").touch()
