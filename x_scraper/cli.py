"""Command-line entry point.

Examples:
    python -m x_scraper.cli user elonmusk --count 40
    python -m x_scraper.cli search "claude code" --count 30
    python -m x_scraper.cli user elonmusk --filter-topic "AI" --summarize
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os

from .scraper import scrape_search, scrape_user, scrape_users


def _load_cookies() -> dict[str, str] | None:
    raw = os.environ.get("X_SCRAPER_COOKIES")
    if not raw:
        return None
    return json.loads(raw)


async def _run(args: argparse.Namespace) -> None:
    cookies = _load_cookies()

    if args.command == "user":
        if len(args.targets) == 1:
            tweets = await scrape_user(args.targets[0], count=args.count, cookies=cookies)
        else:
            grouped = await scrape_users(args.targets, count=args.count, cookies=cookies)
            tweets = [t for group in grouped.values() for t in group]
    elif args.command == "search":
        tweets = await scrape_search(args.query, count=args.count, cookies=cookies)
    else:
        raise SystemExit(f"unknown command: {args.command}")

    if args.filter_topic or args.summarize or args.sentiment:
        from .local_model import LocalFilter

        local = LocalFilter()
        if args.filter_topic:
            tweets = local.filter_relevant(tweets, args.filter_topic)
        if args.sentiment:
            for t in tweets:
                t["sentiment"] = local.classify_sentiment(t.get("text", ""))
        if args.summarize:
            print(local.summarize(tweets))
            print()

    if args.out:
        from .local_model import dump_jsonl

        dump_jsonl(tweets, args.out)
    else:
        print(json.dumps(tweets, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape X/Twitter without the official API.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_user = sub.add_parser("user", help="Scrape one or more user timelines")
    p_user.add_argument("targets", nargs="+", help="Screen name(s), no @")
    p_user.add_argument("--count", type=int, default=40)

    p_search = sub.add_parser("search", help="Scrape a search timeline")
    p_search.add_argument("query")
    p_search.add_argument("--count", type=int, default=20)

    for p in (p_user, p_search):
        p.add_argument("--out", help="Write results as JSONL to this path")
        p.add_argument("--filter-topic", help="Keep only tweets relevant to this topic (local model)")
        p.add_argument("--summarize", action="store_true", help="Print a local-model summary")
        p.add_argument("--sentiment", action="store_true", help="Tag each tweet with sentiment")

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
