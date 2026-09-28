import pytest

from x_scraper.detector import TweetDetector
from x_scraper.detector.train import MODEL_DIR, main as train_main


@pytest.fixture(scope="module", autouse=True)
def ensure_trained():
    if not (MODEL_DIR / "relevance.joblib").exists() or not (
        MODEL_DIR / "sentiment.joblib"
    ).exists():
        train_main()


def test_relevance_rejects_off_topic():
    d = TweetDetector()
    assert d.is_relevant("Lunch was great today, had a burger.", "AI") is False


def test_relevance_accepts_on_topic():
    d = TweetDetector()
    assert d.is_relevant("New Claude model benchmarks look impressive.", "AI") is True


def test_sentiment_neutral_for_factual_statement():
    d = TweetDetector()
    assert d.classify_sentiment("Lunch was great today, had a burger.") == "neutral"


def test_sentiment_detects_positive():
    d = TweetDetector()
    assert d.classify_sentiment("So proud of the team, we hit every milestone.") == "positive"


def test_sentiment_detects_negative():
    d = TweetDetector()
    assert d.classify_sentiment("This is infuriating, third delay with no explanation.") == "negative"


def test_filter_relevant_keeps_only_matches():
    d = TweetDetector()
    tweets = [
        {"text": "New Claude model benchmarks look impressive."},
        {"text": "Lunch was great today, had a burger."},
    ]
    filtered = d.filter_relevant(tweets, "AI")
    assert len(filtered) == 1
    assert filtered[0]["text"].startswith("New Claude")
