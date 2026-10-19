# Provenance-Tiered RAG

Question answering over New Zealand GST law that knows where each passage comes from and when it was in force. Statute outranks official guidance, which outranks untrusted notes; every answer cites passages valid on the date asked about, and code checks that every number in the answer appears in a cited statute or guidance passage.

**Work in progress.** The corpus builder is in place; indexing, answering and the evaluation follow. No results are reported yet.

## Corpus

`provrag fetch` downloads every consolidated version of the Goods and Services Tax Act 1985 from 3 September 2007 to 30 June 2026 from [legislation.govt.nz](https://www.legislation.govt.nz), keeps chosen sections, cuts them into subsections and gives each distinct subsection text the dates during which the consolidations show it unchanged. The result is committed in `corpus/nz/gst-act.jsonl`; `sources.toml` lists each source with its tier, licence and checksum. There is no copyright in New Zealand legislation (Copyright Act 1994, s 27).

> Not tax advice. A portfolio project; the questions, notes and evaluation are written for it.

---
*Personal portfolio project, MIT licensed.*
