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
- Route interception blocks every resource type that isn't needed for text
  (images/media/fonts/stylesheets/manifests/beacons/prefetches), plus known
  ad/analytics/telemetry domains and twimg.com's image/video CDN by name.
  Only `document`, `script`, and `xhr`/`fetch` stay on — X is a
  client-rendered SPA, so JS + its own data fetches are the only things
  that produce tweet text.
- Chromium launches with GPU, extensions, background networking, sync,
  translate, and audio disabled, plus `imagesEnabled=false` at the engine
  level as a second layer under the route blocking.
- Waits on `domcontentloaded` + a specific selector instead of
  `networkidle`, which never truly settles on X's live timeline.
- Bounded concurrency (semaphore) so multiple profiles/searches scrape in
  parallel tabs.
- SQLite response cache (15 min TTL) so repeated pipeline runs cost
  nothing.

### Throughput

This is I/O + render bound, not CPU bound — realistic sustained throughput
on a normal machine is **~2-5 profile/search scrapes per second** with
5-15 concurrent tabs (each Chromium tab costs ~150-400MB RAM; past that
the OS starts thrashing). Scaling further means more machines, not more
threads on one box.

## Free proxy rotation (optional)

`--free-proxies` (CLI) / `X_SCRAPER_FREE_PROXIES=1` (MCP server) routes
each scrape through `x_scraper.proxy_pool.ProxyPool`: it pulls `ip:port`
candidates from several openly-published free proxy lists, health-checks
them concurrently against a real request, and round-robins over whichever
ones are currently alive. Dead proxies are dropped and the pool
re-refreshes from its sources in the background.

Be realistic about what this buys you: free proxies are not infinite and
most are dead or slow at any given moment (this is why the pool
continuously re-checks rather than trusting a fetched list). If every
proxy in a refresh fails, scraping transparently falls back to a direct
connection rather than hanging. Expect proxy-routed scrapes to be slower
and less reliable than direct ones — use it for spreading load across
IPs, not as a performance feature.

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

## On-device models: two, not one

Filtering/summarizing scraped tweets is two different jobs, so it's two
different models — a generative LLM is the wrong tool for classification:

- **Relevance + sentiment (classification)** — `x_scraper.detector`, a
  TF-IDF + logistic regression model trained specifically for this task
  (`x_scraper/detector/data.py` + `train.py`). ~40KB total, CPU-only,
  sub-millisecond per call, no prompt engineering, no hallucinated labels.
  A generic 0.5B instruction model got this wrong on trivial cases (called
  an off-topic lunch tweet "relevant to AI", called neutral statements
  "positive"); a purpose-built classifier doesn't.
- **Summarization (generation)** — Qwen2.5-0.5B-Instruct via `llama.cpp`
  (~350MB Q4_K_M GGUF), the one job here that's actually generative, with
  a few-shot prompt to keep output format consistent.

```bash
./scripts/download_model.sh        # fetches the Qwen GGUF weights once
python -m x_scraper.detector.train # trains the relevance/sentiment models (~1s, no download)
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

# Rotate through free public proxies
python -m x_scraper.cli user elonmusk --free-proxies
```

## Use from Claude directly (MCP server)

`x_scraper.mcp_server` exposes `scrape_x_user`, `scrape_x_users`, `search_x`,
`filter_tweets_by_topic`, `summarize_tweets`, and `tag_tweet_sentiment` as
MCP tools, so Claude can scrape and analyze X directly in conversation.

Register it with Claude Code:

```bash
claude mcp add x-scraper -- python -m x_scraper.mcp_server
```

Or add manually to `.mcp.json` / `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "x-scraper": {
      "command": "python",
      "args": ["-m", "x_scraper.mcp_server"],
      "cwd": "/path/to/X-scraper"
    }
  }
}
```

Run `python -m x_scraper.cli login` first if scraping requires an
authenticated session — the MCP server picks up `storage_state.json`
automatically.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Legal note

X's Terms of Service restrict automated scraping. This tool is provided
for personal/research use in your own private repo; you're responsible
for complying with X's ToS and applicable law in your jurisdiction.
