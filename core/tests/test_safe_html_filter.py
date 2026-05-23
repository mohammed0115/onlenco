"""Pin the contract of the ``|safe_html`` template filter — the one
filter that stands between teacher-authored HTML and student browsers.
"""
from __future__ import annotations

from django.template import Context, Template
from django.test import TestCase


def _render(content_html: str) -> str:
    """Render ``{{ x|safe_html }}`` over an arbitrary string."""
    t = Template("{% load sanitize %}{{ x|safe_html }}")
    return t.render(Context({"x": content_html}))


class SafeHtmlFilterTests(TestCase):
    def test_strips_script_tags(self):
        out = _render('<p>Hello</p><script>alert("xss")</script>')
        self.assertIn("<p>Hello</p>", out)
        # The dangerous bits — the <script> tag itself + its closing tag — are gone.
        # The literal text "alert" may survive (bleach strips tags but
        # preserves visible text); that's safe because text cannot execute.
        self.assertNotIn("<script", out)
        self.assertNotIn("</script>", out)

    def test_strips_inline_event_handlers(self):
        out = _render('<img src="x" onerror="alert(1)">')
        # The img tag itself stays (we allow images), but the
        # onerror handler must be gone.
        self.assertNotIn("onerror", out)
        self.assertNotIn("alert", out)

    def test_strips_javascript_url_in_anchors(self):
        out = _render('<a href="javascript:alert(1)">click</a>')
        self.assertNotIn("javascript:", out)

    def test_keeps_safe_links(self):
        out = _render('<a href="https://example.com">click</a>')
        self.assertIn('href="https://example.com"', out)

    def test_keeps_basic_formatting(self):
        out = _render(
            "<h2>Title</h2><p><strong>Bold</strong> and <em>italic</em>."
            "</p><ul><li>one</li></ul>"
        )
        for tag in ("<h2>", "<p>", "<strong>", "<em>", "<ul>", "<li>"):
            self.assertIn(tag, out)

    def test_empty_value_returns_empty(self):
        self.assertEqual(_render(""), "")
        self.assertEqual(_render(None), "")

    def test_output_is_marked_safe(self):
        """The filter must mark its output safe so the template doesn't
        double-escape the bleached HTML."""
        out = _render("<p>x</p>")
        # If marked_safe failed, the < / > would be HTML-encoded.
        self.assertIn("<p>x</p>", out)
        self.assertNotIn("&lt;p&gt;", out)
