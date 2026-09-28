"""Local sub-1B parameter model for on-device tweet filtering/summarization.

Runs entirely offline via llama.cpp (llama-cpp-python) so scraped data never
has to be sent to a cloud LLM API. Defaults to Qwen2.5-0.5B-Instruct
(~0.5B params, ~350MB in Q4_K_M GGUF), small enough to run fast on CPU.

Use `scripts/download_model.sh` to fetch the GGUF weights once; this module
just loads whatever file is at MODEL_PATH.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_MODEL_PATH = Path(
    os.environ.get("X_SCRAPER_MODEL_PATH", "models/qwen2.5-0.5b-instruct-q4_k_m.gguf")
)

_SYSTEM_PROMPT = (
    "You are a terse text-classification and summarization assistant. "
    "Follow the requested output format exactly with no extra commentary."
)


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
    """Thin wrapper around the local model for the two tasks the scraper needs."""

    def __init__(self, model_path: str | Path | None = None):
        self.model_path = str(model_path or DEFAULT_MODEL_PATH)

    def _chat(self, user_prompt: str, max_tokens: int = 128) -> str:
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
        """Cheap on-device relevance filter to cut noise before any further processing."""
        prompt = (
            f'Topic: "{topic}"\nTweet: "{tweet_text}"\n'
            'Is this tweet relevant to the topic? Reply with exactly one word: yes or no.'
        )
        reply = self._chat(prompt, max_tokens=3).lower()
        return reply.startswith("y")

    def filter_relevant(self, tweets: list[dict], topic: str) -> list[dict]:
        return [t for t in tweets if self.is_relevant(t.get("text", ""), topic)]

    def summarize(self, tweets: list[dict], max_tokens: int = 200) -> str:
        joined = "\n".join(f"- {t.get('author')}: {t.get('text')}" for t in tweets[:30])
        prompt = f"Summarize the key points from these tweets in 3-5 bullet points:\n{joined}"
        return self._chat(prompt, max_tokens=max_tokens)

    def classify_sentiment(self, tweet_text: str) -> str:
        prompt = (
            f'Tweet: "{tweet_text}"\n'
            "Classify sentiment as exactly one word: positive, negative, or neutral."
        )
        return self._chat(prompt, max_tokens=3).lower()


def dump_jsonl(tweets: list[dict], path: str | Path) -> None:
    with open(path, "w") as f:
        for t in tweets:
            f.write(json.dumps(t) + "\n")
