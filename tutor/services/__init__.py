"""Tutor services package.

Backwards-compatible: `from tutor.services import chat` still works.
"""
from ._chat import chat  # noqa: F401
from .context_builder import build_tutor_context, render_context_block  # noqa: F401
from .tts import synthesize  # noqa: F401
