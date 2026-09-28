"""Command-line entry point.

Examples:
    python -m x_scraper.cli user elonmusk --count 40
    python -m x_scraper.cli search "claude code" --count 30
    python -m x_scraper.cli user elonmusk --filter-topic "AI" --summarize
    python -m x_scraper.cli login   # save a browser login session for reuse
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os

from .scraper import scrape_search, scrape_user, scrape_users

DEFAULT_STORAGE_STATE = os.environ.get("X_SCRAPER_STORAGE_STATE", "storage_state.json")


async def _run(args: argparse.Namespace) -> None:
    storage_state = args.storage_state if os.path.exists(args.storage_state) else None

    if args.command == "login":
        from .browser import save_login_state

        await save_login_state(args.storage_state)
        return

    if args.command == "user":
        if len(args.targets) == 1:
            tweets = await scrape_user(
                args.targets[0],
                count=args.count,
                storage_state=storage_state,
                use_free_proxies=args.free_proxies,
            )
        else:
            grouped = await scrape_users(
                args.targets,
                count=args.count,
                storage_state=storage_state,
                use_free_proxies=args.free_proxies,
            )
            tweets = [t for group in grouped.values() for t in group]
    elif args.command == "search":
        tweets = await scrape_search(
            args.query,
            count=args.count,
            storage_state=storage_state,
            use_free_proxies=args.free_proxies,
        )
    else:
        raise SystemExit(f"unknown command: {args.command}")

    if args.filter_topic or args.summarize or args.sentiment:
        from .local_model import LocalFilter

        local = LocalFilter()
        if args.filter_topic:
            tweets = local.filter_relevant(tweets, args.filter_topic)
        if args.sentiment:
            for t in tweets:
                t["sentiment"] = local.classify_sentiment(t.get("text") or "")
        if args.summarize:
            print(local.summarize(tweets))
            print()

    if args.out:
        from .local_model import dump_jsonl

        dump_jsonl(tweets, args.out)
    else:
        print(json.dumps(tweets, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape X/Twitter by rendering pages in a browser (no API calls)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Open a browser to log in once and save the session")

    p_user = sub.add_parser("user", help="Scrape one or more user timelines")
    p_user.add_argument("targets", nargs="+", help="Screen name(s), no @")
    p_user.add_argument("--count", type=int, default=40)

    p_search = sub.add_parser("search", help="Scrape a search timeline")
    p_search.add_argument("query")
    p_search.add_argument("--count", type=int, default=20)

    for p in (p_user, p_search):
        p.add_argument("--out", help="Write results as JSONL to this path")
        p.add_argument(
            "--filter-topic", help="Keep only tweets relevant to this topic (local model)"
        )
        p.add_argument("--summarize", action="store_true", help="Print a local-model summary")
        p.add_argument("--sentiment", action="store_true", help="Tag each tweet with sentiment")
        p.add_argument(
            "--free-proxies",
            action="store_true",
            help="Rotate through free public proxies, health-checked and auto-refreshed",
        )

    for cmd in ("user", "search"):
        sub.choices[cmd].add_argument(
            "--storage-state",
            default=DEFAULT_STORAGE_STATE,
            help="Path to saved login session from `login` (default: storage_state.json)",
        )
    sub.choices["login"].add_argument(
        "--storage-state",
        default=DEFAULT_STORAGE_STATE,
        help="Where to save the login session",
    )

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
