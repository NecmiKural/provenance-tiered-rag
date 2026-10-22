-- The index. Recreated by `provrag index`: everything here is rebuilt from corpus/.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gist;

DROP SCHEMA IF EXISTS corpus CASCADE;

-- Roles are cluster-wide, so create them only once.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'provrag_reader') THEN
        CREATE ROLE provrag_reader NOLOGIN;
    END IF;
END
$$;

CREATE SCHEMA corpus;

CREATE TABLE corpus.chunk (
    id           text PRIMARY KEY,
    source       text NOT NULL,
    tier         text NOT NULL CHECK (tier IN ('T1', 'T2', 'T3')),
    jurisdiction text NOT NULL,
    pack         text NOT NULL,
    section_key  text NOT NULL,
    part         text NOT NULL,
    heading      text NOT NULL,
    body         text NOT NULL,
    valid        daterange NOT NULL CHECK (NOT isempty(valid)),
    hidden_text  boolean NOT NULL,
    -- Stemmed in the language of the jurisdiction's law.
    search       tsvector GENERATED ALWAYS AS (to_tsvector(
                     CASE jurisdiction WHEN 'DE' THEN 'german'::regconfig ELSE 'english'::regconfig END,
                     heading || ' ' || body)) STORED,
    embedding    vector(768) NOT NULL,
    -- One text per provision on any day: overlapping versions are refused here, not in code.
    EXCLUDE USING gist (source WITH =, section_key WITH =, part WITH =, valid WITH &&)
);

CREATE INDEX chunk_search ON corpus.chunk USING gin (search);

-- Answering reads the index and nothing else.
GRANT USAGE ON SCHEMA corpus TO provrag_reader;
GRANT SELECT ON corpus.chunk TO provrag_reader;
