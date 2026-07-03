from src.api.rate_limit import SlidingWindowRateLimiter


def test_rate_limiter_blocks_after_limit_within_window() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    key = "client:admin"

    assert limiter.allow(key)
    assert limiter.allow(key)
    assert not limiter.allow(key)
