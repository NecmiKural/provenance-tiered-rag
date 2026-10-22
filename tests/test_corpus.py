"""The committed corpus is what sources.toml says it is, and it dates the law correctly."""

import hashlib
import re
import tomllib
from collections import defaultdict
from pathlib import Path

import pytest

from provrag import ingest, legislation

ROOT = Path(__file__).resolve().parents[1]
SOURCES = tomllib.loads((ROOT / "sources.toml").read_text())["source"]
STATUTE = next(s for s in SOURCES if s["id"] == "nz-gst-act")
ROWS = legislation.read_jsonl(ROOT / STATUTE["path"])


def in_force(section: str, part: str, day: str) -> str:
    (row,) = [
        r
        for r in ROWS
        if (r["section"], r["part"]) == (section, part)
        and r["valid_from"] <= day
        and (r["valid_to"] is None or day < r["valid_to"])
    ]
    return row["text"]


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_committed_files_match_their_checksums(source):
    assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]


@pytest.mark.parametrize(
    ("day", "rate"),
    [("2010-09-30", "12.5 percent"), ("2010-10-01", "15 percent"), ("2026-06-30", "15%")],
)
def test_the_gst_rate_changes_on_1_october_2010(day, rate):
    assert f"rate of {rate} on the supply" in in_force("8", "1", day)


@pytest.mark.parametrize(
    ("day", "threshold"), [("2009-03-31", "$40,000"), ("2009-04-01", "$60,000")]
)
def test_the_registration_threshold_changes_on_1_april_2009(day, threshold):
    assert re.findall(r"\$[\d,]+", in_force("51", "1", day)) == [threshold]


def test_each_subsection_has_one_text_on_any_day():
    spans = defaultdict(list)
    for r in ROWS:
        spans[(r["section"], r["part"])].append((r["valid_from"], r["valid_to"]))
    for key, items in spans.items():
        items.sort()
        for (start, end), (next_start, _) in zip(items, items[1:], strict=False):
            assert end is not None and start < end <= next_start, key


def test_every_listed_section_is_in_the_latest_version():
    current = {r["section"] for r in ROWS if r["valid_to"] is None}
    assert current == set(STATUTE["sections"])
    assert all(r["text"].strip() for r in ROWS)
    assert min(r["valid_from"] for r in ROWS) == STATUTE["first_version"]


GERMAN = {s["id"]: legislation.read_jsonl(ROOT / s["path"]) for s in SOURCES if "gii" in s}


def de(source: str, section: str, part: str) -> str:
    """The paragraph as indexing reads it: the law's non-breaking spaces become spaces."""
    (row,) = [r for r in GERMAN[source] if (r["section"], r["part"]) == (section, part)]
    return ingest.normalise(row["text"])[0]


def test_the_german_rates_and_thresholds_read_as_published():
    assert "19 Prozent der Bemessungsgrundlage" in de("de-ustg", "12", "1")
    assert "25 000 Euro" in de("de-ustg", "19", "1") and "100 000 Euro" in de("de-ustg", "19", "1")
    assert "16 Prozent" in de("de-ustg", "28", "1") and "1. Juli 2020" in de("de-ustg", "28", "1")
    assert "250 Euro" in de("de-ustdv", "33", "")


def test_a_german_consolidation_is_one_version_dated_by_its_last_amendment():
    for rows in GERMAN.values():
        assert len({r["valid_from"] for r in rows}) == 1
        assert all(r["valid_to"] is None and r["text"].strip() for r in rows)
