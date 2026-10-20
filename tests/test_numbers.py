"""Typed number extraction: the same number written differently matches, and different kinds
never do."""

import pytest

from provrag.numbers import extract, numbers


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("at the rate of 15 percent on the supply", [("percent", "15")]),
        ("at the rate of 15% on the supply", [("percent", "15")]),
        ("the rate of 12.5 percent", [("percent", "12.5")]),
        ("turnover of $60,000 or more", [("money", "6000000")]),
        ("$2 million or less", [("money", "200000000")]),
        ("not more than $2,000,000", [("money", "200000000")]),
        ("goods valued at or below NZ$1,000", [("money", "100000")]),
        ("on or after the 1st day of October 1986", [("date", "1986-10-01")]),
        ("from 1 October 2010", [("date", "2010-10-01")]),
        ("as at 2010-09-30", [("date", "2010-09-30")]),
        (
            "the period ending 31 March is due by 7 May",
            [("day_month", "03-31"), ("day_month", "05-07")],
        ),
        ("due by the 28th of the month", [("day_of_month", "28")]),
        ("within 21 days", [("count:day", "21")]),
        ("for a period of 7 years", [("count:year", "7")]),
        ("within the next 12 months", [("count:month", "12")]),
        ("six-monthly filers", [("count:month", "6")]),
        ("2-monthly filing", [("count:month", "2")]),
        ("multiply by 3/23", [("fraction", "3/23")]),
    ],
)
def test_each_kind_reads_its_value(text, expected):
    assert extract(text) == expected


def test_kinds_never_match_each_other():
    assert numbers("15 days").isdisjoint(numbers("15%"))
    assert numbers("$15").isdisjoint(numbers("15 percent"))


@pytest.mark.parametrize(
    "text",
    [
        "under section 51(1)(a) of this Act",
        "as provided in s 8(1) and s 15(2)",
        "subsection (2) applies to paragraph (b)",
        "sections 19 to 19D",
        "(3) Every registered person",
        "it's 2 o'clock",
    ],
)
def test_references_labels_and_bare_figures_are_not_numbers(text):
    assert extract(text) == []


def test_an_apostrophe_s_is_not_a_section_reference():
    assert extract("the supplier's 15% rate") == [("percent", "15")]


def test_an_impossible_date_is_skipped():
    assert ("date", "2010-02-31") not in numbers("31 February 2010")
