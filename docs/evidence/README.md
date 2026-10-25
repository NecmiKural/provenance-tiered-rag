---
title: Provenance-Tiered RAG evidence
emoji: ⚖️
colorFrom: blue
colorTo: gray
sdk: static
app_file: index.html
pinned: true
short_description: Recorded answers with the dated passages they cite
license: mit
tags:
  - rag
  - retrieval
  - evaluation
  - prompt-injection
  - legal
---

# Provenance-Tiered RAG evidence

A static viewer for the recorded evaluation runs of [provenance-tiered-rag](https://github.com/NecmiKural/provenance-tiered-rag): question answering over New Zealand GST law, German VAT law and New Zealand immigration instructions, where code checks every citation and figure against passages in force on the date asked about. Pick a question to see the answer the user saw, each claim with the passage it cites, the tier of that passage (statute, official guidance or untrusted note), the dates it was in force, and any draft the verifier rejected. Questions with a planted note show the attack and whether it got through.

- **Replayed from recorded runs, not live.** Nothing on this page calls a model, and it needs no key. The files are written by `provrag evidence` from the runs the README reports, and `tests/test_evidence.py` fails if any case differs from its recorded row in `results/*.json`.
- **Information, not tax or immigration advice.** The questions, notes and evaluation were written for a portfolio project.
- The page loads only its own files: no third-party script, font or request.

Personal project. Code under the MIT licence; quoted source text under the terms in [LICENSE.md](LICENSE.md).
