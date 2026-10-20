"""The verifier: rules an answer must pass, checked in code, with no category chosen by the
model.

1. Every cited passage was retrieved for this question.
2. Every cited passage was in force on the question's date.
3. Every typed number in a claim appears in a statute or guidance passage that claim cites;
   an untrusted note supports nothing, and citing one is an error.
4. Every number in the answer text appears in a claim, so free text cannot slip past rule 3.
5. An answer that is not a refusal has at least one claim, and every claim cites something.

Numbers the question itself contains are exempt: repeating them proves nothing. A refusal
passes; whether refusing was right is scored by the evaluation, not here.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from provrag.evalset import valid_on
from provrag.ingest import Chunk
from provrag.numbers import Number, numbers

SOURCE_TIERS = ("T1", "T2")


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    chunk_ids: list[str]


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    claims: list[Claim]
    refused: bool
    reason: str = ""


def show(found: set[Number]) -> str:
    return ", ".join(f"{value} ({kind})" for kind, value in sorted(found))


def verify(
    draft: Draft,
    question: str,
    day: str,
    retrieved: dict[str, Chunk],
    notes_rule: bool = True,
) -> list[str]:
    """Why the cited passages do not support this answer; empty when they do."""
    if draft.refused:
        return []
    errors: list[str] = []
    if not draft.claims:
        errors.append("an answer that is not a refusal needs at least one claim")
    asked = numbers(question)
    claimed: set[Number] = set()
    for n, claim in enumerate(draft.claims, 1):
        if not claim.chunk_ids:
            errors.append(f"claim {n} cites no passage")
        unknown = [i for i in claim.chunk_ids if i not in retrieved]
        if unknown:
            errors.append(f"claim {n} cites passages that were not retrieved: {', '.join(unknown)}")
        cited = [retrieved[i] for i in claim.chunk_ids if i in retrieved]
        stale = [c.id for c in cited if not valid_on(c, day)]
        if stale:
            errors.append(f"claim {n} cites passages not in force on {day}: {', '.join(stale)}")
        notes = [c.id for c in cited if c.tier not in SOURCE_TIERS]
        if notes and notes_rule:
            errors.append(
                f"claim {n} cites untrusted notes, which are never a source: {', '.join(notes)}"
            )
        sources = SOURCE_TIERS if notes_rule else (*SOURCE_TIERS, "T3")
        support = set().union(*(numbers(c.body) for c in cited if c.tier in sources))
        found = numbers(claim.text)
        claimed |= found
        unsupported = found - asked - support
        if unsupported:
            errors.append(f"claim {n} states {show(unsupported)}, which no cited passage contains")
    loose = numbers(draft.answer) - asked - claimed
    if loose:
        errors.append(f"the answer states {show(loose)}, which no claim states")
    return errors
