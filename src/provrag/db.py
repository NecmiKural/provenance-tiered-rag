"""Postgres access: the index schema and least-privilege role switching."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files

import psycopg
from psycopg import sql

DEFAULT_URL = "postgresql://provrag:provrag@localhost:5434/provrag"  # the compose.yaml service
# A name of its own, so an .env shared with another project cannot point this one at the
# wrong database: `provrag index` recreates its schema.
URL_ENV = "PROVRAG_DATABASE_URL"
ROLES = ("provrag_reader",)


def connect(url: str | None = None) -> psycopg.Connection:
    url = url or os.environ.get(URL_ENV) or DEFAULT_URL
    return psycopg.connect(url, autocommit=True)


def reset(conn: psycopg.Connection) -> None:
    conn.execute(files("provrag").joinpath("schema.sql").read_text())


@contextmanager
def as_role(conn: psycopg.Connection, role: str) -> Iterator[psycopg.Connection]:
    """Run a block in its own transaction with only the privileges of `role`.

    NOTE: the owner connection switches role with SET LOCAL ROLE, which code that runs
    arbitrary SQL could undo. Nothing here takes SQL from the model. A deployment would give
    the answering process its own login that is a member of provrag_reader only.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    with conn.transaction():
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        yield conn
