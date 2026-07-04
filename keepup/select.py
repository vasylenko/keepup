"""Select layer: Item[] → ≤N per topic, deterministic and source-diverse."""

from keepup.models import Item

CAP = 40  # sized so ~300-char excerpts fit the LLM's 8k-token input budget


def dedupe(items: list[Item]) -> list[Item]:
    """Merge items sharing a canonical URL into one, keeping the echo visible.

    The merged item joins source names ("OpenAI + Hacker News") — that echo is
    the significance signal the ranker is told to reward.
    """
    merged: dict[str, Item] = {}
    for item in sorted(items, key=lambda i: i.published):
        existing = merged.get(item.id)
        if existing is None:
            merged[item.id] = item
            continue
        if item.source not in existing.source.split(" + "):
            existing.source += f" + {item.source}"
        if len(item.excerpt) > len(existing.excerpt):
            existing.excerpt = item.excerpt
    return list(merged.values())


def select(items: list[Item], cap: int = CAP) -> list[Item]:
    """Newest-first round-robin across sources, so one high-volume feed can't
    crowd out the cross-source echoes ranking depends on."""
    groups: dict[str, list[Item]] = {}
    for item in items:
        groups.setdefault(item.source, []).append(item)
    for group in groups.values():
        group.sort(key=lambda i: i.published, reverse=True)

    picked: list[Item] = []
    while len(picked) < cap and any(groups.values()):
        for name in sorted(groups):
            if groups[name] and len(picked) < cap:
                picked.append(groups[name].pop(0))
    picked.sort(key=lambda i: i.published, reverse=True)
    return picked
