"""The eval set as a Hugging Face dataset: each pack's questions and payloads in a folder of
its own, with the card from docs/dataset/README.md. CI uploads it from main.

    python -m provrag.dataset <out_dir>
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from provrag.packs import PACKS

CARD = Path("docs/dataset/README.md")
FILES = ("questions.jsonl", "questions-held-back.jsonl", "payloads.jsonl")


def stage(out: Path, root: Path = Path(".")) -> list[Path]:
    """Copy the card and every pack's eval files into out; returns the files written."""
    written = [Path(shutil.copy(root / CARD, out / "README.md"))]
    for pack in PACKS.values():
        (out / pack.id).mkdir(parents=True, exist_ok=True)
        written += [Path(shutil.copy(root / pack.evals / f, out / pack.id / f)) for f in FILES]
    return written


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    print("\n".join(str(p) for p in stage(out)))
