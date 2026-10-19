"""Embeddings through an OpenAI-compatible endpoint, with a committed cache.

Every vector the repository needs is in the cache file, keyed by the sha256 of the embedded
text, so indexing and CI run without a key or a network. A key is needed only for texts the
cache does not hold yet.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import openai
from openai import OpenAI

Embedder = Callable[[list[str]], dict[str, list[float]]]


@dataclass(frozen=True)
class EmbeddingSpec:
    name: str
    base_url: str
    key_env: str
    dims: int
    batch: int  # texts per request; the free tier counts each text as one request
    per_minute: int


GEMINI = EmbeddingSpec(
    "gemini-embedding-2",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
    "GEMINI_API_KEY",
    768,
    90,
    100,
)


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def cache_path(spec: EmbeddingSpec, root: Path = Path("corpus/embeddings")) -> Path:
    return root / f"{spec.name}-{spec.dims}.jsonl"


def read_cache(path: Path) -> dict[str, list[float]]:
    if not path.exists():
        return {}
    rows = (json.loads(line) for line in path.read_text().splitlines())
    return {r["sha256"]: r["vector"] for r in rows}


def write_cache(cache: dict[str, list[float]], path: Path) -> None:
    """One line per text, sorted, six decimals: small diffs and a stable file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = (
        json.dumps({"sha256": k, "vector": [round(v, 6) for v in cache[k]]}) for k in sorted(cache)
    )
    path.write_text("\n".join(lines) + "\n")


class MissingEmbeddings(LookupError):
    pass


def embedder(spec: EmbeddingSpec, path: Path) -> Embedder:
    cache = read_cache(path)

    def embed(texts: list[str]) -> dict[str, list[float]]:
        todo = sorted({t for t in texts if text_key(t) not in cache})
        if not todo:
            return {t: cache[text_key(t)] for t in texts}
        if not os.environ.get(spec.key_env):
            raise MissingEmbeddings(
                f"{len(todo)} texts have no committed vector; set {spec.key_env} to embed them"
            )
        client = OpenAI(base_url=spec.base_url, api_key=os.environ.get(spec.key_env), timeout=60)
        for start in range(0, len(todo), spec.batch):
            batch = todo[start : start + spec.batch]
            while True:
                try:
                    response = client.embeddings.create(
                        model=spec.name, input=batch, dimensions=spec.dims
                    )
                    break
                except openai.RateLimitError:
                    time.sleep(62)  # free tier: one minute window
            cache.update(
                {text_key(t): d.embedding for t, d in zip(batch, response.data, strict=True)}
            )
            write_cache(cache, path)
            if start + spec.batch < len(todo):
                time.sleep(60 * len(batch) / spec.per_minute + 2)
        return {t: cache[text_key(t)] for t in texts}

    return embed


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"
