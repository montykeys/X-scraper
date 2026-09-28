"""High-level scraping API used by the CLI and by user code.

Pure browser DOM scraping — no API calls of any kind.
"""

from __future__ import annotations

from pathlib import Path

from .browser import BrowserSession
from .cache import Cache


async def scrape_user(
    screen_name: str, count: int = 40, storage_state: str | Path | None = None
) -> list[dict]:
    cache = Cache()
    key = cache.key_for("profile", {"screen_name": screen_name, "count": count})
    if (hit := cache.get(key)) is not None:
        return hit
    async with BrowserSession(storage_state=storage_state) as session:
        tweets = await session.scrape_profile(screen_name, count=count)
    cache.set(key, tweets)
    return tweets


async def scrape_users(
    screen_names: list[str], count: int = 40, storage_state: str | Path | None = None
) -> dict[str, list[dict]]:
    async with BrowserSession(storage_state=storage_state) as session:
        return await session.scrape_profiles(screen_names, count=count)


async def scrape_search(
    query: str, count: int = 20, storage_state: str | Path | None = None
) -> list[dict]:
    cache = Cache()
    key = cache.key_for("search", {"query": query, "count": count})
    if (hit := cache.get(key)) is not None:
        return hit
    async with BrowserSession(storage_state=storage_state) as session:
        tweets = await session.scrape_search(query, count=count)
    cache.set(key, tweets)
    return tweets
