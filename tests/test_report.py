"""The README results block is exactly what `provrag report` writes from results/*.json."""

from pathlib import Path

from provrag import report

ROOT = Path(__file__).resolve().parents[1]


def test_readme_results_are_in_sync():
    assert not report.sync(ROOT / "README.md", ROOT / "results", check=True), (
        "README results are stale: run `uv run provrag report`"
    )


def test_attacks_succeed_somewhere_with_every_defence_off():
    """An attack set that never succeeds, even undefended, would prove nothing."""
    off = report.evals(ROOT / "results").get("off")
    assert off is not None
    assert off["aggregate"]["attacks_total"]["draft"]["k"] > 0
