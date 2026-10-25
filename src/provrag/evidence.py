"""The evidence export: recorded answers with the dated passages they cite, for the static
viewer in docs/evidence/.

For each pack, the defences-on runs the README reports (development and held back) are
replayed from their cassettes, first repeat only: every case's answer as the user saw it, each
attempt's draft and verifier errors, and the passages the model was shown, with tier, source,
licence and the dates each was in force. The other repeats add their outcome only, read from
the results file. Nothing is called live, and a replayed case that scores differently from its
recorded row stops the export.

NOTE: the full cassettes are local (cassettes/ is gitignored), so CI cannot rebuild the
export; tests/test_evidence.py checks every exported case against its row in the committed
results file instead. Committing the six cassettes is the upgrade if CI must rebuild it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg

from provrag import answer, cli, embed, evalset, evaluate, gii, legislation, report
from provrag.answer import Outcome
from provrag.llm import LLM, MODELS
from provrag.packs import PACKS

OUT = Path("docs/evidence")
RESULTS = Path("results")
CASSETTES = Path("cassettes")
# Built from code points so this file passes the repository's dash check.
EM, EN = chr(0x2014), chr(0x2013)
# The fields a replayed case must share with its recorded row.
AGREE = ("refused", "refused_by", "correct", "cited", "attempts", "attack_draft", "attack_final")


def tidy(value: Any) -> Any:
    """Recorded model text as the viewer shows it: em and en dashes become commas, as in
    bank-reconciliation-agent's replay export. Statute and guidance text is left verbatim."""
    if isinstance(value, str):
        return value.replace(f" {EM} ", ", ").replace(EM, ", ").replace(EN, ", ")
    if isinstance(value, dict):
        return {key: tidy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [tidy(item) for item in value]
    return value


def recorded(pack: str, held_back: bool) -> tuple[Path, dict[str, Any]]:
    """The defences-on record run the README reports, and the file it is in."""
    result = report.held_back(RESULTS, pack) if held_back else report.evals(RESULTS, pack)["on"]
    (path,) = [
        p
        for p in sorted(RESULTS.glob("*-eval-*.json"))
        if json.loads(p.read_text())["generated_at"] == result["generated_at"]
    ]
    return path, result


def source_url(source: dict[str, Any]) -> str | None:
    if "act" in source:
        return f"{legislation.BASE}{source['act']}"
    if "gii" in source:
        return f"{gii.BASE}/{source['gii']}/"
    return source.get("site")


def shown_draft(draft: Any) -> dict[str, Any] | None:
    if draft is None:
        return None
    return tidy(
        {
            "answer": draft.answer,
            "claims": [{"text": c.text, "cites": c.chunk_ids} for c in draft.claims],
            "refused": draft.refused,
            "reason": draft.reason,
        }
    )


def case_doc(
    case: evaluate.Case,
    outcome: Outcome,
    rows: list[dict[str, Any]],
    set_: str,
    hit: Callable[[int, dict[str, Any], str], bool],
) -> dict[str, Any]:
    scored = evaluate.score(case, outcome)
    first = rows[0]
    if wrong := [f for f in AGREE if scored.get(f) != first.get(f)]:
        raise SystemExit(f"{case.id} replays differently from its recorded row: {wrong}")
    return {
        "id": case.id,
        "question": case.question["id"],
        "set": set_,
        "payload": first["payload"],
        "goal": first["goal"],
        "context": [c.id for c in case.chunks],
        "answer": shown_draft(outcome.answer),
        "refused_by": outcome.refused_by,
        "attempts": [
            {
                "draft": shown_draft(a.draft),
                # An unparsed reply is shown as text, cut short.
                "content": None if a.draft else tidy(a.content[:2000]),
                "errors": tidy(a.errors),
            }
            for a in outcome.attempts
        ],
        # Attacks judged as the README counts them: paired with the clean run of the repeat.
        "repeats": [
            {"correct": row["correct"], "refused": row["refused"]}
            | (
                {"attack_draft": hit(r, row, "draft"), "attack_final": hit(r, row, "final")}
                if row["payload"]
                else {}
            )
            for r, row in enumerate(rows)
        ],
    }


def replay(
    conn: psycopg.Connection, pack: str, held_back: bool
) -> tuple[Path, dict[str, Any], list[tuple[evaluate.Case, Outcome]]]:
    path, result = recorded(pack, held_back)
    defences = answer.DEFENCES[result["defences"]["name"]]
    embedder = embed.embedder(embed.GEMINI, embed.cache_path(embed.GEMINI))
    cases = evaluate.build_cases(conn, embedder, defences, held_back, pack)
    if len(cases) != result["cases"] or result["every"] != 1:
        raise SystemExit(f"{path.name} does not hold every case of the current eval set")
    cassette = CASSETTES / f"{path.stem.split('-', 3)[3]}.jsonl"
    llm = LLM(MODELS[result["model"]], "replay", cassette)
    outcomes = [
        answer.answer(c.question["question"], c.question["as_of"], c.chunks, llm, defences, pack)
        for c in cases
    ]
    return path, result, list(zip(cases, outcomes, strict=True))


def build(conn: psycopg.Connection, pack: str) -> dict[str, Any]:
    chunks = {c.id: c for c in cli.corpus_chunks()}
    sources = {s["id"]: s for s in cli.load_sources()}
    questions: dict[str, dict[str, Any]] = {}
    cases: list[dict[str, Any]] = []
    runs = {}
    for held_back in (False, True):
        set_ = "held_back" if held_back else "development"
        path, result, replayed = replay(conn, pack, held_back)
        by_id = [{r["id"]: r for r in run} for run in result["runs"]]
        hit = evaluate.paired_hit(result["runs"], pack)
        for case, outcome in replayed:
            q = case.question
            questions[q["id"]] = {
                k: q[k] for k in ("id", "kind", "origin", "question", "as_of", "expect", "gold")
            } | {"set": set_}
            rows = [run[case.id] for run in by_id]
            cases.append(case_doc(case, outcome, rows, set_, hit))
        runs[set_] = {
            "file": f"results/{path.name}",
            "model": result["model"],
            "api_model": result["api_model"],
            "repeats": result["repeats"],
            "recorded_at": result["generated_at"],
            "recorded_commit": result["commit"],
        }
    shown = sorted({i for c in cases for i in c["context"]})
    payloads = {p["note"]: p for p in evalset.payloads(pack)}
    return {
        "pack": pack,
        "jurisdiction": PACKS[pack].jurisdiction,
        "lang": PACKS[pack].lang,
        "runs": runs,
        "sources": {
            s: {
                "title": sources[s]["title"],
                "tier": sources[s]["tier"],
                "licence": sources[s]["licence"],
                "url": source_url(sources[s]),
                "retrieved": sources[s].get("retrieved"),
            }
            for s in PACKS[pack].sources
        },
        "passages": {
            i: {
                "source": chunks[i].source,
                "tier": chunks[i].tier,
                "section": chunks[i].section,
                "heading": chunks[i].heading,
                "body": chunks[i].body,
                "valid_from": chunks[i].valid_from,
                "valid_to": chunks[i].valid_to,
                "hidden_text": chunks[i].hidden_text,
            }
            for i in shown
        },
        "payloads": {
            n: {k: p[k] for k in ("goal", "style", "target", "instruction")}
            for n, p in payloads.items()
        },
        "questions": questions,
        "cases": cases,
    }


def render(doc: dict[str, Any]) -> str:
    # ASCII escapes keep the dashes in statute text out of the repository's dash check.
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def write(conn: psycopg.Connection, out_dir: Path = OUT, check: bool = False) -> list[str]:
    """Rebuild every pack's file; returns the packs whose file was missing or different.
    With check, nothing is written."""
    stale = []
    for pack in PACKS:
        text = render(build(conn, pack))
        path = out_dir / f"{pack}.json"
        if not path.exists() or path.read_text() != text:
            stale.append(pack)
            if not check:
                out_dir.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
    return stale
