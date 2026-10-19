# Common tasks.
.PHONY: db test fetch index

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
