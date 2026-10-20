"""Inland Revenue GST guidance pages, cut into one chunk per heading.

Inland Revenue licenses the text of its website under Creative Commons Attribution 4.0
International, provided it is reproduced accurately with its source and copyright status;
logos, design elements and images are excluded. Only text is kept here, verbatim apart from
whitespace, and `sources.toml` carries the attribution.

NOTE: a guidance page has no dated versions, only a "last updated" date. A chunk is treated as
valid from that date onward, so guidance never answers a question about an earlier date even
where the page's content was true then. Historical questions rest on the statute alone.
"""

from __future__ import annotations

import html
import re
from datetime import datetime

from provrag.legislation import get

BASE = "https://www.ird.govt.nz"
_START = '<div class="field-content">'
_ENDS = ("link-block-related", 'class="ir-print-date"')
_UPDATED = re.compile(r"Last updated:?\s*(?:<[^>]+>\s*)*(\d{1,2} [A-Z][a-z]{2} \d{4})")
_TITLE = re.compile(r'<h1 class="divider">(.*?)</h1>', re.S)


def text_lines(fragment: str) -> list[str]:
    """Visible text, one block per line, headings marked with '## ' and list items with '- '."""
    fragment = re.sub(r"<(script|style)\b.*?</\1>", "", fragment, flags=re.S)
    fragment = re.sub(r"<h[1-4][^>]*>", "\n## ", fragment)
    fragment = re.sub(r"<li[^>]*>", "\n- ", fragment)
    fragment = re.sub(r"<(p|br|div|tr|td|th|table)\b[^>]*>", "\n", fragment)
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return [line for line in lines if line and line not in ("##", "-")]


def page(slug: str, body: str) -> dict:
    """Title, last-updated date and heading sections of one guidance page."""
    title_lines = text_lines(_TITLE.search(body).group(1))
    updated = datetime.strptime(_UPDATED.search(body).group(1), "%d %b %Y").date().isoformat()
    start = body.index(_START, body.index('<h1 class="divider">'))
    end = min(i for marker in _ENDS if (i := body.find(marker, start)) != -1)
    end = body.rfind("<", start, end)  # the marker sits inside a tag; cut before the tag
    sections, heading, lines = [], "", []
    for line in text_lines(body[start:end]):
        if line.startswith("## "):
            if lines:
                sections.append({"heading": heading, "text": "\n".join(lines)})
            heading, lines = line[3:], []
        else:
            lines.append(line)
    if lines:
        sections.append({"heading": heading, "text": "\n".join(lines)})
    return {"slug": slug, "title": title_lines[-1], "updated": updated, "sections": sections}


def rows(pages: list[dict]) -> list[dict]:
    """Corpus rows in the statute's shape: one per heading section, valid from the update."""
    out = []
    for p in pages:
        for n, section in enumerate(p["sections"], 1):
            out.append(
                {
                    "section": p["slug"],
                    "part": str(n),
                    "heading": " / ".join(h for h in (p["title"], section["heading"]) if h),
                    "text": section["text"],
                    "valid_from": p["updated"],
                    "valid_to": None,
                }
            )
    return out


def build(slugs: list[str]) -> list[dict]:
    return rows([page(slug, get(f"{BASE}/gst/{slug}").decode()) for slug in slugs])
