"""provrag: build the corpus and index it; asking and evaluation follow."""

from __future__ import annotations

import argparse
import hashlib
import tomllib
from pathlib import Path

from provrag import db, embed, ingest, legislation

SOURCES = Path("sources.toml")


def load_sources(path: Path = SOURCES) -> list[dict]:
    return tomllib.loads(path.read_text())["source"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd_fetch(args: argparse.Namespace) -> None:
    for source in load_sources():
        if "act" not in source:
            continue
        rows = legislation.build(
            source["act"],
            source["sections"],
            source["first_version"],
            source["last_version"],
            args.cache / source["id"],
        )
        path = Path(source["path"])
        legislation.write_jsonl(rows, path)
        print(f"{source['id']}: {len(rows)} rows, sha256 {sha256(path)} -> {path}")


def corpus_chunks() -> list[ingest.Chunk]:
    return [c for s in load_sources() if "act" in s for c in ingest.statute_chunks(s)]


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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="provrag", description=__doc__)
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("fetch", help="download the statute versions and write corpus/")
    p.add_argument("--cache", type=Path, default=Path("data/legislation"))
    p.set_defaults(func=cmd_fetch)
    p = sub.add_parser("index", help="recreate the database index from corpus/")
    p.set_defaults(func=cmd_index)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
