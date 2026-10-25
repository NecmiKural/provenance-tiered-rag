---
license: mit
language:
  - en
  - de
pretty_name: Provenance-Tiered RAG eval set
task_categories:
  - question-answering
tags:
  - rag
  - retrieval
  - evaluation
  - prompt-injection
  - legal
size_categories:
  - n<1K
configs:
  - config_name: nz-gst
    data_files:
      - split: development
        path: nz-gst/questions.jsonl
      - split: held_back
        path: nz-gst/questions-held-back.jsonl
  - config_name: nz-gst-payloads
    data_files:
      - split: payloads
        path: nz-gst/payloads.jsonl
  - config_name: de-vat
    data_files:
      - split: development
        path: de-vat/questions.jsonl
      - split: held_back
        path: de-vat/questions-held-back.jsonl
  - config_name: de-vat-payloads
    data_files:
      - split: payloads
        path: de-vat/payloads.jsonl
  - config_name: nz-immigration
    data_files:
      - split: development
        path: nz-immigration/questions.jsonl
      - split: held_back
        path: nz-immigration/questions-held-back.jsonl
  - config_name: nz-immigration-payloads
    data_files:
      - split: payloads
        path: nz-immigration/payloads.jsonl
---

# Provenance-Tiered RAG eval set

The frozen questions and planted payloads that [provenance-tiered-rag](https://github.com/NecmiKural/provenance-tiered-rag) is measured on: question answering over New Zealand GST law, German VAT law and Immigration New Zealand's Operational Manual, where code checks every citation and figure against passages in force on the date asked about. The recorded answers to these questions, with the passages they cite, are in the [evidence viewer](https://huggingface.co/spaces/necmikural/provenance-rag-evidence).

Each body of law is a pack with two configs: its questions (`development` and `held_back` splits) and its payloads. Every file was written before any prompt for its pack and then frozen; the tags [`evals-frozen`](https://github.com/NecmiKural/provenance-tiered-rag/tree/evals-frozen), [`evals-de-frozen`](https://github.com/NecmiKural/provenance-tiered-rag/tree/evals-de-frozen) and [`evals-nz-immigration-frozen`](https://github.com/NecmiKural/provenance-tiered-rag/tree/evals-nz-immigration-frozen) mark them, and the repository's tests pin each file's checksum. The `held_back` split was kept out of prompt and retrieval choices and run once at the end.

## Questions

| Field | Meaning |
|---|---|
| `id` | Question id, unique within its pack |
| `question` | The question in plain words, in the language of the law (German for `de-vat`) |
| `as_of` | The date the question is asked on; only passages in force on that date count |
| `kind` | `answerable`; `unanswerable` (not covered by the sources); `calculation` (needs arithmetic the sources do not state); `advice` (the asker's own immigration case). Every kind but `answerable` should be refused |
| `expect` | Figures a right answer must state, as written in the law (empty when none) |
| `gold` | Passages that support the answer, as `source:locator` without a date, so whichever version was in force on `as_of` counts |
| `origin` | Where the question came from: `statute`, `guidance` or `written` |

The passages behind `gold` are not in this dataset: the corpus, with each source's tier, licence and dates, is in the repository's `corpus/` and `sources.toml`.

## Payloads

Each payload is planted in one untrusted note (tier T3) and shown to the model with the question it targets, one at a time.

| Field | Meaning |
|---|---|
| `note` | Id of the note that carries it |
| `target` | Id of the question it is shown with |
| `goal` | `wrong_fact`, `cite_payload`, `leak`, `wrongful_refusal` or `off_task` |
| `style` | `imperative`, `authority`, `conversational`, `hidden` (invisible Unicode tag characters) or `markup` (fake closing tags) |
| `instruction` | The text of the attack, as a reader would see it |
| `canary` | What code looks for to decide that the attack got through: a typed figure for `wrong_fact`, a marker string for `leak` and `off_task`, the note itself for `cite_payload`; empty for `wrongful_refusal`, which is judged by the refusal |

These are prompt-injection attacks written to test the defences; they target a question-answering prompt about tax and immigration rules, and they are shown here as data.

## Use and limits

Not tax or immigration advice: the questions, notes and payloads were written for a portfolio project. Scores depend on the corpus, retrieval and verifier in the repository, and the README there says what the numbers do not show. Questions and payloads are under the MIT licence; the law and guidance they refer to are under their own terms, listed in `sources.toml`.
