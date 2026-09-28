"""Self-refreshing pool of free public proxies.

Reality check baked into the design: free proxies die constantly (most
public lists are >80% dead at any moment). "Never runs out" isn't achieved
by finding an infinite supply — it's achieved by continuously re-fetching
from several public list sources, health-checking every candidate before
use, and dropping dead ones on the fly. As long as at least one source is
up and at least one proxy from it works, the pool stays alive; when none
do, callers fall back to a direct (no-proxy) connection rather than hang.

Sources are plain-text lists of `ip:port` published openly on GitHub by
the proxy-scraping community — not scraped from any single site, so one
source going stale doesn't kill the pool.
"""

from __future__ import annotations

import asyncio
import random
import time

import httpx

SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
]

HEALTH_CHECK_URL = "https://x.com/robots.txt"
HEALTH_CHECK_TIMEOUT = 5.0


class ProxyPool:
    """Round-robins over currently-live free proxies, refreshing in the background."""

    def __init__(
        self,
        refresh_interval: int = 600,
        health_check_concurrency: int = 50,
        min_pool_size: int = 5,
    ):
        self.refresh_interval = refresh_interval
        self._sem = asyncio.Semaphore(health_check_concurrency)
        self._min_pool_size = min_pool_size
        self._live: list[str] = []
        self._dead: set[str] = set()
        self._last_refresh = 0.0
        self._refresh_lock = asyncio.Lock()
        self._idx = 0

    async def _fetch_candidates(self, client: httpx.AsyncClient) -> list[str]:
        candidates: set[str] = set()
        for url in SOURCES:
            try:
                resp = await client.get(url, timeout=10)
                resp.raise_for_status()
            except httpx.HTTPError:
                continue
            for line in resp.text.splitlines():
                line = line.strip()
                if line and ":" in line and not line.startswith("#"):
                    candidates.add(line)
        return list(candidates)

    async def _check_one(self, client: httpx.AsyncClient, proxy: str) -> str | None:
        async with self._sem:
            try:
                async with httpx.AsyncClient(
                    proxy=f"http://{proxy}", timeout=HEALTH_CHECK_TIMEOUT
                ) as pclient:
                    resp = await pclient.get(HEALTH_CHECK_URL)
                    if resp.status_code < 500:
                        return proxy
            except (httpx.HTTPError, OSError):
                pass
            return None

    async def refresh(self, force: bool = False) -> None:
        async with self._refresh_lock:
            if not force and time.monotonic() - self._last_refresh < self.refresh_interval:
                return
            async with httpx.AsyncClient() as client:
                candidates = await self._fetch_candidates(client)
                candidates = [c for c in candidates if c not in self._dead]
                random.shuffle(candidates)
                # Cap how many we health-check per refresh to bound wall-clock time.
                candidates = candidates[:800]
                results = await asyncio.gather(
                    *(self._check_one(client, c) for c in candidates)
                )
            live = [r for r in results if r]
            if live:
                self._live = live
                self._idx = 0
            self._last_refresh = time.monotonic()

    async def get(self) -> str | None:
        """Return the next live proxy (round-robin), or None if the pool is empty."""
        if len(self._live) < self._min_pool_size:
            await self.refresh()
        if not self._live:
            return None
        proxy = self._live[self._idx % len(self._live)]
        self._idx += 1
        return proxy

    def mark_dead(self, proxy: str) -> None:
        self._dead.add(proxy)
        if proxy in self._live:
            self._live.remove(proxy)

    async def start_background_refresh(self) -> asyncio.Task:
        async def loop() -> None:
            while True:
                await self.refresh(force=True)
                await asyncio.sleep(self.refresh_interval)

        return asyncio.create_task(loop())
