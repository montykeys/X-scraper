"""MCP server exposing x_scraper as tools Claude can call directly.

Run with: python -m x_scraper.mcp_server
Register in Claude Code with: claude mcp add x-scraper -- python -m x_scraper.mcp_server
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from .local_model import LocalFilter
from .scraper import scrape_search, scrape_user, scrape_users

mcp = MCPServer(
    "x-scraper",
    instructions=(
        "Scrapes X/Twitter via headless browser (no API calls) and filters/"
        "summarizes results with a local on-device model."
    ),
)

STORAGE_STATE = os.environ.get("X_SCRAPER_STORAGE_STATE", "storage_state.json")
_storage_state = STORAGE_STATE if os.path.exists(STORAGE_STATE) else None


@mcp.tool()
async def scrape_x_user(screen_name: str, count: int = 40) -> list[dict]:
    """Scrape a single X/Twitter profile's recent tweets via headless browser.

    No API calls are made; the page is rendered and tweets are read from the DOM.

    Args:
        screen_name: The account's handle, without the @ (e.g. "elonmusk").
        count: Max number of tweets to return.
    """
    return await scrape_user(screen_name, count=count, storage_state=_storage_state)


@mcp.tool()
async def scrape_x_users(screen_names: list[str], count: int = 40) -> dict[str, list[dict]]:
    """Scrape several X/Twitter profiles concurrently (one per browser tab).

    Args:
        screen_names: List of handles, without @.
        count: Max tweets per profile.
    """
    return await scrape_users(screen_names, count=count, storage_state=_storage_state)


@mcp.tool()
async def search_x(query: str, count: int = 20) -> list[dict]:
    """Scrape X/Twitter's live search results for a query via headless browser.

    Args:
        query: Search text, supports X search operators (from:, since:, etc).
        count: Max number of tweets to return.
    """
    return await scrape_search(query, count=count, storage_state=_storage_state)


@mcp.tool()
def filter_tweets_by_topic(tweets: list[dict], topic: str) -> list[dict]:
    """Filter scraped tweets to those relevant to a topic, using the local on-device model.

    Runs fully offline (no data leaves the machine).

    Args:
        tweets: Tweets as returned by scrape_x_user / search_x.
        topic: The topic to filter for, e.g. "AI safety".
    """
    return LocalFilter().filter_relevant(tweets, topic)


@mcp.tool()
def summarize_tweets(tweets: list[dict]) -> str:
    """Summarize a set of scraped tweets into bullet points, using the local on-device model.

    Args:
        tweets: Tweets as returned by scrape_x_user / search_x.
    """
    return LocalFilter().summarize(tweets)


@mcp.tool()
def tag_tweet_sentiment(tweets: list[dict]) -> list[dict]:
    """Tag each tweet with a sentiment label (positive/negative/neutral) using the local model.

    Args:
        tweets: Tweets as returned by scrape_x_user / search_x.
    """
    local = LocalFilter()
    for t in tweets:
        t["sentiment"] = local.classify_sentiment(t.get("text") or "")
    return tweets


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
