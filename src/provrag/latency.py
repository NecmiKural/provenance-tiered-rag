"""Timing the index where it runs: loading it, and the retrieval query answering uses.

The times include the network between this machine and the database, which is the point when
comparing a local container with a managed instance in a region.
"""

from __future__ import annotations

import time
from typing import Any

import psycopg

from provrag import cli, db, evalset, ingest, retrieve
from provrag.embed import Embedder
from provrag.evaluate import METHOD, K, quantile
from provrag.results import stamp


def measure(
    conn: psycopg.Connection, embed: Embedder, label: str, repeats: int = 5
) -> dict[str, Any]:
    chunks = cli.corpus_chunks()
    start = time.perf_counter()
    db.reset(conn)
    ingest.load(conn, chunks, embed)
    load_seconds = time.perf_counter() - start

    questions = evalset.questions()
    vectors = embed([q["question"] for q in questions])
    times = []
    for _ in range(repeats):
        for q in questions:
            start = time.perf_counter()
            retrieve.search(
                conn, q["question"], vectors[q["question"]], q["as_of"], [], method=METHOD, k=K
            )
            times.append((time.perf_counter() - start) * 1000)

    server = conn.execute("SHOW server_version").fetchone()[0]
    pgvector = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    return {
        **stamp("latency"),
        "label": label,
        "server_version": server,
        "pgvector": pgvector.fetchone()[0],
        "chunks": len(chunks),
        "load_seconds": round(load_seconds, 2),
        "method": METHOD,
        "k": K,
        "queries": len(times),
        "query_p50_ms": round(quantile(times, 0.5), 2),
        "query_p95_ms": round(quantile(times, 0.95), 2),
    }
