from x_scraper.proxy_pool import ProxyPool


def test_pool_starts_empty():
    pool = ProxyPool()
    assert pool._live == []


def test_mark_dead_removes_from_live_and_blocks_reuse():
    pool = ProxyPool()
    pool._live = ["1.2.3.4:8080", "5.6.7.8:8080"]
    pool.mark_dead("1.2.3.4:8080")
    assert "1.2.3.4:8080" not in pool._live
    assert "1.2.3.4:8080" in pool._dead


async def test_get_round_robins_over_live_pool():
    pool = ProxyPool(min_pool_size=0)
    pool._live = ["a:1", "b:1"]
    pool._last_refresh = 10**12  # skip refresh
    first = await pool.get()
    second = await pool.get()
    third = await pool.get()
    assert [first, second, third] == ["a:1", "b:1", "a:1"]
