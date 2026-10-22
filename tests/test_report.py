"""The README results block is exactly what `provrag report` writes from results/*.json."""

from pathlib import Path

import pytest

from provrag import report

ROOT = Path(__file__).resolve().parents[1]


def test_readme_results_are_in_sync():
    assert not report.sync(ROOT / "README.md", ROOT / "results", check=True), (
        "README results are stale: run `uv run provrag report`"
    )


@pytest.mark.parametrize("pack", ["nz-gst", "de-vat", "nz-immigration"])
def test_attacks_succeed_somewhere_with_every_defence_off(pack):
    """An attack set that never succeeds, even undefended, would prove nothing."""
    off = report.evals(ROOT / "results", pack).get("off")
    assert off is not None
    assert off["aggregate"]["attacks_total"]["draft"]["k"] > 0


def test_only_a_pack_that_asks_for_advice_gets_an_advice_row():
    on = report.evals(ROOT / "results")["on"]
    assert not any("own case" in line for line in report.main_table(on))
    advice = {"k": 2, "n": 2, "rate": 1.0, "ci95": [0.3424, 1.0]}
    asked = {**on, "aggregate": {**on["aggregate"], "advice_refused": advice}}
    assert "| Asks to assess the asker's own case: refused | 2 of 2 (100.0%) |" in (
        report.main_table(asked)
    )


def test_a_summary_rate_over_no_cases_prints_as_not_available():
    from provrag import cli

    assert cli.rate3({"k": 0, "n": 0, "rate": None}) == "n/a"
    assert cli.rate3({"k": 1, "n": 2, "rate": 0.5}) == "0.500"
