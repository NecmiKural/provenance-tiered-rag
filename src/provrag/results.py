"""What every results file shares: the commit it ran from, a fingerprint of the data, Wilson
intervals and the write itself."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Z95 = 1.959964
DATA = ("sources.toml", "corpus", "evals")


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def rate(k: int, n: int) -> dict[str, Any]:
    low, high = wilson(k, n)
    return {"k": k, "n": n, "rate": k / n if n else None, "ci95": [round(low, 4), round(high, 4)]}


def git_commit() -> str:
    """The commit the code ran from, marked -dirty if code, dependencies or data differ."""
    repo = Path(__file__).resolve().parent

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()

    paths = [":/src", ":/pyproject.toml", ":/uv.lock", *(f":/{p}" for p in DATA)]
    try:
        head = git("rev-parse", "--short", "HEAD")
        dirty = git("status", "--porcelain", "--", *paths)
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{head}-dirty" if dirty else head


def fingerprint(jurisdiction: str = "NZ", root: Path = Path(".")) -> str:
    """sha256 over the data a run in one jurisdiction reads: each of its sources as listed in
    sources.toml with the file it points to, and its eval files. Data added for another
    jurisdiction does not change it."""
    sources = tomllib.loads((root / "sources.toml").read_text())["source"]
    evals = root / ("evals" if jurisdiction == "NZ" else f"evals/{jurisdiction.lower()}")
    digest = hashlib.sha256()
    for source in (s for s in sources if s["jurisdiction"] == jurisdiction):
        digest.update(json.dumps(source, sort_keys=True).encode() + b"\0")
        digest.update((root / source["path"]).read_bytes())
    for path in sorted(evals.glob("*.jsonl")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()[:16]


def stamp(kind: str, jurisdiction: str = "NZ") -> dict[str, Any]:
    return {
        "kind": kind,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "jurisdiction": jurisdiction,
        "data_fingerprint": fingerprint(jurisdiction),
    }


def write(
    result: dict[str, Any], name: str, out_dir: Path = Path("results"), dated: bool = True
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (f"{result['generated_at'][:10]}-{name}.json" if dated else f"{name}.json")
    path.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return path
