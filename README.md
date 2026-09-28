# X-scraper

Scrapes X (Twitter) by rendering real pages in a headless browser and
reading tweets straight out of the DOM. **No API calls of any kind** — not
the paid official API, not X's internal GraphQL/REST endpoints. Just a
browser loading x.com like a person would, and code reading what's on
screen.

## How it works

`x_scraper.browser.BrowserSession` drives headless Chromium via Playwright:

1. Navigate to a profile (`x.com/<user>`) or search page
   (`x.com/search?q=...&f=live`).
2. Wait for `article[data-testid="tweet"]` elements to render.
3. Read text/author/timestamp/link straight out of the DOM
   (`page.evaluate`), no network interception or endpoint replay involved.
4. Scroll and repeat until enough tweets are collected.

## Performance

- One shared `Browser` + persistent `BrowserContext` reused across every
  scrape (skips per-call browser/context startup).
- Route interception blocks images/media/fonts/stylesheets — only the text
  DOM is needed, so pages load a fraction of their normal weight.
- Waits on `domcontentloaded` + a specific selector instead of
  `networkidle`, which never truly settles on X's live timeline.
- Bounded concurrency (semaphore) so multiple profiles/searches scrape in
  parallel tabs.
- SQLite response cache (15 min TTL) so repeated pipeline runs cost
  nothing.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

Public profiles/search often render logged out, but X increasingly gates
content behind login. Save a session once:

```bash
python -m x_scraper.cli login   # opens a real browser, log in, press Enter
```

This saves cookies/local storage to `storage_state.json`, reused
automatically by later headless runs.

## Local sub-1B model

`x_scraper.local_model` runs a small (~0.5B parameter) instruction model
fully offline via `llama.cpp`, so scraped data never has to leave the
machine for filtering/summarization/sentiment tagging. Default model is
Qwen2.5-0.5B-Instruct, quantized to Q4_K_M (~350MB), fast enough on CPU.

```bash
./scripts/download_model.sh   # fetches the GGUF weights once
```

## Usage

```bash
# Scrape a profile
python -m x_scraper.cli user elonmusk --count 40

# Scrape several profiles concurrently (separate tabs, one browser)
python -m x_scraper.cli user elonmusk sama --count 20

# Search
python -m x_scraper.cli search "claude code" --count 30

# Filter to on-topic tweets and summarize, entirely on-device
python -m x_scraper.cli user elonmusk --filter-topic "AI safety" --summarize

# Tag sentiment and write JSONL
python -m x_scraper.cli search "claude code" --sentiment --out results.jsonl
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Legal note

X's Terms of Service restrict automated scraping. This tool is provided
for personal/research use in your own private repo; you're responsible
for complying with X's ToS and applicable law in your jurisdiction.
