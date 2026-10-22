"""Typed numbers in German statute text, in the same kinds as the English reader.

"19 Prozent" and "19 %" are the same percent, "25 000 Euro" and "25.000 €" the same amount,
"1. Juli 2020" and "01.07.2020" the same date, "zehn Jahre" a count of years, and "bis zum
10. Tag" or "bis zum zehnten Tag" a day of the month. References ("§ 19 Abs. 1 Satz 2 Nr. 1",
"Anlage 2", "Art. 5") are not numbers, and bare figures without a kind are ignored.

NOTE: pattern based, written for federal tax law; numbers in words are read from one to
twelve, and the text is NFKC-normalised first, so the law's non-breaking spaces count as spaces.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal

Number = tuple[str, str]

_MONTH_NAMES = (
    "januar februar märz april mai juni juli august september oktober november dezember"
).split()
MONTHS = {name: i for i, name in enumerate(_MONTH_NAMES, 1)}
WORDS = {
    "ein": 1, "eine": 1, "einem": 1, "einen": 1, "eines": 1, "einer": 1,
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8,
    "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12,
}  # fmt: skip

_MONTH = r"(" + "|".join(MONTHS) + r")"
_COUNT = r"(\d+|" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")"
_AMOUNT = r"(?<![\d.,])(\d{1,3}(?:[ .]\d{3})+|\d+)(?:,(\d{1,2}))?"
_REF = (
    r"(?:§§?|Art\.|Artikel|Absätze|Absatz|Abs\.|Sätze|Satz|Nummern|Nummer|Nr\.|Buchstaben"
    r"|Buchstabe|Buchst\.|Anlagen|Anlage|Unterabsatz|UAbs\.)"
)
# A reference word starts a word: "Satz 2" is a reference, the end of "Umsatz 19" is not.
_REFERENCES = re.compile(rf"(?<!\w){_REF}\s*\d+[a-z]?(?:\s*(?:,|und|bis|oder)\s*\d+[a-z]?)*", re.I)

ORDINALS = {
    w: i
    for i, w in enumerate(
        "ersten zweiten dritten vierten fünften sechsten siebten achten neunten zehnten elften"
        " zwölften".split(),
        1,
    )
}

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("date", re.compile(rf"\b(\d{{1,2}})\.\s*{_MONTH}\s+(\d{{4}})\b", re.I)),
    ("numeric_date", re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")),
    ("money", re.compile(rf"{_AMOUNT}\s*(?:Euro|EUR|€)", re.I)),
    ("money_before", re.compile(rf"(?:€|EUR)\s*{_AMOUNT}", re.I)),
    ("percent", re.compile(rf"\b{_COUNT}(?:,(\d+))?\s*(?:%|Prozent\b|vom\s+Hundert\b)", re.I)),
    ("day_month", re.compile(rf"\b(\d{{1,2}})\.\s*{_MONTH}\b", re.I)),
    ("ordinal_day", re.compile(r"\b(\d{1,2})\.\s*Tag", re.I)),
    ("ordinal_word_day", re.compile(r"\b(" + "|".join(ORDINALS) + r")\s+Tag", re.I)),
    (
        "count",
        re.compile(
            rf"\b{_COUNT}\s+(?:Kalender)?(Tagen|Tage|Tag|Wochen|Woche|Monaten|Monate|Monat"
            r"|Jahren|Jahre|Jahr)\b",
            re.I,
        ),
    ),
    ("fraction", re.compile(r"\b(\d+)\s*/\s*(\d+)\b")),
]
_UNITS = {"tag": "day", "woche": "week", "monat": "month", "jahr": "year"}


def _int(word: str) -> int:
    return WORDS.get(word.lower()) or int(word)


def _cents(whole: str, fraction: str | None) -> str:
    euros = Decimal(re.sub(r"[ .]", "", whole) + "." + (fraction or "0"))
    return str(int(euros * 100))


def _read(kind: str, g: tuple[str, ...]) -> Number:
    if kind == "date":
        return "date", date(int(g[2]), MONTHS[g[1].lower()], int(g[0])).isoformat()
    if kind == "numeric_date":
        return "date", date(int(g[2]), int(g[1]), int(g[0])).isoformat()
    if kind in ("money", "money_before"):
        return "money", _cents(g[0], g[1])
    if kind == "percent":
        value = Decimal(f"{_int(g[0])}.{g[1] or 0}").normalize()
        return "percent", format(value, "f")
    if kind == "day_month":
        return "day_month", date(2000, MONTHS[g[1].lower()], int(g[0])).strftime("%m-%d")
    if kind == "ordinal_day":
        return "day_of_month", str(int(g[0]))
    if kind == "ordinal_word_day":
        return "day_of_month", str(ORDINALS[g[0].lower()])
    if kind == "count":
        unit = next(u for stem, u in _UNITS.items() if g[1].lower().startswith(stem))
        return f"count:{unit}", str(_int(g[0]))
    return "fraction", f"{int(g[0])}/{int(g[1])}"


def extract(text: str) -> list[Number]:
    """Typed numbers in the order they appear, each span read once, most specific first."""
    text = _REFERENCES.sub(" ", unicodedata.normalize("NFKC", text))
    found: list[tuple[int, Number]] = []
    for kind, pattern in _PATTERNS:
        for m in list(pattern.finditer(text)):
            try:
                found.append((m.start(), _read(kind, m.groups())))
            except (ValueError, KeyError):
                continue  # not a real date, for example 31.02.2020
            text = text[: m.start()] + " " * (m.end() - m.start()) + text[m.end() :]
    return [n for _, n in sorted(found)]
