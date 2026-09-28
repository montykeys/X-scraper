from x_scraper.parse import iter_tweets

SAMPLE_ENTRY = {
    "content": {
        "itemContent": {
            "tweet_results": {
                "result": {
                    "rest_id": "123",
                    "legacy": {
                        "full_text": "hello world",
                        "created_at": "Mon Jan 01 00:00:00 +0000 2024",
                        "favorite_count": 5,
                        "retweet_count": 1,
                        "reply_count": 0,
                    },
                    "core": {
                        "user_results": {
                            "result": {"legacy": {"screen_name": "someuser"}}
                        }
                    },
                }
            }
        }
    }
}

PAYLOAD = {
    "data": {
        "user": {
            "result": {
                "timeline": {
                    "timeline": {
                        "instructions": [
                            {"type": "TimelineAddEntries", "entries": [SAMPLE_ENTRY]}
                        ]
                    }
                }
            }
        }
    }
}


def test_iter_tweets_extracts_fields():
    tweets = list(iter_tweets(PAYLOAD))
    assert len(tweets) == 1
    t = tweets[0]
    assert t["id"] == "123"
    assert t["text"] == "hello world"
    assert t["author"] == "someuser"
    assert t["like_count"] == 5


def test_iter_tweets_empty_payload():
    assert list(iter_tweets({})) == []
