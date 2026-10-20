"""The committed slice replays to the same decisions, a doctored copy does not, and nothing
recorded carries a key."""

import json
import re
from pathlib import Path

from provrag import answer, cli, embed, evaluate, gate
from provrag.llm import MODELS

ROOT = Path(__file__).resolve().parents[1]
CASSETTE = ROOT / "tests/cassettes/slice.jsonl"
RECORDING = json.loads((ROOT / "tests/cassettes/slice.json").read_text())
REFUSAL = json.dumps({"answer": "", "claims": [], "refused": True, "reason": "doctored"})


def replay(conn, cassette):
    return evaluate.evaluate(
        conn,
        embed.embedder(embed.GEMINI, embed.cache_path(embed.GEMINI)),
        MODELS[RECORDING["model"]],
        answer.DEFENCES[RECORDING["defences"]["name"]],
        RECORDING["repeats"],
        "replay",
        cassette,
        workers=4,
        every=RECORDING["every"],
    )


def test_the_slice_replays_to_the_recorded_decisions(conn):
    assert gate.check(replay(conn, CASSETTE), RECORDING) == []


def test_a_doctored_cassette_fails_the_gate(conn, tmp_path):
    doctored = tmp_path / "doctored.jsonl"
    lines = []
    for line in CASSETTE.read_text().splitlines():
        entry = json.loads(line)
        entry["response"]["choices"][0]["message"]["content"] = REFUSAL
        lines.append(json.dumps(entry))
    doctored.write_text("\n".join(lines) + "\n")
    problems = gate.check(replay(conn, doctored), RECORDING)
    assert any("refused" in p for p in problems)


def test_the_recordings_hold_no_keys_or_headers():
    text = CASSETTE.read_text() + json.dumps(RECORDING)
    assert not re.search(r"sk-[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{20,}|Bearer |Authorization", text)


def test_the_cli_replays_the_slice_end_to_end(conn, tmp_path, capsys):
    cli.main(
        [
            "eval",
            "--mode",
            "replay",
            "--repeats",
            str(RECORDING["repeats"]),
            "--every",
            str(RECORDING["every"]),
            "--cassette",
            str(CASSETTE),
            "--out",
            str(tmp_path),
            "--name",
            "replayed",
            "--workers",
            "4",
        ]
    )
    assert "provider errors 0" in capsys.readouterr().out
    assert gate.check(json.loads((tmp_path / "replayed.json").read_text()), RECORDING) == []
