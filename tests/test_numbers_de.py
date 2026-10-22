"""German typed numbers: the same kinds as English, written the German way."""

import pytest

from provrag.numbers import extract, numbers


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("19 Prozent der Bemessungsgrundlage", [("percent", "19")]),
        ("ermäßigt sich auf sieben Prozent", [("percent", "7")]),
        ("ein Satz von 5,5 %", [("percent", "5.5")]),
        ("Gesamtumsatz 25 000 Euro nicht überschritten", [("money", "2500000")]),
        ("im laufenden Kalenderjahr 100 000 Euro", [("money", "10000000")]),
        ("Gesamtbetrag 250 Euro nicht übersteigt", [("money", "25000")]),
        ("mehr als 800.000 €", [("money", "80000000")]),
        (
            "vom 1. Juli 2020 bis 31. Dezember 2020",
            [("date", "2020-07-01"), ("date", "2020-12-31")],
        ),
        ("am 01.01.2025", [("date", "2025-01-01")]),
        ("bis zum 10. Tag nach Ablauf", [("day_of_month", "10")]),
        ("bis zum zehnten Tag nach Ablauf", [("day_of_month", "10")]),
        ("acht Jahre aufzubewahren", [("count:year", "8")]),
        ("innerhalb von zehn Tagen", [("count:day", "10")]),
    ],
)
def test_each_kind_reads_its_value(text, expected):
    assert extract(text, "de") == expected


@pytest.mark.parametrize(
    "text",
    [
        "§ 19 Abs. 1 Satz 2 Nr. 1",
        "Absatz 3 Satz 1 und Anlage 2",
        "durch Art. 5 G",
        "§§ 10, 11, 25 Abs. 3",
        "1. den vollständigen Namen",
    ],
)
def test_references_and_list_labels_are_not_numbers(text):
    assert extract(text, "de") == []


def test_kinds_never_match_each_other_in_german():
    assert numbers("16 Tage", "de").isdisjoint(numbers("16 Prozent", "de"))


def test_a_reference_word_inside_another_word_is_not_a_reference():
    assert extract("Gesamtumsatz 25 000 Euro", "de") == [("money", "2500000")]
    assert extract("für jeden steuerpflichtigen Umsatz 19 Prozent", "de") == [("percent", "19")]


def test_an_amount_does_not_swallow_a_year_before_it():
    assert extract("im Jahr 2025 300 Euro", "de") == [("money", "30000")]


def test_english_stays_the_default():
    assert extract("19 Prozent") == [] and extract("15%") == [("percent", "15")]
