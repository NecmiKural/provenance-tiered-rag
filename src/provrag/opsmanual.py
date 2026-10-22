"""Immigration New Zealand's Operational Manual: chosen instructions with their past versions.

The manual is a static help site: toc.json lists every topic, and each numbered instruction
(a slot) lists its archived versions as children whose titles end with the date they took
effect. Each page states its own "Effective" date, and a slot that ended says so in its title
("to 23/08/2026", "revoked 01/07/2023"). A version is in force from its effective date until
the next version of the same slot takes effect; the last until the slot ends, or onwards.

Crown copyright, Ministry of Business, Innovation and Employment; the text is reproduced
under CC BY 3.0 NZ, and sources.toml carries the attribution. Pages are fetched once into
data/, which is not committed.

NOTE: where the manual does not keep a version, the one before it stays in force here until
the next one it keeps. The archive is what the manual holds, not a register of every change.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, timedelta
from pathlib import Path

from provrag.guidance import text_lines
from provrag.legislation import get, intervals

BASE = "https://www.immigration.govt.nz/opsmanual/"
CACHE = Path("data/opsmanual")
_DATE = r"\(?(\d{1,2})/(\d{1,2})/(\d{4})\)?"
_VERSION = re.compile(r"\s*\((\d{1,2})/(\d{1,2})/(\d{4})\)\s*$")
_ENDED = re.compile(rf"\s*\((to|revoked)\s+{_DATE}\)\s*$", re.I)
_HEADING = re.compile(r'<(p|h\d) id="t\d+" class="heading\d">(.*?)</\1>', re.S)
_EFFECTIVE = re.compile(rf'<p class="effectivedate">\s*Effective(?:\s+Date)?:?\s*{_DATE}')
_CODE = re.compile(r"[A-Z]{1,3}(?:\d+(?:\.\d+)*)?(?=\s)")


def iso(day: str, month: str, year: str) -> str:
    return date(int(year), int(month), int(day)).isoformat()


def cached(name: str, cache: Path) -> bytes:
    path = cache / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(get(BASE + name))
    return path.read_bytes()


def _flat_table(match: re.Match) -> str:
    """A table row on one line, its cells separated by bars."""
    table = re.sub(r"<li\b[^>]*>", "; ", match.group(0))
    table = re.sub(r"</?(p|br|ol|ul|li|div|strong)\b[^>]*>", " ", table)
    return re.sub(r"<t[dh]\b[^>]*>", " | ", table)


def page(body: str) -> dict | None:
    """Title, effective date and sections of one instruction page; None for a page with no
    effective date, which is an index of other pages or an undated note.

    NOTE: a table nested in a table would be cut at the inner table's end; the chosen pages
    have none.
    """
    heading = _HEADING.search(body)
    effective = _EFFECTIVE.search(body)
    if heading is None or effective is None:
        return None
    title = " ".join(html.unescape(re.sub(r"<[^>]+>", "", heading.group(2))).split())
    fragment = " ".join(body[heading.end() : effective.start()].split())  # tags make the lines
    fragment = re.sub(r"<table\b.*?</table>", _flat_table, fragment, flags=re.S)
    fragment = re.sub(r'<p class="headingopsmanual">', "<h4>", fragment)
    sections, sub, lines = [], "", []
    for line in text_lines(fragment):
        if line.startswith("## "):
            if lines:
                sections.append({"heading": sub, "text": "\n".join(lines)})
            sub, lines = line[3:], []
        else:
            lines.append(line)
    if lines:
        sections.append({"heading": sub, "text": "\n".join(lines)})
    return {"title": title, "effective": iso(*effective.groups()), "sections": sections}


def code(title: str) -> str:
    """SR3.10 from "SR3.10 Summary of requirements", WD from "WD Post-Study work instructions"."""
    return _CODE.match(title).group()


def parts(p: dict) -> dict[tuple[str, str], dict[str, str]]:
    """One part per section of a page: the text before the first heading is the instruction
    itself (part ""), SR3.10.5 is part "5" of SR3.10, and the second heading with no code of
    its own is part "#2"."""
    section = code(p["title"])
    title = _ENDED.sub("", _VERSION.sub("", p["title"]))
    out = {}
    for n, s in enumerate(p["sections"]):
        sub = _CODE.match(s["heading"])
        part = f"#{n}" if s["heading"] else ""
        if sub and sub.group().startswith(f"{section}."):
            part = sub.group().removeprefix(f"{section}.")
        if (section, part) in out:
            raise ValueError(f"two sections {section} {part!r} on {p['title']}")
        heading = " / ".join(h for h in (title, s["heading"]) if h)
        out[(section, part)] = {"heading": heading, "text": s["text"]}
    return out


def slots(nodes: list[dict]) -> list[tuple[dict, list[dict]]]:
    """Every slot under the given TOC nodes with its archived versions, current page first.

    A version is a child whose title ends with a date, or one with no children of its own
    that says when it ended: the last version of a series the slot has since replaced."""
    found = []
    for node in nodes:
        children = node.get("children", [])
        versions = [
            c
            for c in children
            if _VERSION.search(c["text"]) or (_ENDED.search(c["text"]) and not c.get("children"))
        ]
        found.append((node, versions))
        found += slots([c for c in children if c not in versions])
    return found


def ends(title: str) -> str | None:
    """The first day a slot no longer applies, from "(to d/m/y)" or "(revoked d/m/y)"."""
    match = _ENDED.search(title)
    if match is None:
        return None
    day = date.fromisoformat(iso(*match.groups()[1:]))
    return (day + timedelta(days=1) if match.group(1).lower() == "to" else day).isoformat()


def rows(toc: list[dict], roots: list[str], cache: Path) -> list[dict]:
    chosen = [n for n in _walk(toc) if n["url"] in roots]
    out = []
    for slot, versions in slots(chosen):
        pages: dict[str, tuple[dict, str | None]] = {}
        for node in [slot, *versions]:
            p = page(cached(node["url"], cache).decode("utf-8-sig"))
            if p is not None:  # the current page wins a shared date
                pages.setdefault(p["effective"], (parts(p), ends(node["text"])))
        if not pages:
            continue
        starts = sorted(pages)
        dated = {start: pages[start][0] for start in starts}
        for start, following in zip(starts, [*starts[1:], None], strict=True):
            end = pages[start][1]
            if end is not None and (following is None or end < following):
                dated[end] = {}  # nothing in force from the end until the next version
        out += intervals(dated)
    return sorted(out, key=lambda r: (_order(r["section"]), _order(r["part"]), r["valid_from"]))


def _walk(nodes: list[dict]):
    for node in nodes:
        yield node
        yield from _walk(node.get("children", []))


def _order(label: str) -> list:
    return [(0, int(t), "") if t.isdigit() else (1, 0, t) for t in re.findall(r"\d+|\D+", label)]


def build(roots: list[str], cache: Path) -> list[dict]:
    toc = json.loads(cached("toc.json", cache))
    return rows(toc, roots, cache)
