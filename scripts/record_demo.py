"""Render the offline demo to docs/demo.svg.

Run with the database up: `uv run --with rich python scripts/record_demo.py`. It replays the
committed slice exactly as `make demo` does, needs no model key, and prints each case with its
dated, tiered citations and the verifier's verdict.
"""

import contextlib
import io
import json
import re
import tempfile
import tomllib
from pathlib import Path

from rich._export_format import CONSOLE_SVG_FORMAT
from rich.console import Console
from rich.text import Text

from provrag import cli

ROOT = Path(__file__).resolve().parents[1]
# Rich's template fetches Fira Code from cdnjs; without it the SVG makes no outside request.
SVG_FORMAT = re.sub(r"\s*@font-face \{\{.*?\}\}", "", CONSOLE_SVG_FORMAT, flags=re.S)


def citation(chunk_id: str, tiers: dict[str, str]) -> str:
    passage, valid_from = chunk_id.rsplit("@", 1)
    return f"{tiers[passage.split(':', 1)[0]]} {passage}, in force from {valid_from}"


def main() -> None:
    with tempfile.TemporaryDirectory() as out:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            cli.main(
                ["eval", "--mode", "replay", "--repeats", "1", "--every", "6", "--cassette"]
                + [str(ROOT / "tests" / "cassettes" / "slice.jsonl"), "--out", out]
                + ["--name", "demo"]
            )
        result = json.loads((Path(out) / "demo.json").read_text())
    lines = (ROOT / "evals" / "questions.jsonl").read_text().splitlines()
    questions = {q["id"]: q for q in map(json.loads, filter(None, lines))}
    sources = tomllib.loads((ROOT / "sources.toml").read_text())["source"]
    tiers = {s["id"]: s["tier"] for s in sources}

    console = Console(record=True, width=150, file=io.StringIO())
    console.print(Text("$ make demo", style="bold"))
    console.print(
        Text("  replays the committed slice: every sixth development question, defences on", "dim")
    )
    for case in result["runs"][0]:
        q = questions[case["question"]]
        ok = case["correct"] and not case.get("attack_final")
        head = f"{'ok ' if ok else 'BAD'} {case['id']:8} as of {q['as_of']}  {q['question']}"
        console.print(Text(head, style="green" if ok else "bold red"))
        if case["goal"]:
            followed = "followed" if case.get("attack_final") else "not followed"
            goal = case["goal"].replace("_", " ")
            console.print(Text(f"      planted note ({goal}): {followed}", "dim"))
        if case["refused"]:
            console.print(Text(f"      refused by the {case['refused_by']}", "dim"))
            continue
        for chunk_id in case["cited"]:
            console.print(Text("      " + citation(chunk_id, tiers), "dim"))
        verdict = "passed" if case["passes_verifier"] else "failed"
        console.print(Text(f"      verifier {verdict}", "dim"))
    console.print(Text(printed.getvalue().splitlines()[0], style="bold"))

    path = ROOT / "docs" / "demo.svg"
    console.save_svg(str(path), title="provrag: offline demo", code_format=SVG_FORMAT)
    assert not re.search(r"url\((?!#)", path.read_text()), "the SVG must load nothing from outside"
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
