"""Server settings, read once from the environment into a frozen model."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """Limits and budgets of the server (defaults: docs/generation.md)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_timeout_s: float = Field(default=20.0, gt=0)
    max_output_tokens: int = Field(default=600, gt=0)
    daily_budget_usd: float = Field(default=1.0, ge=0)
    ask_per_minute: int = Field(default=10, gt=0)
    search_per_minute: int = Field(default=60, gt=0)
    # Read the client address from X-Forwarded-For (only behind a reverse proxy we control).
    trust_proxy: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build the settings from `SEXTANT_*` variables; absent ones keep their default."""
        source = os.environ if env is None else env
        names = {
            "request_timeout_s": "SEXTANT_REQUEST_TIMEOUT_S",
            "max_output_tokens": "SEXTANT_MAX_OUTPUT_TOKENS",
            "daily_budget_usd": "SEXTANT_DAILY_BUDGET_USD",
            "ask_per_minute": "SEXTANT_ASK_PER_MINUTE",
            "search_per_minute": "SEXTANT_SEARCH_PER_MINUTE",
            "trust_proxy": "SEXTANT_TRUST_PROXY",
        }
        values = {field: source[var] for field, var in names.items() if source.get(var)}
        return cls.model_validate(values)
