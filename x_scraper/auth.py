"""Guest-token and cookie auth for X's internal web GraphQL API.

X's own web client (x.com) authenticates unauthenticated ("guest") requests
with a public bearer token embedded in its JS bundle, exchanged for a
short-lived guest token via the 1.1 REST endpoint below. This is the same
mechanism the web app itself uses to render logged-out profile/search pages,
so no paid API key is required. Optional account cookies can be supplied for
higher rate limits / gated content.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

# Long-lived public bearer token used by the X web app for guest sessions.
WEB_BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

GUEST_ACTIVATE_URL = "https://api.x.com/1.1/guest/activate.json"


@dataclass
class Session:
    bearer_token: str
    guest_token: str
    obtained_at: float
    cookies: dict[str, str] | None = None

    @property
    def is_stale(self) -> bool:
        # Guest tokens rotate roughly every few hours server-side; refresh
        # proactively well before that to avoid mid-batch 403s.
        return time.monotonic() - self.obtained_at > 3600

    def headers(self) -> dict[str, str]:
        headers = {
            "authorization": f"Bearer {self.bearer_token}",
            "x-guest-token": self.guest_token,
            "content-type": "application/json",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        }
        if self.cookies and (csrf := self.cookies.get("ct0")):
            headers["x-csrf-token"] = csrf
        return headers


async def new_guest_session(
    client: httpx.AsyncClient, cookies: dict[str, str] | None = None
) -> Session:
    resp = await client.post(
        GUEST_ACTIVATE_URL,
        headers={"authorization": f"Bearer {WEB_BEARER_TOKEN}"},
    )
    resp.raise_for_status()
    guest_token = resp.json()["guest_token"]
    return Session(
        bearer_token=WEB_BEARER_TOKEN,
        guest_token=guest_token,
        obtained_at=time.monotonic(),
        cookies=cookies,
    )
