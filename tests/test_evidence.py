"""The evidence viewer's files say only what the committed results files say, quote the corpus
verbatim, and carry no keys; the viewer never parses recorded text as HTML.

The files are rebuilt from local cassettes (`uv run provrag evidence`), so these checks read the
committed files against results/*.json and the corpus rather than replaying."""

import json
import re
from pathlib import Path

import pytest

from provrag import cli, evalset, evaluate
from provrag.packs import PACKS

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence"
MAX_BYTES = 600_000
DASHES = (chr(0x2013), chr(0x2014))
packs = pytest.mark.parametrize("pack", sorted(PACKS))


def doc(pack):
    return json.loads((EVIDENCE / f"{pack}.json").read_text())


def strings(value, path=()):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, (*path, key))
    elif isinstance(value, list):
        for item in value:
            yield from strings(item, path)


@packs
def test_every_case_matches_its_recorded_rows(pack):
    d = doc(pack)
    for set_, run in d["runs"].items():
        result = json.loads((ROOT / run["file"]).read_text())
        assert result["generated_at"] == run["recorded_at"]
        cases = [c for c in d["cases"] if c["set"] == set_]
        assert len(cases) == result["cases"]
        for case in cases:
            rows = [next(r for r in rn if r["id"] == case["id"]) for rn in result["runs"]]
            first = rows[0]
            final = case["answer"]
            cited = sorted({i for claim in final["claims"] for i in claim["cites"]})
            assert final["refused"] == first["refused"], case["id"]
            assert case["refused_by"] == first["refused_by"], case["id"]
            assert cited == first["cited"], case["id"]
            assert len(case["attempts"]) == first["attempts"], case["id"]
            assert (case["payload"], case["goal"]) == (first["payload"], first["goal"])
            assert [r["correct"] for r in case["repeats"]] == [r["correct"] for r in rows]
            if case["payload"]:
                hit = evaluate.paired_hit(result["runs"], pack)
                assert [r["attack_final"] for r in case["repeats"]] == [
                    hit(n, row, "final") for n, row in enumerate(rows)
                ]


@packs
def test_questions_are_the_eval_set(pack):
    d = doc(pack)
    asked = {q["id"]: q for held in (False, True) for q in evalset.questions(held, pack)}
    assert d["questions"].keys() == asked.keys()
    for qid, q in d["questions"].items():
        for key in ("question", "as_of", "expect", "gold", "kind"):
            assert q[key] == asked[qid][key], (qid, key)


@packs
def test_passages_are_the_corpus_verbatim(pack):
    d = doc(pack)
    chunks = {c.id: c for c in cli.corpus_chunks()}
    shown = {i for c in d["cases"] for i in c["context"]}
    cited = {i for c in d["cases"] for claim in c["answer"]["claims"] for i in claim["cites"]}
    assert shown == d["passages"].keys() and cited <= shown
    for i, p in d["passages"].items():
        chunk = chunks[i]
        assert (p["body"], p["valid_from"], p["valid_to"]) == (
            chunk.body,
            chunk.valid_from,
            chunk.valid_to,
        )
        assert p["source"] in d["sources"]


@packs
def test_files_are_small_dash_free_and_hold_no_keys(pack):
    path = EVIDENCE / f"{pack}.json"
    assert path.stat().st_size < MAX_BYTES
    text = path.read_text()
    assert not re.search(r"sk-[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{20,}|Bearer |Authorization", text)
    # Statute and guidance text is quoted as published; everything else is the project's own.
    own = [
        (path, s)
        for path, s in strings(doc(pack))
        if path[:1] != ("passages",) and any(d in s for d in DASHES)
    ]
    assert not own, own[:3]


def test_the_viewer_never_parses_text_as_html():
    code = (EVIDENCE / "app.js").read_text()
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert sink not in code, sink


def test_the_licence_notes_name_every_source():
    notes = (EVIDENCE / "LICENSE.md").read_text()
    for source in cli.load_sources():
        assert source["licence"] in notes, source["id"]
