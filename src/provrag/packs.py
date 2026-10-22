"""Packs: one body of law with its own sources, eval set, prompt and language.

A run reads one pack, not one jurisdiction: New Zealand has more than one body of law here,
and retrieval, fingerprints and results files must not mix them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Pack:
    id: str
    jurisdiction: str
    lang: str  # the language its sources are written in, for numbers and stemming
    sources: tuple[str, ...]  # ids in sources.toml, the untrusted notes last
    evals: Path
    suffix: str  # the part a results file name carries; empty for the first pack

    @property
    def notes(self) -> str:
        return self.sources[-1]


PACKS = {
    p.id: p
    for p in (
        Pack(
            "nz-gst",
            "NZ",
            "en",
            ("nz-gst-act", "nz-ird-gst-guidance", "nz-notes"),
            Path("evals"),
            "",
        ),
        Pack("de-vat", "DE", "de", ("de-ustg", "de-ustdv", "de-notes"), Path("evals/de"), "de"),
        Pack(
            "nz-immigration",
            "NZ",
            "en",
            ("nz-immigration-act", "nz-inz-opsmanual", "nz-imm-notes"),
            Path("evals/nz-immigration"),
            "nz-immigration",
        ),
    )
}
DEFAULT = "nz-gst"
PACK_OF_SOURCE = {s: p.id for p in PACKS.values() for s in p.sources}
# Results files written before packs existed name only their jurisdiction.
_BY_JURISDICTION = {"NZ": "nz-gst", "DE": "de-vat"}


def of_result(result: dict[str, Any]) -> str:
    return result.get("pack") or _BY_JURISDICTION[result.get("jurisdiction", "NZ")]
