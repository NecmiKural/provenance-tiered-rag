"""provrag: build and index the corpus, measure retrieval, and answer questions."""

from __future__ import annotations

import argparse
import hashlib
import tomllib
from datetime import date
from pathlib import Path

from provrag import (
    answer,
    db,
    embed,
    evaluate,
    guidance,
    ingest,
    legislation,
    report,
    results,
    retrieval_eval,
    retrieve,
)
from provrag.llm import LLM, MODELS

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
        result = retrieval_eval.run(conn, embedder, args.held_back)
    path = results.write(result, "retrieval-held-back" if args.held_back else "retrieval")
    for name, m in result["methods"].items():
        print(
            f"{name:12} recall@5 {m['all']['recall_at_5']['rate']:.3f}  mrr {m['all']['mrr']:.3f}"
            f"  exposure@5 {m['exposure_at_5']['rate']:.3f}"
        )
    print(f"wrote {path} (commit {result['commit']})")


def cmd_ask(args: argparse.Namespace) -> None:
    """Retrieve, answer and verify one question against the index `provrag index` built."""
    chunks = {c.id: c for c in corpus_chunks()}
    notes = sorted({c.section for c in chunks.values() if c.source == retrieve.NOTES_SOURCE})
    embedder = embed.embedder(embed.GEMINI, embed.cache_path(embed.GEMINI))
    vector = embedder([args.question])[args.question]
    with db.connect() as conn:
        hits = retrieve.search(conn, args.question, vector, args.as_of, notes, k=args.k)
    outcome = answer.answer(
        args.question,
        args.as_of,
        [chunks[h.id] for h in hits],
        LLM(MODELS[args.model]),
        answer.DEFENCES[args.defences],
    )
    final = outcome.answer
    if final.refused:
        print(f"Refused ({outcome.refused_by}): {final.reason}")
    else:
        print(final.answer)
        for claim in final.claims:
            print(f"- {claim.text} [{', '.join(claim.chunk_ids)}]")
    print(
        f"({len(outcome.attempts)} model call(s), {'repaired, ' if outcome.repaired else ''}"
        f"${outcome.cost_usd:.4f}, {outcome.latency_ms / 1000:.1f} s)"
    )


def cmd_eval(args: argparse.Namespace) -> None:
    defences = answer.DEFENCES[args.defences]
    parts = ["eval", args.model.replace(":", "_"), defences.name]
    parts += ["held-back"] if args.held_back else []
    parts += [f"every{args.every}"] if args.every > 1 else []
    name = args.name or "-".join([*parts, args.mode])
    cassette = args.cassette or (Path("cassettes") / f"{name}.jsonl")
    embedder = embed.embedder(embed.GEMINI, embed.cache_path(embed.GEMINI))
    with db.connect() as conn:
        db.reset(conn)
        ingest.load(conn, corpus_chunks(), embedder)
        result = evaluate.evaluate(
            conn,
            embedder,
            MODELS[args.model],
            defences,
            args.repeats,
            args.mode,
            None if args.mode == "live" else cassette,
            args.workers,
            args.every,
            args.held_back,
        )
    a = result["aggregate"]
    print(
        f"answerable correct {a['answerable_correct']['rate']:.3f}"
        f"  unanswerable refused {a['unanswerable_refused']['rate']:.3f}"
        f"  attacks final {a['attacks_total']['final']['rate']:.3f}"
        f"  draft {a['attacks_total']['draft']['rate']:.3f}"
        f"  provider errors {a['provider_errors']}"
    )
    if not result["valid"]:
        raise SystemExit("provider errors: not saved; rerun with fewer --workers")
    path = results.write(result, name, args.out, dated=args.name is None)
    print(f"wrote {path} (commit {result['commit']})")


def cmd_report(args: argparse.Namespace) -> None:
    stale = report.sync(Path("README.md"), Path("results"), check=args.check)
    if args.check and stale:
        raise SystemExit("README results are stale: run `uv run provrag report`")
    print("README results " + ("rewritten" if stale else "already in sync"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="provrag", description=__doc__)
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("fetch", help="download the statute versions and write corpus/")
    p.add_argument("--cache", type=Path, default=Path("data/legislation"))
    p.set_defaults(func=cmd_fetch)
    p = sub.add_parser("index", help="recreate the database index from corpus/")
    p.set_defaults(func=cmd_index)
    p = sub.add_parser("retrieval", help="the retrieval ablation; writes results/*.json")
    p.add_argument("--held-back", action="store_true", help="the held-back questions, once")
    p.set_defaults(func=cmd_retrieval)
    p = sub.add_parser("ask", help="answer one question, with citations checked in code")
    p.add_argument("question")
    p.add_argument("--as-of", default=date.today().isoformat(), help="the date asked about")
    p.add_argument("--model", choices=sorted(MODELS), default="deepseek-flash")
    p.add_argument("--defences", choices=sorted(answer.DEFENCES), default="on")
    p.add_argument("--k", type=int, default=retrieval_eval.K)
    p.set_defaults(func=cmd_ask)
    p = sub.add_parser("eval", help="clean and attacked runs, repeated; writes results/*.json")
    p.add_argument("--model", choices=sorted(MODELS), default="deepseek-flash")
    p.add_argument("--defences", choices=sorted(answer.DEFENCES), default="on")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--mode", choices=("live", "record", "replay"), default="record")
    p.add_argument("--cassette", type=Path, default=None)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--every", type=int, default=1, help="every Nth case only, for a slice")
    p.add_argument("--held-back", action="store_true", help="the held-back questions, once")
    p.add_argument("--out", type=Path, default=Path("results"))
    p.add_argument("--name", default=None)
    p.set_defaults(func=cmd_eval)
    p = sub.add_parser("report", help="rewrite the README results block from results/*.json")
    p.add_argument("--check", action="store_true", help="fail if the block is stale")
    p.set_defaults(func=cmd_report)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
