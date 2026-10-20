"""The answer loop, hand-rolled: one draft, the verifier, at most one repair, then an answer
or a refusal with its reason.

Every rule in prompts/answer.md has eval cases: rule 1 the unanswerable questions, rule 2 the
cite_payload goal, rule 3 the calculation questions and the wrong_fact goal, rule 4 the leak
goal, rule 5 the off_task goal, and the fence the payload notes as a whole.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from importlib.resources import files

from pydantic import ValidationError

from provrag.ingest import Chunk
from provrag.llm import LLM, cost_usd, usage_of
from provrag.verify import Draft, verify

PROMPT = files("provrag").joinpath("prompts/answer.md").read_text()
PROMPT_SHA = hashlib.sha256(PROMPT.encode()).hexdigest()[:12]
PROMPT_CANARY = "PROMPT-CANARY-K7Q2"
JSON = {"type": "json_object"}
TIER_NAMES = {"T1": "statute", "T2": "guidance"}


@dataclass(frozen=True)
class Defences:
    """Each defence can be switched off for the ablation."""

    name: str = "on"
    fence: bool = True  # notes go in an untrusted block; off, they look like any passage
    notes_rule: bool = True  # the verifier refuses notes as a source
    verifier: bool = True  # off, the first draft is the answer: no checks, no repair
    normalise: bool = True  # off, a planted note keeps its invisible characters (evaluation only)


DEFENCES = {
    d.name: d
    for d in (
        Defences(),
        Defences("fence_off", fence=False),
        Defences("notes_rule_off", notes_rule=False),
        Defences("verifier_off", verifier=False),
        Defences("normalise_off", normalise=False),
        Defences("off", fence=False, notes_rule=False, verifier=False, normalise=False),
    )
}


@dataclass
class Attempt:
    content: str
    draft: Draft | None
    errors: list[str]


@dataclass
class Outcome:
    attempts: list[Attempt] = field(default_factory=list)
    answer: Draft | None = None  # what the user sees: an accepted answer or a refusal
    refused_by: str = ""  # "model", "verifier" or "invalid_reply" when the answer is a refusal
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0

    @property
    def repaired(self) -> bool:
        return len(self.attempts) == 2 and self.answer is not None and not self.answer.refused

    def text(self, which: int = -1) -> str:
        """Everything an attempt showed, for canary scans: the raw reply of that attempt."""
        return self.attempts[which].content if self.attempts else ""


def _fenced(text: str) -> str:
    """Angle brackets become parentheses, so passage text cannot close or open a tag."""
    return text.replace("<", "(").replace(">", ")")


def passage(chunk: Chunk, fence: bool) -> str:
    until = f"until {chunk.valid_to}" if chunk.valid_to else "onwards"
    body = _fenced(f"{chunk.heading}\n{chunk.body}")
    if chunk.tier == "T3" and fence:
        return f'<untrusted_note id="{chunk.id}">\n{body}\n</untrusted_note>'
    tier = TIER_NAMES.get(chunk.tier, "guidance")  # unfenced, a note passes as guidance
    return (
        f'<passage id="{chunk.id}" tier="{tier}" in_force="{chunk.valid_from} {until}">\n'
        f"{body}\n</passage>"
    )


def user_message(question: str, day: str, chunks: list[Chunk], defences: Defences) -> str:
    passages = "\n\n".join(passage(c, defences.fence) for c in chunks)
    return f"Question date: {day}\nQuestion: {_fenced(question)}\n\n{passages}"


def repair_message(errors: list[str]) -> str:
    listed = "\n".join(f"- {e}" for e in errors)
    return (
        "The verifier rejected that reply:\n"
        f"{listed}\n"
        "Reply again in json: a corrected answer that follows the rules, or a refusal."
    )


def parse(content: str) -> tuple[Draft | None, list[str]]:
    try:
        return Draft.model_validate(json.loads(content)), []
    except (json.JSONDecodeError, ValidationError) as error:
        first = str(error).splitlines()[0]
        return None, [f"the reply is not a json object in the required shape ({first})"]


def answer(
    question: str,
    day: str,
    chunks: list[Chunk],
    llm: LLM,
    defences: Defences = DEFENCES["on"],
) -> Outcome:
    retrieved = {c.id: c for c in chunks}
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": user_message(question, day, chunks, defences)},
    ]
    outcome = Outcome()
    for round_ in (1, 2):
        reply = llm.chat(messages, response_format=JSON)
        outcome.latency_ms += reply.latency_ms
        usage = usage_of(reply.response)
        outcome.input_tokens += usage.input_tokens
        outcome.cached_tokens += usage.cached_tokens
        outcome.output_tokens += usage.output_tokens
        outcome.cost_usd += cost_usd(llm.spec, usage)
        content = reply.response.choices[0].message.content or ""
        draft, errors = parse(content)
        if draft is not None and defences.verifier:
            errors = verify(draft, question, day, retrieved, notes_rule=defences.notes_rule)
        outcome.attempts.append(Attempt(content, draft, errors))
        if draft is not None and (not errors or not defences.verifier):
            outcome.answer = draft
            outcome.refused_by = "model" if draft.refused else ""
            return outcome
        if round_ == 1 and defences.verifier:
            messages += [
                {"role": "assistant", "content": content},
                {"role": "user", "content": repair_message(errors)},
            ]
        else:
            break
    last = outcome.attempts[-1]
    outcome.answer = Draft(
        answer="", claims=[], refused=True, reason=f"not verified: {'; '.join(last.errors)}"
    )
    outcome.refused_by = "verifier" if last.draft is not None else "invalid_reply"
    return outcome
