from x_scraper.browser import (
    BLOCKED_ASSET_HOST_SUFFIXES,
    BLOCKED_DOMAINS,
    BLOCKED_RESOURCE_TYPES,
    TWEET_SELECTOR,
)


def test_tweet_selector_targets_dom_articles():
    assert TWEET_SELECTOR == 'article[data-testid="tweet"]'


def test_blocks_heavy_resource_types():
    assert {"image", "media", "font", "stylesheet"} <= BLOCKED_RESOURCE_TYPES


def test_blocks_noise_resource_types():
    assert {"manifest", "texttrack", "eventsource", "ping", "other"} <= BLOCKED_RESOURCE_TYPES


def test_essential_resource_types_stay_allowed():
    assert not {"document", "script", "xhr", "fetch"} & BLOCKED_RESOURCE_TYPES


def test_blocks_known_ad_and_analytics_domains():
    assert "google-analytics.com" in BLOCKED_DOMAINS
    assert "doubleclick.net" in BLOCKED_DOMAINS


def test_blocks_twimg_asset_cdn():
    assert "pbs.twimg.com" in BLOCKED_ASSET_HOST_SUFFIXES
