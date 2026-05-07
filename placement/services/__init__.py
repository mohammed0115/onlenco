"""Placement services package.

Backwards-compatible: existing imports `from placement.services import assess`
continue to work because `_assessor.assess` is re-exported here.
"""
from ._assessor import assess  # noqa: F401
from .diagnostic_engine import build_diagnostic_profile  # noqa: F401
from .stt import fluency_score, pronunciation_score, transcribe  # noqa: F401
