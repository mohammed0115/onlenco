"""Analytics services package.

Backwards-compatible: `from analytics.services import compute_metrics`
keeps working even though we now ship multiple services.
"""
from .metrics import compute_metrics  # noqa: F401
from .scoring import (  # noqa: F401
    churn_risk,
    engagement_score,
    improvement_trend,
    learning_speed_for,
    persist_for_all,
    persist_for_user,
)
