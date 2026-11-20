"""Price table and cost computation (USD per million tokens), with where each price comes from."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

DEEPSEEK_PRICING_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing"
DEEPSEEK_PRICING_READ_ON = "2026-11-20"
ANTHROPIC_PRICING_SOURCE = "Claude API reference, models table"
ANTHROPIC_PRICING_CACHED_ON = "2026-11-03"

# DeepSeek peak hours (UTC): 01:00-04:00 and 06:00-10:00, Monday to Friday. Chinese public
# holidays are not modelled, so the cost is overstated on those days.
_PEAK_HOURS = frozenset({1, 2, 3, 6, 7, 8, 9})
_OFF_PEAK_FACTOR = 0.5


class Price(BaseModel):
    """USD per million tokens."""

    model_config = ConfigDict(frozen=True)

    input: float
    cache_hit: float
    output: float

    def scaled(self, factor: float) -> Price:
        """Return the price multiplied by `factor` (off-peak discount)."""
        return Price(
            input=self.input * factor,
            cache_hit=self.cache_hit * factor,
            output=self.output * factor,
        )


# Peak prices; off-peak is half.
DEEPSEEK_PEAK: dict[str, Price] = {
    "deepseek-flash": Price(input=0.30, cache_hit=0.006, output=1.20),
    "deepseek-v4-pro": Price(input=1.32, cache_hit=0.044, output=3.96),
}
# A retired alias, billed as flash.
MODEL_ALIASES: dict[str, str] = {"deepseek-v4-flash": "deepseek-flash"}

ANTHROPIC: dict[str, Price] = {
    "claude-opus-5-5": Price(input=4.0, cache_hit=0.20, output=20.0),
    "claude-sonnet-5-5": Price(input=2.0, cache_hit=0.10, output=10.0),
    # Up to 100K-token prompts. Cache-read price not listed: billed at the input price,
    # an overestimate.
    "claude-haiku-5-5": Price(input=0.10, cache_hit=0.10, output=0.50),
}

FREE = Price(input=0.0, cache_hit=0.0, output=0.0)


def is_deepseek_peak(at: datetime) -> bool:
    """Whether `at` falls in DeepSeek's peak window (weekday, UTC hours above)."""
    utc = at.astimezone(UTC)
    return utc.weekday() < 5 and utc.hour in _PEAK_HOURS


def price_for(model: str, at: datetime | None = None) -> Price | None:
    """Return the price of `model` at time `at`, or None when it is not in the table."""
    when = at or datetime.now(UTC)
    key = MODEL_ALIASES.get(model, model)
    if key == "fake":
        return FREE
    if key in DEEPSEEK_PEAK:
        peak = DEEPSEEK_PEAK[key]
        return peak if is_deepseek_peak(when) else peak.scaled(_OFF_PEAK_FACTOR)
    return ANTHROPIC.get(key)


def cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_hit_tokens: int = 0,
    at: datetime | None = None,
) -> float | None:
    """Cost of one call. `input_tokens` includes the cache hits, priced apart."""
    price = price_for(model, at)
    if price is None:
        return None
    hit = min(max(cache_hit_tokens, 0), input_tokens)
    total = (
        (input_tokens - hit) * price.input + hit * price.cache_hit + output_tokens * price.output
    )
    return total / 1_000_000
