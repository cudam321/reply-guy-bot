"""
monitor.py — Fetches new tweets from a Twitter list using TwitterAPI.io.

Usage:
    python monitor.py             # normal mode
    python monitor.py --dry-run   # just print, no DB writes
"""
import sys
import time
import requests
from typing import List, Optional
from dataclasses import dataclass

from config import LIST_ID, TWITTERAPI_KEY, TWITTERAPI_BASE_URL
import state


@dataclass
class Tweet:
    tweet_id: str
    author: str
    text: str


def fetch_new_tweets(dry_run: bool = False) -> Optional[List[Tweet]]:
    """Fetch new tweets from the configured Twitter list using TwitterAPI.io.

    Returns None if the API is unreachable (so callers can tell
    "API down" apart from "no new tweets").
    """
    if not TWITTERAPI_KEY:
        print("[monitor] ❌ Error: TWITTERAPI_KEY is not set in .env")
        return []

    if not LIST_ID:
        print("[monitor] ❌ Error: TWITTER_LIST_ID is not set in .env")
        return []

    url = f"{TWITTERAPI_BASE_URL}/list/tweets_timeline"
    headers = {"X-API-Key": TWITTERAPI_KEY}
    params = {"listId": LIST_ID}

    print(f"[monitor] Fetching list {LIST_ID} via TwitterAPI.io...")
    data = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            print(f"[monitor] ❌ API call failed (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(20)
    if data is None:
        return None

    api_tweets = data.get("tweets", [])
    print(f"[monitor] Found {len(api_tweets)} tweets in timeline")

    new_tweets = []
    for item in api_tweets:
        try:
            # Type must be 'tweet' (ignore ads or other entities if any)
            if item.get("type") != "tweet":
                continue

            tweet_id = item.get("id")
            text = item.get("text", "")

            author_obj = item.get("author", {})
            author = author_obj.get("userName", "")

            if not tweet_id or not text or not author:
                continue

            tweet = Tweet(tweet_id=tweet_id, author=author, text=text)

            if dry_run:
                print(f"  [dry-run] @{author} ({tweet_id}): {text[:80].replace(chr(10), ' ')}")
                new_tweets.append(tweet)
            elif not state.is_seen(tweet_id):
                state.mark_seen(tweet_id)
                new_tweets.append(tweet)

        except Exception as e:
            print(f"[monitor] Error parsing tweet item: {e}")
            continue

    print(f"[monitor] {len(new_tweets)} new tweet(s) to process")

    # Optional: Reverse the array so we process the oldest unseen tweets first
    new_tweets.reverse()
    return new_tweets


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    state.init_db()
    results = fetch_new_tweets(dry_run=dry)
    if not results:
        print("[monitor] Nothing new.")
