"""The Operational Manual parser, and the dated corpus it built."""

import tomllib
from collections import defaultdict
from pathlib import Path

import pytest

from provrag import legislation, opsmanual

ROOT = Path(__file__).resolve().parents[1]
SOURCE = next(
    s
    for s in tomllib.loads((ROOT / "sources.toml").read_text())["source"]
    if s["id"] == "nz-inz-opsmanual"
)
ROWS = legislation.read_jsonl(ROOT / SOURCE["path"])

PAGE = """<html><body><table class="relatedtopics aboveheading"><tr><td>nav</td></tr></table>
<h4 id="t1" class="heading4">SR9.10 Summary of requirements (18/08/2025)</h4>
<ol class="listletter"><li class="listletter">Applicants must be aged 55 or younger.</li></ol>
<p class="headingopsmanual">SR9.10.5 Wage threshold</p>
<table class="tableintopic"><tr><td><p>Date range</p></td><td><p>Threshold</p></td></tr>
<tr><td><p>From 18 August
2025</p></td><td><p>$33.56</p></td></tr></table>
<p class="headingopsmanual">Notes</p><p class="bodytext">A note.</p>
<p class="effectivedate">Effective 18/08/2025</p>
<table class="relatedtopics belowtopictext"><tr><td><p class="relatedheading">PREVIOUS
IMMIGRATION INSTRUCTIONS</p></td></tr></table></body></html>"""


def test_a_page_keeps_its_text_and_drops_the_navigation():
    page = opsmanual.page(PAGE)
    assert page["title"] == "SR9.10 Summary of requirements (18/08/2025)"
    assert page["effective"] == "2025-08-18"
    text = "\n".join(s["text"] for s in page["sections"])
    assert "| From 18 August 2025 | $33.56" in text  # one table row, one line
    assert "PREVIOUS" not in text and "nav" not in text


def test_sections_are_parts_named_by_their_code():
    parts = opsmanual.parts(opsmanual.page(PAGE))
    assert list(parts) == [("SR9.10", ""), ("SR9.10", "5"), ("SR9.10", "#2")]
    assert parts[("SR9.10", "5")]["heading"] == (
        "SR9.10 Summary of requirements / SR9.10.5 Wage threshold"
    )


def test_a_page_with_no_effective_date_is_an_index():
    assert opsmanual.page(PAGE.replace("Effective 18/08/2025", "")) is None


@pytest.mark.parametrize(
    ("title", "end"),
    [
        ("SR3.15 Points Summary (to 23/08/2026)", "2026-08-24"),
        ("SR4.1 Highly Paid objective (revoked 01/07/2023)", "2023-07-01"),
        ("WD4 Transitional visas (Revoked 16/12/2025)", "2025-12-16"),
        ("SR3.10 Summary of requirements", None),
    ],
)
def test_a_slot_ends_the_day_after_to_and_on_the_day_revoked(title, end):
    assert opsmanual.ends(title) == end


def in_force(section: str, part: str, day: str) -> list[dict]:
    return [
        r
        for r in ROWS
        if (r["section"], r["part"]) == (section, part)
        and r["valid_from"] <= day
        and (r["valid_to"] is None or day < r["valid_to"])
    ]


@pytest.mark.parametrize(
    ("day", "wage"), [("2025-10-01", "$33.56"), ("2026-04-01", "$35.00"), ("2024-06-01", "$31.61")]
)
def test_the_median_wage_follows_the_version_in_force(day, wage):
    texts = [r["text"] for r in in_force("SR3.10", "", day) + in_force("SR4.10", "", day)]
    assert any(wage in t for t in texts)


def test_a_revoked_instruction_stops_on_its_revocation_date():
    (highly_paid,) = in_force("SR4.10", "", "2023-06-30")
    assert "twice the median wage" in highly_paid["text"]
    assert highly_paid["valid_to"] == "2023-07-01"
    assert in_force("SR4.10", "", "2023-07-01") == []  # nothing until Tier 1 on 9 October


def test_each_part_has_one_text_on_any_day_and_no_page_chrome():
    spans = defaultdict(list)
    for r in ROWS:
        spans[(r["section"], r["part"])].append((r["valid_from"], r["valid_to"]))
        assert "PREVIOUS IMMIGRATION" not in r["text"] and "Print this page" not in r["text"]
    for key, items in spans.items():
        items.sort()
        for (start, end), (next_start, _) in zip(items, items[1:], strict=False):
            assert end is not None and start < end <= next_start, key
