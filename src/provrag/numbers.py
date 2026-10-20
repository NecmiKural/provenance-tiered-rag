"""Typed numbers in legal and guidance text.

A number is a (kind, value) pair, so "15 days" can never support "15%", and "15 percent" and
"15%" are the same number. Kinds: percent, money (in cents), date (ISO), day and month without
a year, fraction, a count with a unit (days, weeks, months, years; "2-monthly" is a count of
months) and a day of the month ("the 28th").

Section references ("s 8(1)", "section 51", "subsection (2)") and paragraph labels are not
numbers here, and bare figures without a kind are ignored.

NOTE: pattern based, written for New Zealand English statute and guidance text. It reads
numbers in words only from one to twelve, a range such as "$1,000 to $5,000" comes out as two
numbers, and a figure written two ways ("$2 million", "$2,000,000") is one number by value.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

Number = tuple[str, str]

_MONTH_NAMES = (
    "january february march april may june july august september october november december"
).split()
MONTHS = {name[:3]: i for i, name in enumerate(_MONTH_NAMES, 1)}
WORDS = {
    w: i
    for i, w in enumerate(
        "one two three four five six seven eight nine ten eleven twelve".split(), 1
    )
}

_MONTH = r"(" + "|".join(_MONTH_NAMES) + r"|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)\.?"
_COUNT = r"(\d+|" + "|".join(WORDS) + r")"
_REF_WORD = (
    r"(?:sections?|subsections?|paragraphs?|subparagraphs?|schedules?|parts?|clauses?"
    r"|(?<![\w'’])ss?\.?(?=\s?\d))"
)
_REF_ITEM = r"\(?\d+[A-Z]*\)?(?:\s*\(\w+\))*"
_REFERENCES = re.compile(rf"\b{_REF_WORD}\s*{_REF_ITEM}(?:\s*(?:,|and|or|to)\s*{_REF_ITEM})*", re.I)
_LABELS = re.compile(r"\(\d+[A-Z]*\)|\([a-z]{1,4}\)")

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("iso_date", re.compile(r"\b(\d{4})-(\d\d)-(\d\d)\b")),
    (
        "date",
        re.compile(
            rf"\b(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+day\s+of)?\s+{_MONTH},?\s+(\d{{4}})\b", re.I
        ),
    ),
    ("us_date", re.compile(rf"\b{_MONTH}\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.I)),
    ("day_month", re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+day\s+of)?\s+{_MONTH}\b", re.I)),
    ("money", re.compile(r"(?:NZ)?\$\s?(\d[\d,]*(?:\.\d+)?)(?:\s*(million|billion|m)\b)?", re.I)),
    ("percent", re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:%|per\s?cent\b)", re.I)),
    ("fraction", re.compile(r"\b(\d+)\s*/\s*(\d+)\b")),
    ("monthly", re.compile(rf"\b{_COUNT}[\s-]*monthly\b", re.I)),
    (
        "count",
        re.compile(rf"\b{_COUNT}[\s-]+(working\s+days?|days?|weeks?|months?|years?)\b", re.I),
    ),
    ("day_of_month", re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.I)),
]


def _int(word: str) -> int:
    return WORDS.get(word.lower()) or int(word)


def _month(name: str) -> int:
    return MONTHS[name.lower()[:3]]


def _read(kind: str, g: tuple[str, ...]) -> Number:
    if kind == "iso_date":
        return "date", date(int(g[0]), int(g[1]), int(g[2])).isoformat()
    if kind == "date":
        return "date", date(int(g[2]), _month(g[1]), int(g[0])).isoformat()
    if kind == "us_date":
        return "date", date(int(g[2]), _month(g[0]), int(g[1])).isoformat()
    if kind == "day_month":
        return "day_month", date(2000, _month(g[1]), int(g[0])).strftime("%m-%d")
    if kind == "money":
        scale = {"million": 10**6, "m": 10**6, "billion": 10**9}.get((g[1] or "").lower(), 1)
        return "money", str(int(Decimal(g[0].replace(",", "")) * scale * 100))
    if kind == "percent":
        return "percent", format(Decimal(g[0]).normalize(), "f")
    if kind == "fraction":
        return "fraction", f"{int(g[0])}/{int(g[1])}"
    if kind == "monthly":
        return "count:month", str(_int(g[0]))
    if kind == "count":
        unit = re.sub(r"\s+", "_", g[1].lower()).removesuffix("s")
        return f"count:{unit}", str(_int(g[0]))
    return "day_of_month", str(int(g[0]))


def extract(text: str) -> list[Number]:
    """Typed numbers in the order they appear. Patterns run from the most specific, and each
    span of text is read once, so "1 October 2010" is a date and not also a day and month."""
    text = _LABELS.sub(" ", _REFERENCES.sub(" ", text))
    found: list[tuple[int, Number]] = []
    for kind, pattern in _PATTERNS:
        for m in list(pattern.finditer(text)):
            try:
                found.append((m.start(), _read(kind, m.groups())))
            except (ValueError, KeyError):
                continue  # not a real date, for example 31 February
            text = text[: m.start()] + " " * (m.end() - m.start()) + text[m.end() :]
    return [n for _, n in sorted(found)]


def numbers(text: str) -> set[Number]:
    return set(extract(text))
