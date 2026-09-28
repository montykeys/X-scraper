"""Trains the tweet detector: two small TF-IDF + logistic regression models,
purpose-built for relevance filtering and sentiment classification.

This is intentionally not an LLM. Detection ("does this text match this
topic", "is this text positive/negative/neutral") is a text classification
problem, and a linear model over TF-IDF features solves it in microseconds
with a model measured in kilobytes instead of hundreds of megabytes — no
GPU, no prompt engineering, no hallucinated labels.

Run: python -m x_scraper.detector.train
"""

from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .data import RELEVANCE_EXAMPLES, SENTIMENT_EXAMPLES

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models" / "detector"

# Special token marking the topic segment, so the vectorizer can tell
# "topic:ai discussing model benchmarks" apart from "ai" just appearing
# in body text at a different frequency.
_TOPIC_PREFIX = "__topic__"


def _relevance_features(topic: str, text: str) -> str:
    return f"{_TOPIC_PREFIX}{topic.lower().strip()} {text}"


def train_relevance_model() -> Pipeline:
    X = [_relevance_features(topic, text) for topic, text, _ in RELEVANCE_EXAMPLES]
    y = [label for _, _, label in RELEVANCE_EXAMPLES]
    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    pipeline.fit(X, y)
    return pipeline


def train_sentiment_model() -> Pipeline:
    X = [text for text, _ in SENTIMENT_EXAMPLES]
    y = [label for _, label in SENTIMENT_EXAMPLES]
    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    pipeline.fit(X, y)
    return pipeline


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    relevance = train_relevance_model()
    joblib.dump(relevance, MODEL_DIR / "relevance.joblib")

    sentiment = train_sentiment_model()
    joblib.dump(sentiment, MODEL_DIR / "sentiment.joblib")

    print(f"Trained and saved detector models to {MODEL_DIR}")


if __name__ == "__main__":
    main()
