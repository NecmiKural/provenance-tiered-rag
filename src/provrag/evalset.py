"""The eval set: questions with their gold passages, and the payloads planted in notes.

Gold passages are named by source and locator without a date (nz-gst-act:s8(1)), so the
passage that counts is whichever version was in force on the question's date, and cutting
the corpus differently does not break the labels.
"""

from __future__ import annotations

import json
from pathlib import Path

from provrag.ingest import Chunk
from provrag.packs import DEFAULT, PACKS

# advice: a personal assessment, which only the immigration pack asks for and which must be refused
KINDS = ("answerable", "unanswerable", "calculation", "advice")
GOALS = ("wrong_fact", "cite_payload", "leak", "wrongful_refusal", "off_task")


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]


def questions(held_back: bool = False, pack: str = DEFAULT) -> list[dict]:
    name = "questions-held-back.jsonl" if held_back else "questions.jsonl"
    return [{**q, "pack": pack} for q in read(PACKS[pack].evals / name)]


def payloads(pack: str = DEFAULT) -> list[dict]:
    return read(PACKS[pack].evals / "payloads.jsonl")


def locator(chunk: Chunk) -> str:
    """The dateless name of a chunk's passage, as gold labels use it."""
    return chunk.id.rsplit("@", 1)[0]


def valid_on(chunk: Chunk, day: str) -> bool:
    return chunk.valid_from <= day and (chunk.valid_to is None or day < chunk.valid_to)
