"""Shared GitHub Models client — OpenAI-compatible, so another backend is a
base-URL/key change. Returns None when no token is set, letting every caller
degrade gracefully instead of failing the run.
"""

import os

from openai import OpenAI

BASE_URL = "https://models.github.ai/inference"


def client() -> OpenAI | None:
    token = os.environ.get("GITHUB_TOKEN")
    return OpenAI(base_url=BASE_URL, api_key=token) if token else None
