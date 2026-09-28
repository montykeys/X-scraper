from x_scraper.browser import BLOCKED_RESOURCE_TYPES, TWEET_SELECTOR


def test_tweet_selector_targets_dom_articles():
    assert TWEET_SELECTOR == 'article[data-testid="tweet"]'


def test_blocks_heavy_resource_types():
    assert {"image", "media", "font", "stylesheet"} <= BLOCKED_RESOURCE_TYPES
