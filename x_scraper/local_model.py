"""On-device tweet processing: a purpose-built detector for classification,
a small instruction model for summarization.

Two different jobs, two different tools:
- Relevance filtering and sentiment are classification, not generation —
  handled by x_scraper.detector.TweetDetector, a TF-IDF + logistic
  regression model trained specifically for this task (see
  detector/train.py). It's accurate, deterministic, and microseconds per
  call, none of which a generic instruction-following LLM reliably is at
  0.5B parameters.
- Summarization is genuinely generative, so it stays on Qwen2.5-0.5B-
  Instruct via llama.cpp, with a few-shot prompt to keep output format
  consistent.

Everything runs fully offline; no data leaves the machine.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from .detector import TweetDetector

DEFAULT_MODEL_PATH = Path(
    os.environ.get("X_SCRAPER_MODEL_PATH", "models/qwen2.5-0.5b-instruct-q4_k_m.gguf")
)

_SYSTEM_PROMPT = (
    "You are a terse summarization assistant. Follow the requested output "
    "format exactly with no extra commentary."
)

_SUMMARIZE_FEWSHOT = """Example:
Tweets:
- alice: Just shipped the new onboarding flow, conversion is already up 12%.
- bob: Server room AC died again, this is the third time this month.
- carol: Great turnout at the meetup last night, over 200 people showed.

Summary:
- Alice's team shipped a new onboarding flow, boosting conversion 12%.
- Recurring AC failures in the server room, third time this month.
- Strong turnout (200+) at last night's meetup.

Now summarize these:
"""


@lru_cache(maxsize=1)
def _load(model_path: str):
    from llama_cpp import Llama

    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Local model not found at {model_path}. Run scripts/download_model.sh first."
        )
    return Llama(
        model_path=model_path,
        n_ctx=2048,
        n_threads=os.cpu_count() or 4,
        verbose=False,
    )


class LocalFilter:
    """Combines the tweet detector (classification) and Qwen (summarization)."""

    def __init__(self, model_path: str | Path | None = None):
        self.model_path = str(model_path or DEFAULT_MODEL_PATH)
        self._detector = TweetDetector()

    def _chat(self, user_prompt: str, max_tokens: int = 200) -> str:
        llm = _load(self.model_path)
        out = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0,
        )
        return out["choices"][0]["message"]["content"].strip()

    def is_relevant(self, tweet_text: str, topic: str) -> bool:
        return self._detector.is_relevant(tweet_text, topic)

    def filter_relevant(self, tweets: list[dict], topic: str) -> list[dict]:
        return self._detector.filter_relevant(tweets, topic)

    def classify_sentiment(self, tweet_text: str) -> str:
        return self._detector.classify_sentiment(tweet_text)

    def summarize(self, tweets: list[dict], max_tokens: int = 200) -> str:
        joined = "\n".join(f"- {t.get('author')}: {t.get('text')}" for t in tweets[:30])
        prompt = f"{_SUMMARIZE_FEWSHOT}Tweets:\n{joined}\n\nSummary:"
        return self._chat(prompt, max_tokens=max_tokens)


def dump_jsonl(tweets: list[dict], path: str | Path) -> None:
    with open(path, "w") as f:
        for t in tweets:
            f.write(json.dumps(t) + "\n")
