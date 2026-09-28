# X-scraper

Async scraper for X (Twitter) that talks directly to X's internal web
GraphQL API — the same endpoints x.com itself uses to render logged-out
profile and search pages — instead of the paid official API.

## How it avoids the official API

X's web client authenticates unauthenticated ("guest") requests with a
public bearer token embedded in its own JS bundle, exchanged for a
short-lived guest token via `POST /1.1/guest/activate.json`. `x_scraper`
does the same exchange and then calls the same `UserByScreenName`,
`UserTweets`, and `SearchTimeline` GraphQL operations the web app uses.
Optional account cookies (`X_SCRAPER_COOKIES`) raise rate limits / unlock
gated content but aren't required for public profiles and search.

## Performance

- One pooled `httpx.AsyncClient` (HTTP/2) reused across every request —
  no per-request TLS/TCP handshakes.
- Bounded concurrency (semaphore) so many profiles/searches scrape in
  parallel without tripping rate limits.
- Exponential backoff + guest-token auto-refresh on 429/403/5xx.
- SQLite response cache (15 min TTL by default) — reruns of the same
  pipeline cost nothing.

## Local sub-1B model

`x_scraper.local_model` runs a small (~0.5B parameter) instruction model
fully offline via `llama.cpp`, so scraped data never has to leave the
machine for filtering/summarization/sentiment tagging. Default model is
Qwen2.5-0.5B-Instruct, quantized to Q4_K_M (~350MB), fast enough on CPU.

```bash
pip install -r requirements.txt
./scripts/download_model.sh   # fetches the GGUF weights once
```

## Usage

```bash
# Scrape a profile
python -m x_scraper.cli user elonmusk --count 40

# Scrape several profiles concurrently
python -m x_scraper.cli user elonmusk sama --count 20

# Search
python -m x_scraper.cli search "claude code" --count 30

# Filter to on-topic tweets and summarize, entirely on-device
python -m x_scraper.cli user elonmusk --filter-topic "AI safety" --summarize

# Tag sentiment and write JSONL
python -m x_scraper.cli search "claude code" --sentiment --out results.jsonl
```

Set `X_SCRAPER_COOKIES` to a JSON object (e.g. `{"auth_token": "...", "ct0": "..."}`)
to scrape as an authenticated account.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Legal note

X's Terms of Service restrict automated scraping. This tool is provided
for personal/research use in your own private repo; you're responsible
for complying with X's ToS and applicable law in your jurisdiction.
