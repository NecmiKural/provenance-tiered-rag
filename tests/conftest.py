"""Shared fixtures: one Postgres index for the whole test session, and a scripted
OpenAI-compatible client so answer tests never touch the network."""

import json
import os

import psycopg
import pytest
from openai.types.chat import ChatCompletion

from provrag import cli, db, embed, ingest


@pytest.fixture(scope="session")
def conn():
    """The full index, loaded from the committed vectors. Skipped locally without Postgres;
    in CI a missing database is a failure."""
    try:
        c = db.connect()
    except psycopg.OperationalError:
        if os.environ.get("CI"):
            raise
        pytest.skip("Postgres not reachable; run `docker compose up -d --wait`")
    db.reset(c)
    ingest.load(
        c, cli.corpus_chunks(), embed.embedder(embed.GEMINI, embed.cache_path(embed.GEMINI))
    )
    yield c
    c.close()


def completion(*, content=None, reasoning="thinking", finish="stop", usage=None, tool_calls=None):
    """Build a ChatCompletion the way an OpenAI-compatible provider returns it."""
    calls = [
        {
            "id": f"call_{i}",
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)},
        }
        for i, (name, args) in enumerate(tool_calls or [])
    ]
    message = {"role": "assistant", "content": content, "reasoning_content": reasoning}
    if calls:
        message["tool_calls"] = calls
    return ChatCompletion.model_validate(
        {
            "id": "resp",
            "object": "chat.completion",
            "created": 0,
            "model": "fake",
            "choices": [{"index": 0, "finish_reason": finish, "message": message}],
            "usage": usage
            or {
                "prompt_tokens": 1000,
                "completion_tokens": 100,
                "total_tokens": 1100,
                "prompt_cache_hit_tokens": 800,
                "prompt_cache_miss_tokens": 200,
            },
        }
    )


class FakeClient:
    """Returns scripted completions in order and records every request it receives."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        if not self.script:
            raise AssertionError("the fake model was called more times than scripted")
        return self.script.pop(0)
