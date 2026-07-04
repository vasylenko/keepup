"""Loads config/topics.yml into typed config objects."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SitemapSource:
    url: str
    path_prefix: str


@dataclass
class Topic:
    name: str
    feeds: list[str] = field(default_factory=list)
    sitemaps: list[SitemapSource] = field(default_factory=list)
    hn_keywords: list[str] = field(default_factory=list)


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
            feeds=[f["url"] for f in t.get("feeds", [])],
            sitemaps=[SitemapSource(s["url"], s["path_prefix"]) for s in t.get("sitemaps", [])],
            hn_keywords=t.get("hn_keywords", []),
        )
        for t in raw["topics"]
    ]
    return Config(model=raw["llm"]["model"], topics=topics)
