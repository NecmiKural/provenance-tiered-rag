"""Retrieval ablation: full text, vectors and their fusion, and the fusion without the date
filter. No chat model is involved, only the embedding model for the questions.

A question counts as found at k when a gold passage in force on its date is among the top k.
Exposure asks the attacker's question: with one payload note visible among the ordinary
notes, does it reach the top k for the question it targets? Only the development questions
are used; the held-back set is not run until the end.
"""

from __future__ import annotations

import re
from statistics import mean
from typing import Any

import psycopg

from provrag import cli, evalset, retrieve
from provrag.embed import GEMINI, Embedder
from provrag.ingest import Chunk
from provrag.results import rate, stamp

K = 5
DEPTH = 10
VARIANTS = {"full_text": ("full_text", True), "vector": ("vector", True), "rrf": ("rrf", True)}
VARIANTS["rrf_undated"] = ("rrf", False)
_WORD = re.compile(r"[a-z]{3,}")
_STOP = set(
    "the and for are you your can what how does when with that this have from not any".split()
)


def words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def overlap(question: str, passages: list[Chunk]) -> float:
    """Highest Jaccard word overlap between the question and a gold passage: a high value means
    the question borrows the passage's wording and full-text search has an easy job."""
    q = words(question)
    return max(len(q & (p := words(c.heading + " " + c.body))) / len(q | p) for c in passages)


def gold_rank(hits: list[retrieve.Hit], question: dict, chunks: dict[str, Chunk]) -> int | None:
    for rank, hit in enumerate(hits, 1):
        chunk = chunks[hit.id]
        if evalset.locator(chunk) in question["gold"] and evalset.valid_on(
            chunk, question["as_of"]
        ):
            return rank
    return None


def summarise(ranks: dict[str, int | None], ids: list[str]) -> dict[str, Any]:
    found = [ranks[i] for i in ids]
    return {
        "recall_at_1": rate(sum(r == 1 for r in found), len(found)),
        f"recall_at_{K}": rate(sum(r is not None and r <= K for r in found), len(found)),
        "mrr": round(mean(1 / r if r else 0.0 for r in found), 4),
    }


def run(conn: psycopg.Connection, embed: Embedder) -> dict[str, Any]:
    chunks = {c.id: c for c in cli.corpus_chunks()}
    questions = evalset.questions()
    answerable = [q for q in questions if q["kind"] == "answerable"]
    by_id = {q["id"]: q for q in questions}
    payloads = [p for p in evalset.payloads() if p["target"] in by_id]
    planted = {p["note"] for p in evalset.payloads()}
    benign = sorted(c.section for c in chunks.values() if c.source == retrieve.NOTES_SOURCE)
    benign = [n for n in benign if n not in planted]
    vectors = embed([q["question"] for q in questions])

    def hits(q: dict, notes: list[str], method: str, dated: bool, k: int) -> list[retrieve.Hit]:
        vector = vectors[q["question"]]
        return retrieve.search(
            conn, q["question"], vector, q["as_of"], notes, method=method, k=k, dated=dated
        )

    current = max(q["as_of"] for q in answerable)
    groups = {
        "all": [q["id"] for q in answerable],
        "statute_origin": [q["id"] for q in answerable if q["origin"] == "statute"],
        "guidance_origin": [q["id"] for q in answerable if q["origin"] == "guidance"],
        "historical": [q["id"] for q in answerable if q["as_of"] < current],
    }
    methods: dict[str, Any] = {}
    for name, (method, dated) in VARIANTS.items():
        ranks = {
            q["id"]: gold_rank(hits(q, benign, method, dated, DEPTH), q, chunks) for q in answerable
        }
        exposure = {}
        for p in payloads:
            found = hits(by_id[p["target"]], benign + [p["note"]], method, dated, K)
            exposure[p["note"]] = next(
                (i for i, h in enumerate(found, 1) if chunks[h.id].section == p["note"]), None
            )
        methods[name] = {
            **{g: summarise(ranks, ids) for g, ids in groups.items()},
            f"exposure_at_{K}": rate(sum(r is not None for r in exposure.values()), len(exposure)),
            "ranks": ranks,
            "exposure": exposure,
        }

    gold_passages = {
        q["id"]: [
            c
            for c in chunks.values()
            if evalset.locator(c) in q["gold"] and evalset.valid_on(c, q["as_of"])
        ]
        for q in answerable
    }
    overlaps = {
        q["id"]: round(overlap(q["question"], gold_passages[q["id"]]), 4) for q in answerable
    }
    return {
        **stamp("retrieval"),
        "embedding_model": GEMINI.name,
        "dims": GEMINI.dims,
        "k": K,
        "depth": DEPTH,
        "groups": {g: len(ids) for g, ids in groups.items()},
        "payloads": len(payloads),
        "methods": methods,
        "lexical_overlap": {
            g: round(mean(overlaps[i] for i in ids), 4) for g, ids in groups.items() if ids
        },
    }
