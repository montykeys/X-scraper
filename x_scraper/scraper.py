"""High-level scraping API used by the CLI and by user code."""

from __future__ import annotations

import asyncio

from .api import XClient
from .cache import Cache
from .parse import iter_tweets


async def scrape_user(
    screen_name: str, count: int = 40, cookies: dict[str, str] | None = None
) -> list[dict]:
    async with XClient(cookies=cookies, cache=Cache()) as client:
        user_payload = await client.user_by_screen_name(screen_name)
        user_id = user_payload["data"]["user"]["result"]["rest_id"]
        tweets_payload = await client.user_tweets(user_id, count=count)
        return list(iter_tweets(tweets_payload))


async def scrape_users(
    screen_names: list[str], count: int = 40, cookies: dict[str, str] | None = None
) -> dict[str, list[dict]]:
    """Scrape several profiles concurrently, sharing one connection pool."""
    async with XClient(cookies=cookies, cache=Cache()) as client:

        async def one(name: str) -> tuple[str, list[dict]]:
            user_payload = await client.user_by_screen_name(name)
            user_id = user_payload["data"]["user"]["result"]["rest_id"]
            tweets_payload = await client.user_tweets(user_id, count=count)
            return name, list(iter_tweets(tweets_payload))

        results = await asyncio.gather(*(one(n) for n in screen_names))
        return dict(results)


async def scrape_search(
    query: str, count: int = 20, cookies: dict[str, str] | None = None
) -> list[dict]:
    async with XClient(cookies=cookies, cache=Cache()) as client:
        payload = await client.search(query, count=count)
        return list(iter_tweets(payload))
