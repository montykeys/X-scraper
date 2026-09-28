"""Async client for X's internal GraphQL endpoints (no official API).

Optimizations over a naive scraper:
- HTTP/2 + a single pooled httpx.AsyncClient reused across all requests
  (connection reuse avoids per-request TLS/TCP handshakes).
- Bounded concurrency via a semaphore so many pages/users can be scraped in
  parallel without tripping rate limits.
- Exponential backoff with jitter on 429/503.
- SQLite-backed caching so repeated calls (e.g. re-running a pipeline) are
  free.
- Guest-token auto-refresh, transparent to callers.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from .auth import Session, new_guest_session
from .cache import Cache

GRAPHQL_BASE = "https://x.com/i/api/graphql"

# Public query IDs used by the x.com web client itself for these operations.
QUERY_IDS = {
    "UserByScreenName": "G3KGOASz96M-Qu0nwmGXNg",
    "UserTweets": "V7H0Ap3_Hh2FyS75OCDO3Q",
    "SearchTimeline": "gkjsKepM6gl_HmFWoWKfgg",
}

FEATURES = {
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}


class XClient:
    def __init__(
        self,
        cookies: dict[str, str] | None = None,
        max_concurrency: int = 5,
        cache: Cache | None = None,
    ) -> None:
        self._cookies = cookies
        self._session: Session | None = None
        self._sem = asyncio.Semaphore(max_concurrency)
        self._cache = cache
        self._http = httpx.AsyncClient(http2=True, timeout=20, cookies=cookies)

    async def __aenter__(self) -> "XClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()
        if self._cache:
            self._cache.close()

    async def _ensure_session(self) -> Session:
        if self._session is None or self._session.is_stale:
            self._session = await new_guest_session(self._http, self._cookies)
        return self._session

    async def _get(self, url: str, params: dict) -> dict:
        cache_key = self._cache.key_for(url, params) if self._cache else None
        if cache_key and (hit := self._cache.get(cache_key)) is not None:
            return hit

        async with self._sem:
            session = await self._ensure_session()
            backoff = 1.0
            for attempt in range(5):
                resp = await self._http.get(url, params=params, headers=session.headers())
                if resp.status_code == 429 or resp.status_code >= 500:
                    await asyncio.sleep(backoff + random.uniform(0, 0.5))
                    backoff *= 2
                    if resp.status_code == 429:
                        self._session = None
                        session = await self._ensure_session()
                    continue
                if resp.status_code == 403:
                    # Guest token likely rotated server-side; refresh once.
                    self._session = None
                    session = await self._ensure_session()
                    resp = await self._http.get(url, params=params, headers=session.headers())
                resp.raise_for_status()
                data = resp.json()
                if cache_key:
                    self._cache.set(cache_key, data)
                return data
            resp.raise_for_status()
            return {}

    async def user_by_screen_name(self, screen_name: str) -> dict:
        variables = {"screen_name": screen_name, "withSafetyModeUserFields": True}
        params = {"variables": _json(variables), "features": _json(FEATURES)}
        url = f"{GRAPHQL_BASE}/{QUERY_IDS['UserByScreenName']}/UserByScreenName"
        return await self._get(url, params)

    async def user_tweets(self, user_id: str, count: int = 40) -> dict:
        variables = {
            "userId": user_id,
            "count": count,
            "includePromotedContent": False,
            "withQuickPromoteEligibilityTweetFields": False,
            "withVoice": True,
        }
        params = {"variables": _json(variables), "features": _json(FEATURES)}
        url = f"{GRAPHQL_BASE}/{QUERY_IDS['UserTweets']}/UserTweets"
        return await self._get(url, params)

    async def search(self, query: str, count: int = 20, product: str = "Latest") -> dict:
        variables = {
            "rawQuery": query,
            "count": count,
            "querySource": "typed_query",
            "product": product,
        }
        params = {"variables": _json(variables), "features": _json(FEATURES)}
        url = f"{GRAPHQL_BASE}/{QUERY_IDS['SearchTimeline']}/SearchTimeline"
        return await self._get(url, params)


def _json(obj: dict) -> str:
    import json

    return json.dumps(obj, separators=(",", ":"))
