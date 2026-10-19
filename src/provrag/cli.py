"""provrag: build the corpus, and later index, ask and evaluate."""

from __future__ import annotations

import argparse
import hashlib
import tomllib
from pathlib import Path

from provrag import legislation

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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="provrag", description=__doc__)
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("fetch", help="download the statute versions and write corpus/")
    p.add_argument("--cache", type=Path, default=Path("data/legislation"))
    p.set_defaults(func=cmd_fetch)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
