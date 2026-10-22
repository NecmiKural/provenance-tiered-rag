"""Hybrid retrieval in one query: full text and vectors, fused by reciprocal rank, filtered to
the passages in force on the date asked about.

Ties go to the higher tier (statute, then guidance, then notes); there is no tier weight to
tune. Which notes are visible is a parameter, so an evaluation can show the model one planted
payload at a time.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from provrag import db
from provrag.embed import vector_literal

RRF_K = 60
METHODS = ("full_text", "vector", "rrf")
NOTES = {"NZ": "nz-notes", "DE": "de-notes"}  # the untrusted-notes source of each jurisdiction
NOTES_SOURCE = NOTES["NZ"]
TEXT_SEARCH = {"NZ": "english", "DE": "german"}  # stemming for each jurisdiction's language

# Full-text matching is an OR over the question's stemmed lexemes, quoted so no word can be
# read as query syntax: a question rarely shares every word with the passage that answers it.
SEARCH_SQL = """
WITH query AS (
    SELECT to_tsquery('simple', string_agg(quote_literal(lexeme), ' | ')) AS tsq
    FROM unnest(tsvector_to_array(to_tsvector(%(text_search)s::regconfig, %(q)s))) AS lexeme
),
pool AS (
    SELECT id, tier,
           coalesce(ts_rank_cd(search, (SELECT tsq FROM query)), 0) AS text_score,
           1 - (embedding <=> %(qv)s::vector) AS cosine
    FROM corpus.chunk
    WHERE jurisdiction = %(jurisdiction)s
      AND (NOT %(dated)s OR valid @> %(day)s::date)
      AND (source <> %(notes_source)s OR section_key = ANY(%(notes)s))
),
ranked AS (
    SELECT id, tier, text_score, cosine,
           CASE WHEN text_score > 0 THEN rank() OVER (ORDER BY text_score DESC) END AS text_rank,
           rank() OVER (ORDER BY cosine DESC) AS vector_rank
    FROM pool
)
SELECT id, tier,
       CASE %(method)s
           WHEN 'full_text' THEN text_score
           WHEN 'vector' THEN cosine
           ELSE coalesce(1.0 / (%(rrf_k)s + text_rank), 0) + 1.0 / (%(rrf_k)s + vector_rank)
       END AS score
FROM ranked
WHERE %(method)s <> 'full_text' OR text_score > 0
ORDER BY score DESC, tier, id
LIMIT %(k)s
"""


@dataclass(frozen=True)
class Hit:
    id: str
    tier: str
    score: float


def search(
    conn: psycopg.Connection,
    question: str,
    vector: list[float],
    day: str,
    notes: list[str],
    *,
    method: str = "rrf",
    k: int = 5,
    dated: bool = True,
    jurisdiction: str = "NZ",
) -> list[Hit]:
    """The top k passages for a question as at `day`, read as the reader role."""
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    params = {
        "q": question,
        "qv": vector_literal(vector),
        "day": day,
        "dated": dated,
        "notes": notes,
        "notes_source": NOTES[jurisdiction],
        "text_search": TEXT_SEARCH[jurisdiction],
        "jurisdiction": jurisdiction,
        "method": method,
        "rrf_k": RRF_K,
        "k": k,
    }
    with db.as_role(conn, "provrag_reader"):
        rows = conn.execute(SEARCH_SQL, params).fetchall()
    return [Hit(*row) for row in rows]
