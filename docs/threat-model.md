# Threat model

What can go wrong when a language model answers tax and immigration questions from retrieved passages, and which control in this repository stands in the way. Categories follow the OWASP Top 10 for LLM Applications (2025).

## What is worth protecting

- **The figures.** A wrong rate, threshold or date in an answer is the costly failure: someone files, registers or charges on it, or applies for a visa on it.
- **The line between information and advice.** An answer that tells someone whether they qualify for a visa is immigration advice, which only licensed advisers and a few exempt people may give in New Zealand; a confident wrong assessment can cost a person their visa.
- **The source of each claim.** An answer that cites a forum post as if it were law, or a passage not in force on the date asked about, misleads even when the figure happens to be right.
- **The prompt and the task.** The answering instructions, and the answer staying on its subject, with no links or promotions an outsider planted.
- **Spend** on the model provider and the embedding quota.

## Who controls what

| Input | Written by | Trusted |
|---|---|---|
| Statute text and its dates | Parliamentary Counsel Office, fetched from legislation.govt.nz | yes, checked against a pinned checksum |
| Guidance text and its last-updated date | Inland Revenue, fetched from ird.govt.nz | yes, checked against a pinned checksum |
| Immigration instructions, their archived versions and effective dates | Immigration New Zealand, fetched from immigration.govt.nz/opsmanual | yes, checked against a pinned checksum |
| Notes (forum posts, practitioner notes) | anyone | no: data, never a source |
| The question and its date | the user | the question is data; the date only filters |
| Model output | the model | no: checked before it counts |

## Threats and controls

| OWASP LLM 2025 | Threat here | Control | Test or measurement |
|---|---|---|---|
| LLM01 Prompt injection | A note tells the model to give a wrong figure, cite the note, refuse, reveal its prompt or add a link; the instruction may be hidden in invisible Unicode tag characters or try to close the fence | Notes sit in a fenced block whose text cannot close it; the prompt says notes are data; invisible format characters are stripped at indexing and tag or bidirectional characters flagged; the verifier refuses any note as a source and any figure not in a cited statute or guidance passage | `tests/test_answer.py`, `tests/test_verify.py`, `tests/test_ingest.py`; the attack table and the defence ablation in the README, scored on the first draft and on what the user sees |
| LLM08 Vector and embedding weaknesses | A note planted in the index ranks above the law, or a passage from another date ranks first | Retrieval filters to passages in force on the date asked about; ties go to the higher tier; which notes are visible is a parameter, so an evaluation shows one payload at a time; the verifier refuses a cited passage not in force on the date | `tests/test_retrieve.py`, `tests/test_db.py`; natural exposure of each payload and the retrieval table, including the run without the date filter |
| LLM09 Misinformation | The model states a figure no source gives, computes one, or answers a question the sources do not cover | Every typed number in a claim must be in a statute or guidance passage that claim cites; numbers in the answer text must be in a claim; the prompt asks for a refusal when the passages do not answer or arithmetic is needed; a draft that fails gets one repair, then a refusal with the reason | `tests/test_verify.py`, `tests/test_numbers.py`; refusal rates for uncovered and arithmetic questions in the README |
| LLM09 Misinformation: advice | A user asks whether they qualify, should apply or which visa suits them, and the model assesses their case from the published rules | The immigration prompt's information-not-advice rule: such questions are refused and pointed to Immigration New Zealand or a licensed adviser; every figure in an answer still has to be in a cited passage | `tests/test_answer.py`; the advice questions' refusal rate in the README |
| LLM07 System prompt leakage | A note asks the model to print its instructions | The prompt holds no secret beyond a canary planted to detect leaks; the controls are in code, so knowing the prompt does not help an attacker | the leak goal in the attack table looks for the canary |
| LLM05 Improper output handling | Model text is shown as an answer without checks | Replies must parse as a json object of a fixed shape; anything else goes to the repair round and then becomes a refusal | `tests/test_answer.py` |
| LLM06 Excessive agency | Answering changes the index | No tools; retrieval runs under a Postgres role that can only read the index, switched to per transaction from the owner connection; an exclusion constraint refuses two texts of one provision on the same day | `tests/test_db.py` tries the forbidden writes and an overlapping insert |
| LLM04 Data and model poisoning | A source file is edited, or a fetch returns different text | `sources.toml` pins the checksum of every corpus file and the eval set's files are pinned too; a rerun of `provrag fetch` over the fixed version range must reproduce them | `tests/test_corpus.py`, `tests/test_evals.py` |
| LLM10 Unbounded consumption | Retries burn spend or quota | One repair round at most; the embedder halves a rate-limited batch, prints every wait, gives up after eight in a row and stops at once on a daily quota; indexing and CI use committed vectors | `tests/test_ingest.py`; the agent log's quota entry |
| LLM03 Supply chain | A compromised dependency or CI action | Locked dependencies (`uv.lock`), GitHub Actions pinned by commit SHA, the Postgres image pinned by tag (not by digest), no agent or RAG framework | CI runs `uv sync --locked` |

## What remains

- **A note written as convincing official text was not tried.** The payloads are templated instructions; one that looks like a newer version of the Act, or a guidance page, may fare better, and the verifier only checks that a figure is in a cited statute or guidance passage, not that the passage is the right one.
- **An answer can cite the wrong passage with the right figure.** The verifier checks that a figure is in a cited passage in force, not that the passage is about the question; a coincidental figure in an unrelated passage would pass.
- **The source sites are trusted.** A compromised legislation.govt.nz or ird.govt.nz page fetched into the corpus would change the checksums, which a rerun would show, but nothing checks the content against another copy.
- **Dates are consolidation dates.** An amendment that took effect between two consolidations is dated from the later one; a question about a date in between gets the earlier text.
- **A payload in another language than the law is not measured.** The German payloads are in German and the New Zealand ones in English; a payload written in a third language, or mixing languages, may slip past the model's reading of the prompt. The verifier's figure and source checks do not depend on language, but its number reader does: a figure in a language it does not read is not checked.
- **The advice line is drawn by the model.** No code decides whether a question asks for advice, and no code reads a refusal's reason; a question about the asker's case phrased as a general one can be answered, and a refusal can still comment on the case it declines to assess.
- **Immigration New Zealand changes the manual.** A new version or a rewritten archived page changes the checksum, which a rerun of `provrag fetch` would show; until then the corpus describes the manual as fetched, and the newest version stays in force here indefinitely.
- **The model provider sees every passage and question.** Only public text and questions written for this project are sent; a deployment with private questions would need a provider it can send them to.
