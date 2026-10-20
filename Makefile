# Common tasks.
.PHONY: db test fetch index eval ablate record-slice demo

db:
	docker compose up -d --wait

test: db
	uv run pytest

# Rebuilds corpus/ from legislation.govt.nz; the result should match the committed checksums.
fetch:
	uv run provrag fetch

# Recreates the index from corpus/ with the committed vectors; no key needed. After a corpus
# change, `uv run --env-file .env provrag index` embeds the new texts.
index: db
	uv run provrag index

# Live, three repeats, clean and attacked; writes results/<date>-eval-<model>-<defences>-record.json.
eval: db
	uv run --env-file .env provrag eval --repeats 3

# The defences switched off, all together over three repeats and one at a time once.
ablate: db
	uv run --env-file .env provrag eval --defences off --repeats 3
	for d in fence_off notes_rule_off verifier_off normalise_off; do \
		uv run --env-file .env provrag eval --defences $$d --repeats 1; done

# Re-record the slice CI replays. Needed after any change to the prompt, retrieval or data.
record-slice: db
	rm -f tests/cassettes/slice.jsonl
	uv run --env-file .env provrag eval --repeats 1 --every 6 --cassette tests/cassettes/slice.jsonl \
		--out tests/cassettes --name slice

# Offline: replays the committed slice, no key needed.
demo: db
	uv run provrag eval --mode replay --repeats 1 --every 6 --cassette tests/cassettes/slice.jsonl \
		--out runs --name demo
