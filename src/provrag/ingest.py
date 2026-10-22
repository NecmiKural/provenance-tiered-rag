"""Corpus rows to index chunks: normalised text, tier, dates and an embedding each."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import psycopg

from provrag import legislation
from provrag.embed import Embedder, vector_literal
from provrag.packs import PACK_OF_SOURCE

# Characters that can carry or reorder text a reader does not see: Unicode tag characters
# (used to smuggle ASCII instructions) and bidirectional overrides and isolates.
_TAGS = range(0xE0000, 0xE0080)
_BIDI = {chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A))}


def normalise(text: str) -> tuple[str, bool]:
    """NFKC, then drop every invisible format character. Returns the clean text and whether
    any removed character could have hidden or reordered text.

    Plain zero-width spaces and joiners are dropped without a flag: statute text uses them as
    typesetting hints.
    """
    text = unicodedata.normalize("NFKC", text)
    hidden = any(ord(c) in _TAGS or c in _BIDI for c in text)
    clean = "".join(c for c in text if unicodedata.category(c) != "Cf")
    return clean, hidden


@dataclass(frozen=True)
class Chunk:
    """One provision as it read between two dates. NOTE: a chunk is one subsection; the
    longest is about a thousand tokens, within the embedding model's input. A corpus with
    longer passages would split them by paragraph."""

    id: str
    source: str
    tier: str
    jurisdiction: str
    section: str
    part: str
    heading: str
    body: str
    valid_from: str
    valid_to: str | None
    hidden_text: bool

    def embed_text(self) -> str:
        return f"{self.heading}\n{self.body}"


def locator(source: dict, row: dict) -> str:
    """s8(1) for a New Zealand subsection, §19(1) for a German paragraph, SR3.10.5 for a part
    of an immigration instruction, page#3 for the third heading of a guidance page, and the
    note id for a note."""
    if "act" in source:
        return f"s{row['section']}" + (f"({row['part']})" if row["part"] else "")
    if "gii" in source:  # § 19(1), or § 4 Nr. 8 for a numbered item
        part = row["part"]
        return f"§{row['section']}" + (
            f" {part}" if part.startswith("Nr") else f"({part})" if part else ""
        )
    if "opsmanual" in source:  # a heading with no code of its own has part "#2"
        part = row["part"]
        return row["section"] + (part if not part or part.startswith("#") else f".{part}")
    return f"{row['section']}#{row['part']}" if row["part"] else row["section"]


def source_chunks(source: dict, root: Path = Path(".")) -> list[Chunk]:
    chunks = []
    for row in legislation.read_jsonl(root / source["path"]):
        heading, hidden_heading = normalise(row["heading"])
        body, hidden_body = normalise(row["text"])
        chunks.append(
            Chunk(
                id=f"{source['id']}:{locator(source, row)}@{row['valid_from']}",
                source=source["id"],
                tier=source["tier"],
                jurisdiction=source["jurisdiction"],
                section=row["section"],
                part=row["part"],
                heading=heading,
                body=body,
                valid_from=row["valid_from"],
                valid_to=row["valid_to"],
                hidden_text=hidden_heading or hidden_body,
            )
        )
    return chunks


INSERT_SQL = """
INSERT INTO corpus.chunk (id, source, tier, jurisdiction, pack, section_key, part, heading,
                          body, valid, hidden_text, embedding)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, daterange(%s, %s, '[)'), %s, %s::vector)
"""


def load(conn: psycopg.Connection, chunks: list[Chunk], embed: Embedder) -> None:
    vectors = embed([c.embed_text() for c in chunks])
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            INSERT_SQL,
            [
                (
                    c.id,
                    c.source,
                    c.tier,
                    c.jurisdiction,
                    PACK_OF_SOURCE[c.source],
                    c.section,
                    c.part,
                    c.heading,
                    c.body,
                    c.valid_from,
                    c.valid_to,
                    c.hidden_text,
                    vector_literal(vectors[c.embed_text()]),
                )
                for c in chunks
            ],
        )
