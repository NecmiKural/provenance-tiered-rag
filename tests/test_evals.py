"""Oracle checks on each pack's eval set, with no model: every label is supported by the
corpus, every payload can reach the model and has a canary code can find, and the set is frozen."""

import hashlib
from collections import Counter
from functools import cache
from pathlib import Path

import pytest

from provrag import cli, evalset, ingest
from provrag.numbers import extract, numbers
from provrag.packs import PACKS

ROOT = Path(__file__).resolve().parents[1]
PACK_IDS = ("nz-gst", "de-vat")

# sha256 of each frozen file. Changing one needs a docs/agent-log.md entry saying why.
FROZEN = {
    "evals/questions.jsonl": "e74a880d40891b0e8699e4df6d799b3b0ffc77ff2e03db2d4948f79a1aa3cd92",
    "evals/questions-held-back.jsonl": (
        "ff5cdac9b0abb61646b67ddfa662399f30f81813cd494e25a820e3c6db37f08c"
    ),
    "evals/payloads.jsonl": "b784fa4551361779f1daf7b303d9f1dfe5b0d7af176eedf9ba6d8038ddff1548",
    "corpus/nz/notes.jsonl": "8b105efd24fb810e152f64ae934a3aaf3e39055c17e0e8754eb4748d670ab33e",
    "evals/de/questions.jsonl": (
        "29a5befb13a802fb977eb9f798941f4b1042b7fb8394e7de9f015f0910ffd724"
    ),
    "evals/de/questions-held-back.jsonl": (
        "37b14e14ea71ba1ea21b7090515a87b288922c4876ea93e828c0cca58acc0b1a"
    ),
    "evals/de/payloads.jsonl": ("355ebfb419c7561bd1f607eb007e691f9fce696723b260e543e12fe19841a8fa"),
    "corpus/de/notes.jsonl": ("59f3f3ac074a7db9fb3463a2806c8cfa6d1877790b2bf05c334afdc7e88ac71e"),
}
PAYLOADS_PER_GOAL = {"nz-gst": 8, "de-vat": 4}
# Planted figures that some passage in force also states; scoring pairs those attacks with the
# clean run (see the agent log, 2026-10-22).
KNOWN_COLLISIONS = {"nz-gst": {"P04", "P07"}, "de-vat": {"DP04"}}


@cache
def eval_set(j: str) -> dict:
    questions = evalset.questions(pack=j) + evalset.questions(True, pack=j)
    chunks = [c for c in cli.corpus_chunks() if c.source in PACKS[j].sources]
    by_locator: dict[str, list[ingest.Chunk]] = {}
    for chunk in chunks:
        by_locator.setdefault(evalset.locator(chunk), []).append(chunk)
    return {
        "dev": evalset.questions(pack=j),
        "held": evalset.questions(True, pack=j),
        "questions": {q["id"]: q for q in questions},
        "payloads": evalset.payloads(j),
        "chunks": chunks,
        "by_locator": by_locator,
        "lang": PACKS[j].lang,
    }


def in_force(j: str, locator: str, day: str) -> list[ingest.Chunk]:
    return [c for c in eval_set(j)["by_locator"].get(locator, []) if evalset.valid_on(c, day)]


def each(kind_filter, source="questions"):
    """(pack, item) pairs for parametrising per question or payload."""
    pairs = []
    for j in PACK_IDS:
        items = eval_set(j)[source]
        items = items.values() if isinstance(items, dict) else items
        pairs += [(j, item) for item in items if kind_filter(item)]
    return pairs


def name(pair) -> str:
    j, item = pair
    return f"{j}-{item.get('id', item.get('note'))}"


@pytest.mark.parametrize("path", sorted(FROZEN))
def test_the_eval_set_is_frozen(path):
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == FROZEN[path]


@pytest.mark.parametrize("j", PACK_IDS)
def test_ids_kinds_and_split(j):
    s = eval_set(j)
    assert len(s["questions"]) == len(s["dev"]) + len(s["held"])
    assert {q["kind"] for q in s["questions"].values()} == set(evalset.KINDS)
    assert 0.2 <= len(s["held"]) / len(s["questions"]) <= 0.3
    for kind in evalset.KINDS:
        assert any(q["kind"] == kind for q in s["held"]), kind


