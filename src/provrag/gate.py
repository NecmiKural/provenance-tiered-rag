"""The CI gate: a replayed run must decide exactly as the recording did.

Replay feeds the recorded model replies back through today's retrieval, prompt, verifier and
scoring. It tests the harness, not the model: if any code path changes a decision, a figure,
a citation or an attack outcome, the gate names it.
"""

from __future__ import annotations

from typing import Any

SAME = ("data_fingerprint", "prompt_sha", "method", "k", "cases", "repeats")
ITEM_FIELDS = (
    "refused",
    "refused_by",
    "correct",
    "numbers",
    "cited",
    "attack_draft",
    "attack_final",
)


def check(result: dict[str, Any], recording: dict[str, Any]) -> list[str]:
    problems = [f"{key} differs" for key in SAME if result.get(key) != recording.get(key)]
    if result["aggregate"]["provider_errors"]:
        problems.append("provider errors in the replay")
    for r, (now, then) in enumerate(zip(result["runs"], recording["runs"], strict=True)):
        old = {i["id"]: i for i in then}
        for item in now:
            before = old.get(item["id"], {})
            changed = [f for f in ITEM_FIELDS if item.get(f) != before.get(f)]
            if changed:
                problems.append(f"run {r} {item['id']}: {', '.join(changed)} differ")
    return problems
