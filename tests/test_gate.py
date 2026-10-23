"""Each committed slice replays to the same decisions, a doctored copy does not, and nothing
recorded carries a key. One slice per pack that has one: New Zealand GST and immigration."""

import json
import re
from pathlib import Path

import pytest

from provrag import answer, cli, embed, evaluate, gate, packs
from provrag.llm import MODELS

ROOT = Path(__file__).resolve().parents[1]
SLICES = ["slice", "slice-nz-immigration"]
REFUSAL = json.dumps({"answer": "", "claims": [], "refused": True, "reason": "doctored"})
pytestmark = pytest.mark.parametrize("name", SLICES)


def recorded(name):
    """The slice's cassette and the results file it was recorded with."""
    cassette = ROOT / f"tests/cassettes/{name}.jsonl"
    return cassette, json.loads(cassette.with_suffix(".json").read_text())


def replay(conn, cassette, recording):
    return evaluate.evaluate(
        conn,
        embed.embedder(embed.GEMINI, embed.cache_path(embed.GEMINI)),
        MODELS[recording["model"]],
        answer.DEFENCES[recording["defences"]["name"]],
        recording["repeats"],
        "replay",
        cassette,
        workers=4,
        every=recording["every"],
        pack=packs.of_result(recording),
    )


def test_the_slice_replays_to_the_recorded_decisions(conn, name):
    cassette, recording = recorded(name)
    assert gate.check(replay(conn, cassette, recording), recording) == []


def test_a_doctored_cassette_fails_the_gate(conn, tmp_path, name):
    cassette, recording = recorded(name)
    doctored = tmp_path / "doctored.jsonl"
    lines = []
    for line in cassette.read_text().splitlines():
        entry = json.loads(line)
        entry["response"]["choices"][0]["message"]["content"] = REFUSAL
        lines.append(json.dumps(entry))
    doctored.write_text("\n".join(lines) + "\n")
    problems = gate.check(replay(conn, doctored, recording), recording)
    assert any("refused" in p for p in problems)


def test_the_recordings_hold_no_keys_or_headers(name):
    cassette, recording = recorded(name)
    text = cassette.read_text() + json.dumps(recording)
    assert not re.search(r"sk-[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{20,}|Bearer |Authorization", text)


def test_the_cli_replays_the_slice_end_to_end(conn, tmp_path, capsys, name):
    cassette, recording = recorded(name)
    cli.main(
        [
            "eval",
            "--pack",
            packs.of_result(recording),
            "--mode",
            "replay",
            "--repeats",
            str(recording["repeats"]),
            "--every",
            str(recording["every"]),
            "--cassette",
            str(cassette),
            "--out",
            str(tmp_path),
            "--name",
            "replayed",
            "--workers",
            "4",
        ]
    )
    assert "provider errors 0" in capsys.readouterr().out
    assert gate.check(json.loads((tmp_path / "replayed.json").read_text()), recording) == []