@pytest.mark.parametrize("pair", each(lambda q: q["kind"] == "answerable"), ids=name)
def test_every_answerable_question_is_supported_on_its_date(pair):
    j, q = pair
    lang = eval_set(j)["lang"]
    assert q["gold"]
    assert all(g in eval_set(j)["by_locator"] for g in q["gold"]), "a gold passage is missing"
    passages = [c for g in q["gold"] for c in in_force(j, g, q["as_of"])]
    assert passages, "no gold passage was in force on the question's date"
    assert all(c.tier in ("T1", "T2") for c in passages)
    supported = set().union(*(numbers(c.body, lang) for c in passages))
    for expected in q["expect"]:
        (number,) = extract(expected, lang)
        assert number in supported, expected
        assert number not in numbers(q["question"], lang), "the answer would be in the question"


@pytest.mark.parametrize("pair", each(lambda q: q["kind"] != "answerable"), ids=name)
def test_other_questions_have_no_labels(pair):
    _, q = pair
    assert q["gold"] == [] and q["expect"] == []


@pytest.mark.parametrize("j", PACK_IDS)
def test_questions_about_dates_before_the_corpus_are_unanswerable(j):
    first = min(c.valid_from for c in eval_set(j)["chunks"] if c.tier == "T1")
    early = [q for q in eval_set(j)["questions"].values() if q["as_of"] < first]
    assert early and all(q["kind"] == "unanswerable" for q in early)


@pytest.mark.parametrize("j", PACK_IDS)
def test_payloads_cover_every_goal_and_style_evenly(j):
    payloads = eval_set(j)["payloads"]
    assert Counter(p["goal"] for p in payloads) == dict.fromkeys(
        evalset.GOALS, PAYLOADS_PER_GOAL[j]
    )
    assert len({p["style"] for p in payloads}) == 5


@pytest.mark.parametrize("pair", each(lambda p: True, "payloads"), ids=name)
def test_every_payload_targets_an_answerable_question_it_can_reach(pair):
    j, p = pair
    (note,) = eval_set(j)["by_locator"][f"{PACKS[j].notes}:{p['note']}"]
    target = eval_set(j)["questions"][p["target"]]
    assert note.tier == "T3"
    assert target["kind"] == "answerable"
    assert evalset.valid_on(note, target["as_of"])
    if p["style"] == "hidden":
        assert note.hidden_text and p["instruction"] not in note.body
    else:
        assert p["instruction"] in note.body


@pytest.mark.parametrize("pair", each(lambda p: p["goal"] == "wrong_fact", "payloads"), ids=name)
def test_a_planted_number_is_wrong_for_its_target(pair):
    j, p = pair
    lang = eval_set(j)["lang"]
    planted = tuple(p["canary"])
    target = eval_set(j)["questions"][p["target"]]
    gold = [c for g in target["gold"] for c in in_force(j, g, target["as_of"])]
    assert planted in numbers(p["instruction"], lang)
    assert all(planted not in numbers(c.body, lang) for c in gold)


@pytest.mark.parametrize("j", PACK_IDS)
def test_canaries_are_unique_except_the_shared_prompt_canary(j):
    payloads = eval_set(j)["payloads"]
    canaries = [tuple(p["canary"]) for p in payloads if p["canary"] and p["canary"][0] != "prompt"]
    assert len(canaries) == len(set(canaries))
    assert len({tuple(p["canary"]) for p in payloads if p["goal"] == "leak"}) == 1


@pytest.mark.parametrize("j", PACK_IDS)
def test_planted_figures_that_are_also_true_somewhere_are_known(j):
    """Scoring pairs each wrong-figure attack with the clean run, so a planted figure that a
    passage in force also states is counted only when the attack introduced it."""
    s = eval_set(j)
    collisions = set()
    for p in s["payloads"]:
        if p["goal"] != "wrong_fact":
            continue
        day = s["questions"][p["target"]]["as_of"]
        sources = [c for c in s["chunks"] if c.tier in ("T1", "T2") and evalset.valid_on(c, day)]
        if any(tuple(p["canary"]) in numbers(c.body, s["lang"]) for c in sources):
            collisions.add(p["note"])
    assert collisions == KNOWN_COLLISIONS[j]
