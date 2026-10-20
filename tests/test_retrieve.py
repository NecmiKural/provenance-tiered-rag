"""Retrieval honours the date, the visible notes and the reader role."""

import pytest

from provrag import cli, embed, evalset, retrieve

CHUNKS = {c.id: c for c in cli.corpus_chunks()}
CACHE = embed.read_cache(embed.cache_path(embed.GEMINI))
RATE = "What was the GST rate on 30 September 2010?"


def vector(text: str) -> list[float]:
    return CACHE[embed.text_key(text)]


@pytest.mark.parametrize("method", retrieve.METHODS)
def test_every_hit_is_in_force_on_the_day(conn, method):
    hits = retrieve.search(conn, RATE, vector(RATE), "2010-09-30", [], method=method, k=10)
    assert hits
    assert all(evalset.valid_on(CHUNKS[h.id], "2010-09-30") for h in hits)


def test_the_rate_in_force_is_found_for_a_date(conn):
    hits = retrieve.search(conn, RATE, vector(RATE), "2010-09-30", [], k=5)
    assert "nz-gst-act:s8(1)@2007-09-03" in [h.id for h in hits]


def test_a_note_is_retrieved_only_when_visible(conn):
    question = "What rate of GST is charged on most sales?"
    hidden = retrieve.search(conn, question, vector(question), "2026-10-19", [], k=20)
    shown = retrieve.search(conn, question, vector(question), "2026-10-19", ["P01"], k=20)
    assert not any(CHUNKS[h.id].tier == "T3" for h in hidden)
    assert any(CHUNKS[h.id].section == "P01" for h in shown)


def test_an_unknown_method_is_refused(conn):
    with pytest.raises(ValueError):
        retrieve.search(conn, RATE, vector(RATE), "2010-09-30", [], method="bm25")
