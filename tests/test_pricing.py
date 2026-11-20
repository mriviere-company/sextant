from datetime import UTC, datetime

import pytest

from sextant.generation.pricing import cost_usd, is_deepseek_peak, price_for

PEAK = datetime(2026, 11, 18, 7, 0, tzinfo=UTC)  # Wednesday 07:00 UTC
OFF_PEAK_HOUR = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)  # Wednesday 12:00 UTC
WEEKEND = datetime(2026, 11, 21, 7, 0, tzinfo=UTC)  # Saturday 07:00 UTC


def test_peak_window_boundaries() -> None:
    assert is_deepseek_peak(datetime(2026, 11, 18, 1, 0, tzinfo=UTC))
    assert is_deepseek_peak(datetime(2026, 11, 18, 3, 59, tzinfo=UTC))
    assert not is_deepseek_peak(datetime(2026, 11, 18, 4, 0, tzinfo=UTC))
    assert not is_deepseek_peak(datetime(2026, 11, 18, 5, 59, tzinfo=UTC))
    assert is_deepseek_peak(datetime(2026, 11, 18, 9, 59, tzinfo=UTC))
    assert not is_deepseek_peak(datetime(2026, 11, 18, 10, 0, tzinfo=UTC))


def test_deepseek_peak_versus_off_peak() -> None:
    peak = cost_usd("deepseek-flash", input_tokens=1_000_000, output_tokens=1_000_000, at=PEAK)
    off = cost_usd("deepseek-flash", input_tokens=1_000_000, output_tokens=1_000_000, at=WEEKEND)
    assert peak == pytest.approx(0.30 + 1.20)
    assert off == pytest.approx((0.30 + 1.20) / 2)
    assert cost_usd(
        "deepseek-flash", input_tokens=1_000_000, output_tokens=0, at=OFF_PEAK_HOUR
    ) == pytest.approx(0.15)


def test_cache_hit_tokens_are_priced_apart() -> None:
    cost = cost_usd(
        "deepseek-flash", input_tokens=1_000_000, output_tokens=0, cache_hit_tokens=400_000, at=PEAK
    )
    assert cost == pytest.approx(600_000 * 0.30 / 1e6 + 400_000 * 0.006 / 1e6)


def test_v4_flash_alias_is_billed_as_flash() -> None:
    assert price_for("deepseek-v4-flash", PEAK) == price_for("deepseek-flash", PEAK)


def test_deepseek_pro_prices() -> None:
    cost = cost_usd("deepseek-v4-pro", input_tokens=1_000_000, output_tokens=1_000_000, at=PEAK)
    assert cost == pytest.approx(1.32 + 3.96)


def test_anthropic_cost_ignores_time_of_day() -> None:
    kwargs = {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_hit_tokens": 500_000}
    assert cost_usd("claude-opus-5-5", at=PEAK, **kwargs) == pytest.approx(
        500_000 * 4 / 1e6 + 500_000 * 0.20 / 1e6 + 100_000 * 20 / 1e6
    )
    assert cost_usd("claude-opus-5-5", at=PEAK, **kwargs) == cost_usd(
        "claude-opus-5-5", at=WEEKEND, **kwargs
    )
    assert cost_usd("claude-sonnet-5-5", input_tokens=1_000_000, output_tokens=0) == pytest.approx(
        2
    )
    assert cost_usd("claude-haiku-5-5", input_tokens=0, output_tokens=1_000_000) == pytest.approx(
        0.5
    )


def test_fake_is_free_and_unknown_model_has_no_cost() -> None:
    assert cost_usd("fake", input_tokens=100, output_tokens=100) == 0.0
    assert cost_usd("mystery-model", input_tokens=100, output_tokens=100) is None
