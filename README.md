# Provenance-Tiered RAG

Question answering over New Zealand GST law that knows where each passage comes from and when it was in force. Statute outranks official guidance, which outranks untrusted notes; every answer cites passages valid on the date asked about, and code checks that every number in the answer appears in a cited statute or guidance passage.

**Work in progress.** The corpus, the index, the frozen eval set, retrieval, answering and the verifier are in place; the measured evaluation follows. No results are reported yet.

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

## Answering

```
question + date ──► retrieval: full text and pgvector fused by reciprocal rank,
                    only passages in force on the date, ties to the higher tier
               ──► model drafts json: an answer and claims, each citing passage ids
               ──► verifier (code) ──► passes: the answer
                                  └──► fails: the errors go back once ──► passes: the answer
                                                                     └──► fails: a refusal with the reason
```

- **Prompt** ([prompts/answer.md](src/provrag/prompts/answer.md)). Statute and guidance passages are marked with their tier and dates; untrusted notes sit in a fenced block whose text cannot close the fence. The model answers in json and must refuse when the passages do not answer the question for the date, and when an answer would need arithmetic. Each rule has eval cases.
- **Verifier** ([verify.py](src/provrag/verify.py)). In code, with no category chosen by the model: every cited passage was retrieved and was in force on the date; every typed number in a claim (a rate, an amount, a date, a period) is in a statute or guidance passage that claim cites, so "15 days" never supports "15%"; a note is never a source; every number in the answer text is in a claim; the numbers in the question are exempt. A calculated figure appears in no passage, so it cannot pass.
- **Loop** ([answer.py](src/provrag/answer.py)). One draft, at most one repair with the verifier's errors and the fenced passages sent again, then an answer or a refusal that says why. Each defence (the fence, the notes rule, the verifier) can be switched off for the ablation.

```bash
uv run --env-file .env provrag ask "When is the GST return for the period ending 31 March due?"
uv run --env-file .env provrag ask "What was the GST rate?" --as-of 2010-09-30
```

> Not tax advice. A portfolio project; the questions, notes and evaluation are written for it.

---
*Personal portfolio project, MIT licensed.*
