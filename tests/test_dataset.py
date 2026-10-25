"""The Hugging Face dataset holds exactly the frozen eval files, each named by the card."""

import re
from pathlib import Path

from provrag import dataset

ROOT = Path(__file__).resolve().parents[1]


def test_the_card_names_every_staged_file_and_nothing_else(tmp_path):
    staged = {p.relative_to(tmp_path).as_posix() for p in dataset.stage(tmp_path, ROOT)}
    card = (ROOT / dataset.CARD).read_text()
    named = set(re.findall(r"^\s+path: (\S+)$", card, flags=re.M))
    assert named == staged - {"README.md"}


def test_staged_files_are_the_eval_files_byte_for_byte(tmp_path):
    for path in dataset.stage(tmp_path, ROOT):
        if path.name != "README.md":
            pack = next(p for p in dataset.PACKS.values() if p.id == path.parent.name)
            assert path.read_bytes() == (ROOT / pack.evals / path.name).read_bytes()
