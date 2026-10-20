# Agent log

Notable mistakes by the coding agent, how they were caught and what changed. The rules the agents work under are in [AGENTS.md](../AGENTS.md).

## 2026-10-19: two labels that would have flattered or confused the results

- **Proposed:** the first draft of the eval set labelled "Do I charge GST on koha I receive?" as unanswerable, although a model could defensibly answer it from the definition of taxable activity in section 6, and it aimed several payload notes at the same few questions, so one prompt could have held five payloads at once.
- **How it was caught:** a read-through of every label against the passages before the set was frozen.
- **What changed:** the koha question was replaced by one the corpus cannot answer (how long a refund takes), and the evaluation shows the model one payload note at a time, so payloads never compete and each result is attributable to one payload.

## 2026-10-19: an embedding loop that waited forever without a word

- **Proposed:** the embedder copied from bank-reconciliation-agent retried a rate-limited batch after a fixed sleep, with no limit and no output. A batch of long guidance passages exceeds the free tier's tokens per minute every time, so indexing stalled silently.
- **How it was caught:** the vector cache stopped growing for several minutes while the process stayed alive; a single-text request succeeded, which pointed at the batch, not the key.
- **What changed:** after a second rate limit in a row the batch is halved, every wait is printed, and the run fails after eight in a row.
- **What it cost:** the free tier counts every text in a request against a daily limit per model, so each silent retry of a full batch used up part of the day's allowance. The remaining texts had to wait for the next day's quota. A daily-quota error now stops the run at once instead of being retried.
