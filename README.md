# Provenance-Tiered RAG

Question answering over New Zealand GST law that knows where each passage comes from and when it was in force. Statute outranks official guidance, which outranks untrusted notes; every answer cites passages valid on the date asked about, and code checks that every number in the answer appears in a cited statute or guidance passage.

**Work in progress.** The corpus and the index are in place; retrieval, answering and the evaluation follow. No results are reported yet.

## Corpus

`provrag fetch` downloads every consolidated version of the Goods and Services Tax Act 1985 from 3 September 2007 to 30 June 2026 from [legislation.govt.nz](https://www.legislation.govt.nz), keeps chosen sections, cuts them into subsections and gives each distinct subsection text the dates during which the consolidations show it unchanged. The result is committed in `corpus/nz/gst-act.jsonl`; `sources.toml` lists each source with its tier, licence and checksum. There is no copyright in New Zealand legislation (Copyright Act 1994, s 27).

## Index

`provrag index` loads every chunk into Postgres with its tier, its in-force dates as a `daterange`, a full-text vector and an embedding (`gemini-embedding-2`, 768 dimensions, pgvector). Postgres refuses two texts of one provision on the same day with an exclusion constraint, and answering will run under a role that can only read. Text is NFKC-normalised and stripped of invisible format characters; characters that can hide or reorder text (Unicode tags, bidirectional overrides) are flagged. The vectors are committed in `corpus/embeddings/`, keyed by the hash of each text, so indexing and CI need no key.

```bash
make db      # Postgres 17 with pgvector on localhost:5434
make index   # recreate the index from corpus/, offline
make test
```

> Not tax advice. A portfolio project; the questions, notes and evaluation are written for it.

---
*Personal portfolio project, MIT licensed.*
