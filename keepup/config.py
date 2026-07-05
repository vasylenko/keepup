"""Loads config/topics.yml into typed config objects."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class FeedSource:
    url: str
    categories: list[str] = field(default_factory=list)  # empty ⇒ take all entries
    name: str = ""  # display name when the feed's own title is unhelpful


@dataclass
class SitemapSource:
    url: str
    path_prefix: str
    name: str = ""  # display name when the bare hostname is unhelpful


@dataclass
class Topic:
    name: str
    feeds: list[FeedSource] = field(default_factory=list)
    sitemaps: list[SitemapSource] = field(default_factory=list)
    hn_keywords: list[str] = field(default_factory=list)
    synthesize: bool = True  # False ⇒ no LLM pass, render headlines verbatim


@dataclass
class Config:
    model: str
    topics: list[Topic]


def load_config(path: str | Path = "config/topics.yml") -> Config:
    """Parse the hand-curated topics file; fail loudly on malformed config."""
    raw = yaml.safe_load(Path(path).read_text())
    topics = [
        Topic(
            name=t["name"],
            feeds=[
                FeedSource(f["url"], f.get("categories", []), f.get("name", ""))
                for f in t.get("feeds", [])
            ],
            sitemaps=[
                SitemapSource(s["url"], s["path_prefix"], s.get("name", ""))
                for s in t.get("sitemaps", [])
            ],
            hn_keywords=t.get("hn_keywords", []),
            synthesize=t.get("synthesize", True),
        )
        for t in raw["topics"]
    ]
    return Config(model=raw["llm"]["model"], topics=topics)
