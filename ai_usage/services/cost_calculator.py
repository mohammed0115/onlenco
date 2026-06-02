"""Cost calculation — always from ``AIModelPricing``, never hardcoded.

All money is ``Decimal``. Missing pricing returns 0 and logs a warning;
it never raises (a user request must not fail because a price row is absent).
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from ..models import AIModelPricing

logger = logging.getLogger(__name__)

# Round money to 6 dp internally; the DB column matches.
_QUANT = Decimal("0.000001")
_MILLION = Decimal("1000000")
_SECONDS_PER_MINUTE = Decimal("60")


def safe_decimal(value, default: str = "0") -> Decimal:
    """Coerce anything to Decimal without raising. Floats go via str()
    so we don't inherit binary-float noise."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _round(amount: Decimal) -> Decimal:
    return safe_decimal(amount).quantize(_QUANT, rounding=ROUND_HALF_UP)


def get_active_pricing(provider: str, model_name: str, at_datetime=None):
    """Active ``AIModelPricing`` row, or ``None`` (caller treats as zero cost)."""
    return AIModelPricing.get_active(provider, model_name, at_datetime)


def calculate_token_cost(provider: str, model_name: str,
                         input_tokens: int, output_tokens: int,
                         at_datetime=None) -> Decimal:
    """USD cost of token usage. 0 (warned) when no price row exists."""
    pricing = get_active_pricing(provider, model_name, at_datetime)
    if pricing is None:
        logger.warning(
            "ai_usage.cost: no active pricing for %s:%s — token cost charged as 0",
            provider, model_name,
        )
        return Decimal("0")
    in_tok = safe_decimal(input_tokens)
    out_tok = safe_decimal(output_tokens)
    cost = (
        in_tok / _MILLION * safe_decimal(pricing.input_price_per_1m_tokens)
        + out_tok / _MILLION * safe_decimal(pricing.output_price_per_1m_tokens)
    )
    return _round(cost)


def calculate_audio_cost(provider: str, model_name: str,
                         audio_input_seconds: int, audio_output_seconds: int,
                         at_datetime=None) -> Decimal:
    """USD cost of audio usage (per-minute pricing). 0 (warned) when unpriced."""
    pricing = get_active_pricing(provider, model_name, at_datetime)
    if pricing is None:
        logger.warning(
            "ai_usage.cost: no active pricing for %s:%s — audio cost charged as 0",
            provider, model_name,
        )
        return Decimal("0")
    in_min = safe_decimal(audio_input_seconds) / _SECONDS_PER_MINUTE
    out_min = safe_decimal(audio_output_seconds) / _SECONDS_PER_MINUTE
    in_rate = safe_decimal(pricing.audio_input_price_per_minute)
    out_rate = safe_decimal(pricing.audio_output_price_per_minute)
    cost = in_min * in_rate + out_min * out_rate
    return _round(cost)


def calculate_image_cost(provider: str, model_name: str, n_images: int = 1,
                         at_datetime=None) -> Decimal:
    """USD cost of image generation. 0 (warned) when no image pricing exists.

    Uses per-image or per-1k-images pricing per the row's ``image_pricing_unit``.
    """
    pricing = get_active_pricing(provider, model_name, at_datetime)
    if pricing is None:
        logger.warning(
            "ai_usage.cost: no active pricing for %s:%s — image cost charged as 0",
            provider, model_name,
        )
        return Decimal("0")
    n = safe_decimal(n_images)
    unit = getattr(pricing, "image_pricing_unit", "per_image")
    if unit == "per_1k_images" and pricing.image_price_per_1k_images is not None:
        return _round(n / Decimal("1000") * safe_decimal(pricing.image_price_per_1k_images))
    if pricing.image_price_per_generation is not None:
        return _round(n * safe_decimal(pricing.image_price_per_generation))
    logger.warning(
        "ai_usage.cost: no image price set for %s:%s — image cost charged as 0",
        provider, model_name,
    )
    return Decimal("0")


def calculate_total_cost(provider: str, model_name: str, *,
                         input_tokens: int = 0, output_tokens: int = 0,
                         audio_input_seconds: int = 0, audio_output_seconds: int = 0,
                         at_datetime=None) -> Decimal:
    """Token + audio cost in one call (one pricing lookup per sub-cost)."""
    token = calculate_token_cost(
        provider, model_name, input_tokens, output_tokens, at_datetime,
    )
    audio = calculate_audio_cost(
        provider, model_name, audio_input_seconds, audio_output_seconds, at_datetime,
    )
    return _round(token + audio)
