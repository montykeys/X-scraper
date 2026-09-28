"""Loads the trained tweet detector and exposes relevance/sentiment calls.

Purpose-built for this one task: two TF-IDF + logistic regression models
(a few hundred KB combined, CPU-only, sub-millisecond inference), not a
general-purpose LLM being asked to play classifier. Train with
`python -m x_scraper.detector.train` before first use.
"""

from __future__ import annotations

from functools import lru_cache

import joblib

from .train import MODEL_DIR, _relevance_features


@lru_cache(maxsize=1)
def _load(name: str):
    path = MODEL_DIR / f"{name}.joblib"
    if not path.exists():
        raise FileNotFoundError(
            f"Detector model not found at {path}. Run `python -m x_scraper.detector.train` first."
        )
    return joblib.load(path)


class TweetDetector:
    """Fast, purpose-built classifier for tweet relevance and sentiment."""

    def is_relevant(self, text: str, topic: str) -> bool:
        model = _load("relevance")
        pred = model.predict([_relevance_features(topic, text or "")])[0]
        return bool(pred)

    def relevance_score(self, text: str, topic: str) -> float:
        """Probability the text is relevant to the topic, in [0, 1]."""
        model = _load("relevance")
        classes = list(model.classes_)
        proba = model.predict_proba([_relevance_features(topic, text or "")])[0]
        return float(proba[classes.index(True)])

    def classify_sentiment(self, text: str) -> str:
        model = _load("sentiment")
        return str(model.predict([text or ""])[0])

    def filter_relevant(self, tweets: list[dict], topic: str) -> list[dict]:
        return [t for t in tweets if self.is_relevant(t.get("text") or "", topic)]

    def tag_sentiment(self, tweets: list[dict]) -> list[dict]:
        for t in tweets:
            t["sentiment"] = self.classify_sentiment(t.get("text") or "")
        return tweets
