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
