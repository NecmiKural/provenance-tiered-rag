"""The index enforces its own rules in Postgres: one text per provision per day, read-only
answering, and dates that pick the law in force."""

import psycopg
import pytest

from provrag import cli, db

IN_FORCE_SQL = """
SELECT body FROM corpus.chunk
WHERE source = 'nz-gst-act' AND section_key = %s AND part = %s AND valid @> %s::date
"""


def test_every_chunk_is_indexed(conn):
    assert conn.execute("SELECT count(*) FROM corpus.chunk").fetchone()[0] == len(
        cli.corpus_chunks()
    )


@pytest.mark.parametrize(
    ("day", "rate"), [("2010-09-30", "12.5 percent"), ("2010-10-01", "15 percent")]
)
def test_the_reader_sees_the_rate_in_force_on_the_day(conn, day, rate):
    with db.as_role(conn, "provrag_reader"):
        (body,) = conn.execute(IN_FORCE_SQL, ["8", "1", day]).fetchall()
    assert f"rate of {rate}" in body[0]


def test_an_overlapping_version_of_a_provision_is_refused(conn):
    row = conn.execute(
        "SELECT * FROM corpus.chunk WHERE id = 'nz-gst-act:s8(1)@2010-10-01'"
    ).fetchone()
    assert row is not None
    with pytest.raises(psycopg.errors.ExclusionViolation), conn.transaction():
        conn.execute(
            "INSERT INTO corpus.chunk (id, source, tier, jurisdiction, section_key, part,"
            " heading, body, valid, hidden_text, embedding)"
            " SELECT 'overlap', source, tier, jurisdiction, section_key, part, heading,"
            " 'a different text', daterange('2011-01-01', NULL), hidden_text, embedding"
            " FROM corpus.chunk WHERE id = 'nz-gst-act:s8(1)@2010-10-01'"
        )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO corpus.chunk (id) VALUES ('x')",
        "UPDATE corpus.chunk SET body = 'rate of 0%'",
        "DELETE FROM corpus.chunk",
        "TRUNCATE corpus.chunk",
    ],
)
def test_the_reader_cannot_change_the_index(conn, statement):
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.as_role(conn, "provrag_reader"):
        conn.execute(statement)


def test_role_switch_rejects_unknown_roles(conn):
    with pytest.raises(ValueError), db.as_role(conn, "postgres"):
        pass
