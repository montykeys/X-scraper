"""Pure browser-rendered DOM scraping of x.com. No API calls of any kind.

Loads real x.com pages in headless Chromium via Playwright and reads tweet
data straight out of the rendered DOM (article[data-testid="tweet"]
elements) — the same markup a human sees. No REST or GraphQL endpoint is
ever called directly.

Speed optimizations:
- One shared Browser reused across scrapes (skips browser startup cost per
  call). Contexts are still created per-scrape when proxy rotation is on,
  since Playwright binds a proxy at context creation, not per-page — but
  context creation is cheap relative to a fresh browser process.
- Route interception blocks images/media/fonts/stylesheets, cutting page
  weight drastically since only text content is needed.
- Waits on `domcontentloaded` + a specific selector instead of
  `networkidle`, which on x.com's live-updating timeline never truly settles.
- Bounded concurrency across multiple tabs so several profiles/searches
  scrape in parallel.

Proxy rotation (optional, off by default): when use_free_proxies=True, each
scrape call runs through a fresh live proxy from ProxyPool, and transparently
retries on the next proxy (then falls back to a direct connection) if the
proxy is dead or the page fails to load.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .proxy_pool import ProxyPool

BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

TWEET_SELECTOR = 'article[data-testid="tweet"]'

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_EXTRACT_JS = """
(articles) => articles.map(a => {
  const text = a.querySelector('[data-testid="tweetText"]');
  const user = a.querySelector('[data-testid="User-Name"]');
  const time = a.querySelector('time');
  const link = time ? time.closest('a') : null;
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

    def __init__(
        self,
        storage_state: str | Path | None = None,
        max_concurrency: int = 4,
        use_free_proxies: bool = False,
        max_proxy_attempts: int = 3,
    ):
        self._storage_state = str(storage_state) if storage_state else None
        self._sem = asyncio.Semaphore(max_concurrency)
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None  # used only when proxies are off
        self._use_free_proxies = use_free_proxies
        self._max_proxy_attempts = max_proxy_attempts
        self._proxy_pool = ProxyPool() if use_free_proxies else None

    async def __aenter__(self) -> "BrowserSession":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        if not self._use_free_proxies:
            self._context = await self._new_context()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _new_context(self, proxy: str | None = None) -> BrowserContext:
        assert self._browser is not None
        kwargs: dict[str, Any] = dict(
            storage_state=self._storage_state,
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 1600},
        )
        if proxy:
            kwargs["proxy"] = {"server": f"http://{proxy}"}
        context = await self._browser.new_context(**kwargs)
        await context.route("**/*", self._maybe_block)
        return context

    @staticmethod
    async def _maybe_block(route):
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()

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

    async def _run_scrape(self, goto_url: str, count: int) -> list[dict]:
        """Navigate + scroll + collect, transparently rotating proxies on failure."""
        if not self._use_free_proxies:
            page = await self._context.new_page()  # type: ignore[union-attr]
            try:
                await page.goto(goto_url, wait_until="domcontentloaded")
                await page.wait_for_selector(TWEET_SELECTOR, timeout=15000)
                return await self.scroll_and_collect(page, count)
            finally:
                await page.close()

        assert self._proxy_pool is not None
        last_error: Exception | None = None
        for _ in range(self._max_proxy_attempts):
            proxy = await self._proxy_pool.get()
            context = await self._new_context(proxy=proxy)
            page = await context.new_page()
            try:
                await page.goto(goto_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_selector(TWEET_SELECTOR, timeout=15000)
                return await self.scroll_and_collect(page, count)
            except Exception as exc:  # noqa: BLE001 - proxy/network failures vary widely
                last_error = exc
                if proxy:
                    self._proxy_pool.mark_dead(proxy)
            finally:
                await context.close()

        # All proxy attempts failed: fall back to a direct connection rather than error out.
        context = await self._new_context(proxy=None)
        page = await context.new_page()
        try:
            await page.goto(goto_url, wait_until="domcontentloaded")
            await page.wait_for_selector(TWEET_SELECTOR, timeout=15000)
            return await self.scroll_and_collect(page, count)
        except Exception:
            if last_error:
                raise last_error
            raise
        finally:
            await context.close()

    async def scrape_profile(self, screen_name: str, count: int = 40) -> list[dict]:
        async with self._sem:
            return await self._run_scrape(f"https://x.com/{screen_name}", count)

    async def scrape_search(self, query: str, count: int = 20) -> list[dict]:
        async with self._sem:
            from urllib.parse import quote

            url = f"https://x.com/search?q={quote(query)}&f=live"
            return await self._run_scrape(url, count)

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
