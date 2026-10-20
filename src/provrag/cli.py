"""provrag: build and index the corpus, and measure retrieval."""

from __future__ import annotations

import argparse
import hashlib
import tomllib
from pathlib import Path

from provrag import (
    db,
    embed,
    guidance,
    ingest,
    legislation,
    results,
    retrieval_eval,
)

SOURCES = Path("sources.toml")


def load_sources(path: Path = SOURCES) -> list[dict]:
    return tomllib.loads(path.read_text())["source"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd_fetch(args: argparse.Namespace) -> None:
    for source in load_sources():
        if "act" in source:
            rows = legislation.build(
                source["act"],
                source["sections"],
                source["first_version"],
                source["last_version"],
                args.cache / source["id"],
            )
        elif "pages" in source:
            rows = guidance.build(source["pages"])
        else:
            continue
        path = Path(source["path"])
        legislation.write_jsonl(rows, path)
        print(f"{source['id']}: {len(rows)} rows, sha256 {sha256(path)} -> {path}")


def corpus_chunks() -> list[ingest.Chunk]:
    return [c for s in load_sources() for c in ingest.source_chunks(s)]


def cmd_index(args: argparse.Namespace) -> None:
    chunks = corpus_chunks()
    embedder = embed.embedder(embed.GEMINI, embed.cache_path(embed.GEMINI))
    with db.connect() as conn:
        db.reset(conn)
        ingest.load(conn, chunks, embedder)
        n, hidden = conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE hidden_text) FROM corpus.chunk"
        ).fetchone()
    print(f"indexed {n} chunks ({hidden} with hidden text removed)")


def cmd_retrieval(args: argparse.Namespace) -> None:
    embedder = embed.embedder(embed.GEMINI, embed.cache_path(embed.GEMINI))
    with db.connect() as conn:
        db.reset(conn)
        ingest.load(conn, corpus_chunks(), embedder)
        result = retrieval_eval.run(conn, embedder)
    path = results.write(result, "retrieval")
    for name, m in result["methods"].items():
        print(
            f"{name:12} recall@5 {m['all']['recall_at_5']['rate']:.3f}  mrr {m['all']['mrr']:.3f}"
            f"  exposure@5 {m['exposure_at_5']['rate']:.3f}"
        )
    print(f"wrote {path} (commit {result['commit']})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="provrag", description=__doc__)
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("fetch", help="download the statute versions and write corpus/")
    p.add_argument("--cache", type=Path, default=Path("data/legislation"))
    p.set_defaults(func=cmd_fetch)
    p = sub.add_parser("index", help="recreate the database index from corpus/")
    p.set_defaults(func=cmd_index)
    p = sub.add_parser("retrieval", help="the retrieval ablation; writes results/*.json")
    p.set_defaults(func=cmd_retrieval)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
