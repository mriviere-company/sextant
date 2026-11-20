from datetime import UTC, datetime

from fakes import ManualClock

from sextant.generation.budget import DailyBudget, Deadline, RateLimiter


def test_daily_budget_exhausts_and_resets_at_midnight_utc() -> None:
    now = [datetime(2026, 11, 20, 23, 59, tzinfo=UTC)]
    budget = DailyBudget(1.0, lambda: now[0])
    budget.add(0.6)
    assert not budget.exhausted()
    budget.add(0.5)
    assert budget.exhausted()
    now[0] = datetime(2026, 11, 21, 0, 0, tzinfo=UTC)
    assert not budget.exhausted()
    assert budget.spent_usd == 0.0


def test_zero_budget_is_always_exhausted() -> None:
    assert DailyBudget(0.0).exhausted()


def test_rate_limiter_blocks_over_the_limit_with_a_retry_after() -> None:
    clock = ManualClock()
    limiter = RateLimiter(2, clock)
    assert limiter.acquire("a") == 0.0
    clock.advance(10)
    assert limiter.acquire("a") == 0.0
    clock.advance(5)
    wait = limiter.acquire("a")
    assert 44.9 < wait <= 45.0  # the first hit leaves the window 60 s after it happened
    assert limiter.acquire("b") == 0.0  # keys are independent
    clock.advance(wait)
    assert limiter.acquire("a") == 0.0


def test_rate_limiter_does_not_count_refused_requests() -> None:
    clock = ManualClock()
    limiter = RateLimiter(1, clock)
    assert limiter.acquire("a") == 0.0
    for _ in range(5):
        assert limiter.acquire("a") > 0
    clock.advance(60)
    assert limiter.acquire("a") == 0.0


def test_deadline_counts_down() -> None:
    clock = ManualClock()
    deadline = Deadline(20, clock)
    assert deadline.remaining() == 20
    clock.advance(25)
    assert deadline.expired()
    assert deadline.remaining() == -5
