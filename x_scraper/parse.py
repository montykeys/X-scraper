"""Flatten X's deeply nested GraphQL timeline responses into plain dicts."""

from __future__ import annotations

from typing import Any, Iterator


def _instructions(payload: dict) -> list[dict]:
    for key in ("user", "search_by_raw_query"):
        pass
    try:
        return payload["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
    except KeyError:
        pass
    try:
        return payload["data"]["search_by_raw_query"]["search_timeline"]["timeline"][
            "instructions"
        ]
    except KeyError:
        return []


def iter_tweets(payload: dict) -> Iterator[dict[str, Any]]:
    for instruction in _instructions(payload):
        entries = instruction.get("entries") or []
        if instruction.get("type") == "TimelineAddEntries":
            for entry in entries:
                tweet = _extract_tweet(entry)
                if tweet:
                    yield tweet


def _extract_tweet(entry: dict) -> dict[str, Any] | None:
    try:
        item = entry["content"]["itemContent"]
        result = item["tweet_results"]["result"]
        if result.get("__typename") == "TweetWithVisibilityResults":
            result = result["tweet"]
        legacy = result["legacy"]
        user = result["core"]["user_results"]["result"]["legacy"]
    except (KeyError, TypeError):
        return None
    return {
        "id": result.get("rest_id"),
        "text": legacy.get("full_text"),
        "created_at": legacy.get("created_at"),
        "like_count": legacy.get("favorite_count"),
        "retweet_count": legacy.get("retweet_count"),
        "reply_count": legacy.get("reply_count"),
        "author": user.get("screen_name"),
    }
