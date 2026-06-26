"""
generator.py — Uses OpenAI to generate a contextual reply to a tweet.
Includes a mood randomizer for unpredictable tone variety and anti-slop filter.

Usage:
    python generator.py --dry-run
"""
import sys
import re
import random
from typing import Optional
from openai import OpenAI
from config import (
    OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT_BASE,
    REPLY_MOODS, SLOP_PHRASES, SLOP_PATTERNS_STARTSWITH, BOT_HANDLE,
)

_client = OpenAI(api_key=OPENAI_API_KEY)


def _detect_slop(text: str) -> list:
    """Check text against known AI slop patterns. Returns list of violations."""
    violations = []
    lower = text.lower().strip()

    for phrase in SLOP_PHRASES:
        if phrase in lower:
            violations.append(f"slop: '{phrase}'")

    for starter in SLOP_PATTERNS_STARTSWITH:
        if lower.startswith(starter):
            violations.append(f"starter: '{starter}'")

    if "—" in text or " - " in text:
        violations.append("em dash")

    words = re.findall(r'\b\w+ly\b', lower)
    slop_adverbs = [w for w in words if w not in (
        "only", "early", "daily", "fly", "supply", "apply", "ally",
        "rally", "bully", "belly", "jelly", "holly", "folly",
    )]
    if slop_adverbs:
        violations.append(f"adverbs: {', '.join(slop_adverbs)}")

    if re.search(r'\w+,\s+\w+,\s+and\s+\w+', lower):
        violations.append("three-item list")

    return violations


def generate_reply(tweet_text: str, author: str) -> Optional[str]:
    """
    Generate a reply with a randomly selected mood/style.
    Runs up to 3 attempts with different moods if slop is detected.
    """
    for attempt in range(3):
        # Pick a random mood each attempt for maximum variety
        mood = random.choice(REPLY_MOODS)
        prompt = SYSTEM_PROMPT_BASE.format(
            mood=mood, author=author, tweet_text=tweet_text
        )

        # Vary temperature per attempt for more diversity
        temp = random.uniform(0.85, 1.05)

        try:
            response = _client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temp,
                max_tokens=100,
            )
            reply = response.choices[0].message.content.strip()

            # Strip accidental self-mention of the bot's own handle
            if BOT_HANDLE:
                handle = "@" + BOT_HANDLE.lstrip("@").lower()
                if reply.lower().startswith(handle):
                    reply = reply[len(handle):].lstrip(": ").strip()

            # Strip wrapping quotes
            if (reply.startswith('"') and reply.endswith('"')) or \
               (reply.startswith("'") and reply.endswith("'")):
                reply = reply[1:-1].strip()

            if not reply:
                print(f"[generator] Empty (attempt {attempt+1}), retrying...")
                continue

            if len(reply) > 270:
                reply = reply[:267] + "..."

            violations = _detect_slop(reply)
            if violations:
                print(f"[generator] ⚠️  Slop (attempt {attempt+1}, mood: {mood[:30]}...): {violations}")
                print(f"[generator]    Rejected: {reply}")
                continue

            print(f"[generator] ✅ Clean (attempt {attempt+1}, mood: {mood[6:30]})")
            return reply

        except Exception as e:
            print(f"[generator] Error (attempt {attempt+1}): {e}")

    print("[generator] ❌ All attempts failed.")
    return None


def select_best_tweets(tweets_data: list, limit: int = 3) -> list:
    """
    Given a list of dicts [{'id': '..', 'author': '..', 'text': '..'}],
    ask the LLM to pick the top `limit` most interesting tweets to reply to.
    Returns a list of the selected tweet IDs.
    """
    if len(tweets_data) <= limit:
        return [t['id'] for t in tweets_data]

    prompt = (
        f"Evaluate the following {len(tweets_data)} tweets. Select the {limit} most interesting "
        "ones to reply to as a provocative, witty Twitter account. Look for tweets that "
        "invite strong opinions, jokes, or insightful counter-takes. Ignore boring updates.\n\n"
    )

    for i, t in enumerate(tweets_data):
        prompt += f"[{i}] Author: @{t['author']}\nText: {t['text']}\n\n"

    prompt += f"Return ONLY a comma-separated list of the numerical indices (e.g. 0, 3, 4) of the {limit} best tweets. No other text."

    try:
        response = _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=30,
        )
        content = response.choices[0].message.content.strip()

        indices = [int(n) for n in re.findall(r'\d+', content)]

        selected_ids = []
        for idx in indices:
            if 0 <= idx < len(tweets_data):
                selected_ids.append(tweets_data[idx]['id'])

        if not selected_ids:
            return [t['id'] for t in tweets_data[:limit]]

        return selected_ids[:limit]
    except Exception as e:
        print(f"[generator] Error selecting best tweets: {e}")
        return [t['id'] for t in tweets_data[:limit]]


if __name__ == "__main__":
    print("=== Generator Dry-Run (mood randomizer + anti-slop) ===\n")
    test_author = input("Author (without @): ").strip() or "someone"
    test_text = input("Tweet text: ").strip() or "the timeline is so boring right now i might start touching grass"

    print(f"\nGenerating 5 replies to show variety:\n")
    for i in range(5):
        reply = generate_reply(test_text, test_author)
        if reply:
            print(f"  {i+1}. {reply}\n")
        else:
            print(f"  {i+1}. [FAILED]\n")
