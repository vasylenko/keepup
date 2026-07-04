"""Synthesize layer: selected items → ranked stories, one LLM call per topic.

Bound to GitHub Models through the OpenAI-compatible API; provider and model
are config, so another backend is a base-URL/key change.
"""

import json
import os
from pathlib import Path

from openai import OpenAI

from keepup.models import Item, Story

BASE_URL = "https://models.github.ai/inference"
_PROMPT = Path(__file__).parent / "prompts" / "synthesize.md"
_EXCERPT_CAP = 300  # keeps 40 items inside the free tier's 8k-token input cap
_MAX_OUTPUT = 3000  # free tier caps completions at 4k tokens


def _payload(items: list[Item]) -> str:
    return "\n".join(
        f"{i.id} | {i.source} | {i.published:%Y-%m-%d} | {i.title} — {i.excerpt[:_EXCERPT_CAP]}"
        for i in items
    )


def synthesize(topic_name: str, items: list[Item], model: str) -> list[Story] | None:
    """Cluster, rank, and write stories for one topic.

    Returns None on any failure (no token, API error, bad JSON) so the caller
    renders that topic links-only instead of failing the run. Anti-slop:
    stories may only reference fetched item IDs — anything else is dropped.
    """
    if not items:
        return []
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    try:
        client = OpenAI(base_url=BASE_URL, api_key=token)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _PROMPT.read_text().replace("{topic}", topic_name)},
                {"role": "user", "content": _payload(items)},
            ],
            response_format={"type": "json_object"},
            max_tokens=_MAX_OUTPUT,
            temperature=0.2,
        )
        data = json.loads(response.choices[0].message.content)
        known = {i.id for i in items}
        stories = []
        for raw in data.get("stories", []):
            ids = [i for i in raw.get("item_ids", []) if i in known]
            if ids and raw.get("headline") and raw.get("why_it_matters"):
                stories.append(Story(raw["headline"], raw["why_it_matters"], ids))
        return stories
    except Exception as exc:
        print(f"  synthesis failed for {topic_name}: {exc}")
        return None
