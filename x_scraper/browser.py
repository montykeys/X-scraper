"""Pure browser-rendered DOM scraping of x.com. No API calls of any kind.

Loads real x.com pages in headless Chromium via Playwright and reads tweet
data straight out of the rendered DOM (article[data-testid="tweet"]
elements) — the same markup a human sees. No REST or GraphQL endpoint is
ever called directly.

Speed optimizations:
- One shared Browser + a pool of persistent contexts reused across scrapes
  (skips browser/context startup cost per call).
- Route interception blocks images/media/fonts/stylesheets, cutting page
  weight drastically since only text content is needed.
- Waits on `domcontentloaded` + a specific selector instead of
  `networkidle`, which on x.com's live-updating timeline never truly settles.
- Bounded concurrency across multiple tabs so several profiles/searches
  scrape in parallel.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

TWEET_SELECTOR = 'article[data-testid="tweet"]'

_EXTRACT_JS = """
(articles) => articles.map(a => {
  const text = a.querySelector('[data-testid="tweetText"]');
  const user = a.querySelector('[data-testid="User-Name"]');
  const time = a.querySelector('time');
  const link = time ? time.closest('a') : null;
  const stats = a.querySelectorAll('[data-testid$="-count"], [data-testid="reply"] span, [data-testid="retweet"] span, [data-testid="like"] span');
  return {
    text: text ? text.innerText : null,
    author: user ? user.innerText.split('\\n')[0] : null,
    created_at: time ? time.getAttribute('datetime') : null,
    url: link ? link.getAttribute('href') : null,
  };
})
"""


class BrowserSession:
    """Long-lived Playwright browser reused across many scrape calls."""

    def __init__(self, storage_state: str | Path | None = None, max_concurrency: int = 4):
        self._storage_state = str(storage_state) if storage_state else None
        self._sem = asyncio.Semaphore(max_concurrency)
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "BrowserSession":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            storage_state=self._storage_state,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 1600},
        )
        await self._context.route("**/*", self._maybe_block)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @staticmethod
    async def _maybe_block(route):
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()

    async def new_page(self) -> Page:
        assert self._context is not None
        return await self._context.new_page()

    async def scroll_and_collect(
        self, page: Page, count: int, max_scrolls: int = 15
    ) -> list[dict]:
        seen: dict[str, dict] = {}
        for _ in range(max_scrolls):
            handles = await page.query_selector_all(TWEET_SELECTOR)
            batch = await page.evaluate(_EXTRACT_JS, handles)
            for item in batch:
                if item.get("url"):
                    seen[item["url"]] = item
            if len(seen) >= count:
                break
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(600)
        return list(seen.values())[:count]

    async def scrape_profile(self, screen_name: str, count: int = 40) -> list[dict]:
        async with self._sem:
            page = await self.new_page()
            try:
                await page.goto(
                    f"https://x.com/{screen_name}", wait_until="domcontentloaded"
                )
                await page.wait_for_selector(TWEET_SELECTOR, timeout=15000)
                return await self.scroll_and_collect(page, count)
            finally:
                await page.close()

    async def scrape_search(self, query: str, count: int = 20) -> list[dict]:
        async with self._sem:
            page = await self.new_page()
            try:
                from urllib.parse import quote

                url = f"https://x.com/search?q={quote(query)}&f=live"
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_selector(TWEET_SELECTOR, timeout=15000)
                return await self.scroll_and_collect(page, count)
            finally:
                await page.close()

    async def scrape_profiles(
        self, screen_names: list[str], count: int = 40
    ) -> dict[str, list[dict]]:
        results = await asyncio.gather(
            *(self.scrape_profile(name, count) for name in screen_names)
        )
        return dict(zip(screen_names, results))


async def save_login_state(storage_state_path: str | Path) -> None:
    """Interactive helper: opens a visible browser so you can log in once,
    then saves cookies/local storage to reuse across headless scrape runs.
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://x.com/login")
        print("Log in in the opened browser window, then press Enter here...")
        await asyncio.get_event_loop().run_in_executor(None, input)
        await context.storage_state(path=str(storage_state_path))
        await browser.close()
    print(f"Saved login state to {storage_state_path}")
