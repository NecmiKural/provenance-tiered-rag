"""German federal law from gesetze-im-internet.de, one chunk per paragraph (Absatz).

Laws and regulations are official works without copyright protection (§ 5 Abs. 1 UrhG). The
site publishes only the current consolidation of each law, as XML.

NOTE: one consolidation, dated by its last amending act ("Stand"). A chunk is treated as in
force from that date onward, so questions about earlier dates find nothing and are refused,
even where today's text describes an earlier window (§ 28 UStG states the 2020 rate cut). The
upgrade path is a source of dated versions; the federal NeuRIS service holds only the current
UStG in its test phase.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date

from provrag.legislation import get

BASE = "https://www.gesetze-im-internet.de"
_STAND = re.compile(r"v\.\s*(\d{1,2})\.(\d{1,2})\.(\d{4})")
_ABSATZ = re.compile(r"^\((\d+[a-z]?)\)\s*")


def text_of(element: ET.Element) -> str:
    """All text of an element, with every run of whitespace made one space. Non-breaking spaces
    (the law's thousands separator) are kept; indexing normalises them."""
    return re.sub(r"[ \t\r\n]+", " ", " ".join(element.itertext())).strip()


def stand(root: ET.Element) -> str:
    """The date of the last amending act, from the law's "Stand" note."""
    for note in root.iter("standangabe"):
        if (note.findtext("standtyp") or "").strip() == "Stand":
            d, m, y = _STAND.search(note.findtext("standkommentar") or "").groups()
            return date(int(y), int(m), int(d)).isoformat()
    raise ValueError("no Stand note in the law's metadata")


def norms(xml: bytes, wanted: dict[str, list[str] | None]) -> tuple[str, list[dict]]:
    """Rows for the wanted sections: one per Absatz, or for a section listed with item numbers,
    one per numbered item (§ 4 UStG lists its exemptions as Nr. 1 to Nr. 29)."""
    root = ET.fromstring(xml)
    valid_from = stand(root)
    rows = []
    for norm in root.iter("norm"):
        label = (norm.findtext("metadaten/enbez") or "").strip().removeprefix("§").strip()
        if label not in wanted:
            continue
        heading = (norm.findtext("metadaten/titel") or "").strip()
        content = norm.find("textdaten/text/Content")
        if content is None:
            continue
        items = wanted[label]
        if items:
            number = ""
            for child in content.find("P/DL"):  # the top-level list only, not nested letters
                if child.tag == "DT":
                    number = (child.text or "").strip().rstrip(".")
                elif child.tag == "DD" and number in items:
                    rows.append(row(label, f"Nr. {number}", heading, text_of(child), valid_from))
            continue
        for paragraph in content.findall("P"):
            text = text_of(paragraph)
            match = _ABSATZ.match(text)
            part = match.group(1) if match else ""
            rows.append(
                row(label, part, heading, text[match.end() :] if match else text, valid_from)
            )
    return valid_from, rows


def row(section: str, part: str, heading: str, text: str, valid_from: str) -> dict:
    return {
        "section": section,
        "part": part,
        "heading": heading,
        "text": text,
        "valid_from": valid_from,
        "valid_to": None,
    }


def build(slug: str, wanted: dict[str, list[str] | None]) -> list[dict]:
    archive = zipfile.ZipFile(io.BytesIO(get(f"{BASE}/{slug}/xml.zip")))
    (name,) = [n for n in archive.namelist() if n.endswith(".xml")]
    _, rows = norms(archive.read(name), wanted)
    return rows
