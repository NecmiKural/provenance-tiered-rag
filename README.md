# Provenance-Tiered RAG

Question answering over New Zealand GST law that knows where each passage comes from and when it was in force. Statute outranks official guidance, which outranks untrusted notes; every answer cites passages valid on the date asked about, and code checks that every number in the answer appears in a cited statute or guidance passage.

**Work in progress.** The corpus, the index, the frozen eval set and retrieval are in place; answering, the verifier and the evaluation follow. No results are reported yet.

## Corpus

Three tiers, each with dates. `sources.toml` lists every source with its tier, licence and checksum.

| Tier | Source | In force | Licence |
|---|---|---|---|
| T1 statute | Goods and Services Tax Act 1985, seventeen sections, every consolidation from 3 September 2007 to 30 June 2026 ([legislation.govt.nz](https://www.legislation.govt.nz)) | between the consolidations that show each subsection's text | no copyright in New Zealand legislation (Copyright Act 1994, s 27) |
| T2 guidance | Inland Revenue GST pages ([ird.govt.nz/gst](https://www.ird.govt.nz/gst)), one chunk per heading | from each page's "last updated" date | Crown copyright, Inland Revenue, text reproduced under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); logos and images excluded |
| T3 notes | forum posts and practitioner notes written for this project, some carrying prompt-injection payloads | from their posting date | MIT, as part of this repository |

`provrag fetch` rebuilds T1 and T2 from the sites: every consolidated version of the Act in the range, cut into subsections with each distinct text dated by the consolidations that show it, and the guidance pages cut at their headings. T2 text is kept verbatim apart from whitespace. A guidance page has no dated versions, so it is used only for dates on or after its last update; questions about earlier dates rest on the statute alone.

## Eval set

Written before any prompt, then frozen: `tests/test_evals.py` pins the checksum of every file, and the `evals-frozen` tag marks the commit.

- `evals/questions.jsonl`: answerable questions in plain words, labelled with the passages that support them (by section or guidance heading, valid on the question's date) and the numbers a right answer must contain; questions the corpus cannot answer, including dates before it begins; and arithmetic questions, which the system should refuse because it does no arithmetic.
- `evals/questions-held-back.jsonl`: about a quarter of the questions of every kind, held back from tuning and run once at the end.
- `evals/payloads.jsonl`: the payload planted in each T3 note, with its goal (a wrong figure, being cited, leaking the prompt, refusing an answerable question, adding an off-topic link), its style (plain imperative, fake authority, invisible Unicode tag characters, fake closing tags, ordinary conversation), the question it targets and a canary code can detect. Evaluation shows the model one payload note at a time, so payloads never compete.

Oracle tests check, with no model, that every gold passage exists and is in force on the question's date, that every expected number is in it as the same typed number, that every payload note is posted before its target's date, and that every planted figure is wrong for its target.

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
