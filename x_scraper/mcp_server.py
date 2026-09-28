"""MCP server exposing x_scraper as tools Claude can call directly.

Run with: python -m x_scraper.mcp_server
Register in Claude Code with: claude mcp add x-scraper -- python -m x_scraper.mcp_server

The browser is launched once at server startup and kept warm for the whole
MCP session (via lifespan), instead of a fresh Chromium process per tool
call — since this server is a long-lived process anyway, paying the
~1-2s browser startup cost once instead of on every scrape is the single
biggest latency win available here.
"""

from __future__ import annotations

import contextlib
import os
from typing import AsyncIterator

from mcp.server.mcpserver import Context, MCPServer

from .browser import BrowserSession
from .cache import Cache
from .local_model import LocalFilter

STORAGE_STATE = os.environ.get("X_SCRAPER_STORAGE_STATE", "storage_state.json")
_storage_state = STORAGE_STATE if os.path.exists(STORAGE_STATE) else None
_use_free_proxies = os.environ.get("X_SCRAPER_FREE_PROXIES", "").lower() in ("1", "true", "yes")

_local_filter = LocalFilter()


@contextlib.asynccontextmanager
async def _lifespan(_server: MCPServer) -> AsyncIterator[dict]:
    async with BrowserSession(
        storage_state=_storage_state, use_free_proxies=_use_free_proxies
    ) as session:
        yield {"browser": session, "cache": Cache()}


mcp = MCPServer(
    "x-scraper",
    instructions=(
        "Scrapes X/Twitter via headless browser (no API calls) and filters/"
        "summarizes results with local on-device models."
    ),
    lifespan=_lifespan,
)


def _state(ctx: Context) -> dict:
    return ctx.request_context.lifespan_context


@mcp.tool()
async def scrape_x_user(screen_name: str, ctx: Context, count: int = 40) -> list[dict]:
    """Scrape a single X/Twitter profile's recent tweets via headless browser.

    No API calls are made; the page is rendered and tweets are read from the DOM.

    Args:
        screen_name: The account's handle, without the @ (e.g. "elonmusk").
        count: Max number of tweets to return.
    """
    state = _state(ctx)
    cache: Cache = state["cache"]
    key = cache.key_for("profile", {"screen_name": screen_name, "count": count})
    if (hit := cache.get(key)) is not None:
        return hit
    browser: BrowserSession = state["browser"]
    tweets = await browser.scrape_profile(screen_name, count=count)
    cache.set(key, tweets)
    return tweets


@mcp.tool()
async def scrape_x_users(
    screen_names: list[str], ctx: Context, count: int = 40
) -> dict[str, list[dict]]:
    """Scrape several X/Twitter profiles concurrently (one per browser tab).

    Args:
        screen_names: List of handles, without @.
        count: Max tweets per profile.
    """
    browser: BrowserSession = _state(ctx)["browser"]
    return await browser.scrape_profiles(screen_names, count=count)


@mcp.tool()
async def search_x(query: str, ctx: Context, count: int = 20) -> list[dict]:
    """Scrape X/Twitter's live search results for a query via headless browser.

    Args:
        query: Search text, supports X search operators (from:, since:, etc).
        count: Max number of tweets to return.
    """
    state = _state(ctx)
    cache: Cache = state["cache"]
    key = cache.key_for("search", {"query": query, "count": count})
    if (hit := cache.get(key)) is not None:
        return hit
    browser: BrowserSession = state["browser"]
    tweets = await browser.scrape_search(query, count=count)
    cache.set(key, tweets)
    return tweets


@mcp.tool()
def filter_tweets_by_topic(tweets: list[dict], topic: str) -> list[dict]:
    """Filter scraped tweets to those relevant to a topic, using a purpose-built
    on-device classifier (not a generative model).

    Runs fully offline (no data leaves the machine).

    Args:
        tweets: Tweets as returned by scrape_x_user / search_x.
        topic: The topic to filter for, e.g. "AI safety".
    """
    return _local_filter.filter_relevant(tweets, topic)


@mcp.tool()
def summarize_tweets(tweets: list[dict]) -> str:
    """Summarize a set of scraped tweets into bullet points, using the local
    generative model.

    Args:
        tweets: Tweets as returned by scrape_x_user / search_x.
    """
    return _local_filter.summarize(tweets)


@mcp.tool()
def tag_tweet_sentiment(tweets: list[dict]) -> list[dict]:
    """Tag each tweet with a sentiment label (positive/negative/neutral) using a
    purpose-built on-device classifier (not a generative model).

    Args:
        tweets: Tweets as returned by scrape_x_user / search_x.
    """
    for t in tweets:
        t["sentiment"] = _local_filter.classify_sentiment(t.get("text") or "")
    return tweets


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
