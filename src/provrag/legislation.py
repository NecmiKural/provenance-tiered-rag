"""Point-in-time sections of a New Zealand Act, from legislation.govt.nz.

There is no copyright in New Zealand legislation (Copyright Act 1994, s 27), so the extracted
text is committed. Every consolidated version of the Act in a fixed date range is downloaded
once as XML (cached under data/, which is not committed), the chosen sections are cut into
subsections, and each distinct subsection text gets the half-open date interval during which
the consolidations show it unchanged.

NOTE: a version date is the date of a consolidation, not the commencement date of each
amendment in it. An amendment that took effect between two consolidations is dated here
from the later one. The tested events (the 2009 registration threshold and the 2010 rate
change) have consolidations on their commencement dates; others may not.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path

BASE = "https://www.legislation.govt.nz"
USER_AGENT = (
    "Mozilla/5.0 (compatible; provenance-tiered-rag/0.1;"
    " +https://github.com/NecmiKural/provenance-tiered-rag)"
)
PAUSE_SECONDS = 1.0  # between network requests, to be gentle with a public site
SKIP = {"notes", "history"}  # amendment history, not law


def get(url: str, attempts: int = 3) -> bytes:
    """GET with a pause after every request and a retry on a transient server error."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == attempts:
                raise
            time.sleep(PAUSE_SECONDS * 10 * attempt)
            continue
        time.sleep(PAUSE_SECONDS)
        return body
    raise AssertionError("unreachable")


def version_dates(act: str) -> list[str]:
    """Every consolidation date of the Act that the site lists, oldest first."""
    latest = get(f"{BASE}{act}latest/").decode()
    (current,) = set(re.findall(rf"{re.escape(act)}(\d{{4}}-\d\d-\d\d)\.pdf", latest))
    dates = {current}
    for page in range(1, 50):
        html = get(f"{BASE}{act}{current}/versions/?per_page=50&page={page}").decode()
        found = set(re.findall(rf'href="{re.escape(act)}(\d{{4}}-\d\d-\d\d)/"', html))
        if found <= dates:
            break
        dates |= found
    return sorted(dates)


def version_xml(act: str, date: str, cache: Path) -> bytes:
    path = cache / f"{date}.xml"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(get(f"{BASE}{act}{date}.xml"))
    return path.read_bytes()


def render(element: ET.Element) -> str:
    """Plain text of a provision: paragraph labels in brackets, amendment notes left out."""
    parts: list[str] = []

    def walk(e: ET.Element) -> None:
        if e.tag in SKIP:
            return
        if e.get("deletion-status") == "repealed":
            parts.append(" [Repealed] ")
            return  # a repealed provision may keep an empty shell or a stale text
        if e.tag == "label":
            parts.append(f" ({(e.text or '').strip()}) ")
        else:
            parts.append(e.text or "")
            for child in e:
                walk(child)
                parts.append(child.tail or "")

    walk(element)
    return " ".join("".join(parts).split())


def sections(xml: bytes, wanted: Iterable[str]) -> dict[tuple[str, str], dict[str, str]]:
    """Subsections of the wanted sections in the body of one version, keyed by (section, part).

    A section without subsections is one part named "". A repealed section keeps its stub.
    """
    wanted = set(wanted)
    body = ET.fromstring(xml).find("body")
    out: dict[tuple[str, str], dict[str, str]] = {}
    seen: set[str] = set()
    for prov in body.iter("prov") if body is not None else ():
        label = (prov.findtext("label") or "").strip()
        if label not in wanted or label in seen:  # the first is the section, not a quotation
            continue
        seen.add(label)
        heading = render(prov.find("heading")) if prov.find("heading") is not None else ""
        if prov.get("deletion-status") == "repealed":
            out[(label, "")] = {"heading": heading, "text": "[Repealed]"}
            continue
        content = prov.find("prov.body")
        subs = content.findall("subprov") if content is not None else []
        if not subs:
            text = render(content) if content is not None else ""
            out[(label, "")] = {"heading": heading, "text": text}
        for sub in subs:
            part = (sub.findtext("label") or "").strip()
            body_only = ET.Element("subprov", sub.attrib)  # the same subsection without its label
            body_only.extend(c for c in sub if c.tag != "label")
            out[(label, part)] = {"heading": heading, "text": render(body_only)}
    return out


def intervals(versions: dict[str, dict[tuple[str, str], dict[str, str]]]) -> list[dict]:
    """One row per distinct text of each subsection, valid from the first consolidation that
    shows it until the first that does not (valid_to is exclusive; None means still current)."""
    rows: list[dict] = []
    open_rows: dict[tuple[str, str], dict] = {}
    for date in sorted(versions):
        current = versions[date]
        for key, row in list(open_rows.items()):
            if key not in current or current[key] != {k: row[k] for k in ("heading", "text")}:
                row["valid_to"] = date
                del open_rows[key]
        for key, content in current.items():
            if key not in open_rows:
                row = {"section": key[0], "part": key[1], **content}
                row |= {"valid_from": date, "valid_to": None}
                rows.append(row)
                open_rows[key] = row
    return rows


def section_order(label: str) -> tuple[int, str]:
    number = re.match(r"\d+", label)
    return (int(number.group()) if number else 0, label)


def build(act: str, wanted: list[str], first: str, last: str, cache: Path) -> list[dict]:
    dates = [d for d in version_dates(act) if first <= d <= last]
    versions = {d: sections(version_xml(act, d, cache), wanted) for d in dates}
    rows = intervals(versions)
    return sorted(rows, key=lambda r: (section_order(r["section"]), r["part"], r["valid_from"]))


def write_jsonl(rows: list[dict], path: Path) -> None:
    """ASCII-escaped JSON keeps the statute's own punctuation exact in an ASCII-only file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, sort_keys=True, ensure_ascii=True) + "\n" for r in rows)
    path.write_text(text, encoding="ascii")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]
