"""Guardrail: no AI/provider call may bypass the ai_client wrapper.

Scans the project source for an HTTP POST (requests/urllib/httpx) in a file
that ALSO references an AI provider endpoint or the AI key. Such a file is a
direct provider egress and must be the wrapper or a documented adapter.

This test FAILS if future code adds a new direct AI call outside the
allowlist — forcing it through ai_usage/services/ai_client.py instead.
"""
import os
import re

from django.conf import settings
from django.test import TestCase

# Files permitted to talk to the provider directly (documented exceptions).
ALLOWED = {
    # The single wrapper / egress.
    os.path.join("ai_usage", "services", "ai_client.py"),
    # Local-first router transport — self-logs usage at the funnel (12A.1).
    os.path.join("factory", "services", "llm_router.py"),
    # Realtime control-plane: mints the ephemeral client_secret. No token
    # usage here; the session is logged via ai_client.log_realtime_session_start.
    os.path.join("tutor", "services", "realtime_session.py"),
    # Realtime SDP relay: passes the browser's ephemeral token + SDP through.
    # Carries no AI usage (pure WebRTC handshake relay).
    os.path.join("tutor", "api", "views.py"),
}

AI_ENDPOINTS = (
    "/chat/completions", "/audio/speech", "/audio/transcriptions",
    "/images/generations", "/embeddings", "/realtime/client_secrets",
    "/realtime/calls",
)
POST_CALL = re.compile(r"\b(requests\.(post|request)|urllib\.request\.urlopen|httpx\.(post|stream))\s*\(")

SKIP_DIRS = {".venv", "venv", "node_modules", "static", "staticfiles",
             "media", "migrations", "__pycache__", ".git", "docs"}


class NoDirectAICallsTest(TestCase):
    def test_no_direct_ai_provider_calls_outside_wrapper(self):
        root = str(settings.BASE_DIR)
        offenders = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            # Skip any test directory / test module.
            if os.path.basename(dirpath) == "tests":
                continue
            for fn in filenames:
                if not fn.endswith(".py") or fn.startswith("test_"):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                if rel in ALLOWED:
                    continue
                try:
                    text = open(full, encoding="utf-8").read()
                except (OSError, UnicodeDecodeError):
                    continue
                if not POST_CALL.search(text):
                    continue
                if any(ep in text for ep in AI_ENDPOINTS):
                    offenders.append(rel)
        self.assertEqual(
            offenders, [],
            "Direct AI provider call(s) found outside the ai_client wrapper / "
            f"documented adapters: {offenders}. Route them through "
            "ai_usage.services.ai_client.",
        )
