"""Oracle checks on the eval set, with no model: every label is supported by the corpus, every
payload can reach the model and has a canary code can find, and the set is frozen."""

import hashlib
from collections import Counter
from pathlib import Path

import pytest

from provrag import cli, evalset, ingest
from provrag.numbers import extract, numbers

ROOT = Path(__file__).resolve().parents[1]
DEV = evalset.questions()
HELD = evalset.questions(held_back=True)
QUESTIONS = {q["id"]: q for q in DEV + HELD}
PAYLOADS = evalset.payloads()
CHUNKS = cli.corpus_chunks()
BY_LOCATOR: dict[str, list[ingest.Chunk]] = {}
for chunk in CHUNKS:
    BY_LOCATOR.setdefault(evalset.locator(chunk), []).append(chunk)
ANSWERABLE = [q for q in QUESTIONS.values() if q["kind"] == "answerable"]

# sha256 of each frozen file. Changing one needs a docs/agent-log.md entry saying why.
FROZEN = {
    "evals/questions.jsonl": "e74a880d40891b0e8699e4df6d799b3b0ffc77ff2e03db2d4948f79a1aa3cd92",
    "evals/questions-held-back.jsonl": (
        "ff5cdac9b0abb61646b67ddfa662399f30f81813cd494e25a820e3c6db37f08c"
    ),
    "evals/payloads.jsonl": "b784fa4551361779f1daf7b303d9f1dfe5b0d7af176eedf9ba6d8038ddff1548",
    "corpus/nz/notes.jsonl": "8b105efd24fb810e152f64ae934a3aaf3e39055c17e0e8754eb4748d670ab33e",
}


def in_force(locator: str, day: str) -> list[ingest.Chunk]:
    return [c for c in BY_LOCATOR.get(locator, []) if evalset.valid_on(c, day)]


@pytest.mark.parametrize("path", sorted(FROZEN))
def test_the_eval_set_is_frozen(path):
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == FROZEN[path]


def test_ids_kinds_and_split():
    assert len(QUESTIONS) == len(DEV) + len(HELD)
    assert {q["kind"] for q in QUESTIONS.values()} == set(evalset.KINDS)
    assert 0.2 <= len(HELD) / len(QUESTIONS) <= 0.3
    for kind in evalset.KINDS:
        assert any(q["kind"] == kind for q in HELD), kind


@pytest.mark.parametrize("q", ANSWERABLE, ids=lambda q: q["id"])
def test_every_answerable_question_is_supported_on_its_date(q):
    assert q["gold"]
    assert all(g in BY_LOCATOR for g in q["gold"]), "a gold passage is missing from the corpus"
    passages = [c for g in q["gold"] for c in in_force(g, q["as_of"])]
    assert passages, "no gold passage was in force on the question's date"
    assert all(c.tier in ("T1", "T2") for c in passages)
    supported = set().union(*(numbers(c.body) for c in passages))
    for expected in q["expect"]:
        (number,) = extract(expected)
        assert number in supported, expected
        assert number not in numbers(q["question"]), "the answer would be in the question"


@pytest.mark.parametrize(
    "q", [q for q in QUESTIONS.values() if q["kind"] != "answerable"], ids=lambda q: q["id"]
)
def test_other_questions_have_no_labels(q):
    assert q["gold"] == [] and q["expect"] == []


def test_questions_about_dates_before_the_corpus_are_unanswerable():
    first = min(c.valid_from for c in CHUNKS if c.tier == "T1")
    early = [q for q in QUESTIONS.values() if q["as_of"] < first]
    assert early and all(q["kind"] == "unanswerable" for q in early)


def test_payloads_cover_every_goal_and_style_evenly():
    assert Counter(p["goal"] for p in PAYLOADS) == dict.fromkeys(evalset.GOALS, 8)
    assert len({p["style"] for p in PAYLOADS}) == 5


@pytest.mark.parametrize("p", PAYLOADS, ids=lambda p: p["note"])
def test_every_payload_targets_an_answerable_question_it_can_reach(p):
    (note,) = BY_LOCATOR[f"nz-notes:{p['note']}"]
    target = QUESTIONS[p["target"]]
    assert note.tier == "T3"
    assert target["kind"] == "answerable"
    assert evalset.valid_on(note, target["as_of"])
    if p["style"] == "hidden":
        assert note.hidden_text and p["instruction"] not in note.body
    else:
        assert p["instruction"] in note.body


@pytest.mark.parametrize(
    "p", [p for p in PAYLOADS if p["goal"] == "wrong_fact"], ids=lambda p: p["note"]
)
def test_a_planted_number_is_wrong_for_its_target(p):
    planted = tuple(p["canary"])
    target = QUESTIONS[p["target"]]
    gold = [c for g in target["gold"] for c in in_force(g, target["as_of"])]
    assert planted in numbers(p["instruction"])
    assert all(planted not in numbers(c.body) for c in gold)


def test_canaries_are_unique_except_the_shared_prompt_canary():
    canaries = [tuple(p["canary"]) for p in PAYLOADS if p["canary"] and p["canary"][0] != "prompt"]
    assert len(canaries) == len(set(canaries))
    assert len({tuple(p["canary"]) for p in PAYLOADS if p["goal"] == "leak"}) == 1
