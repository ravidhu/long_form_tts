"""Tests for resolve_input() — webpage URL detection."""

from unittest.mock import MagicMock, patch

import requests as _real_requests
from configs.common import InputSource, resolve_input


class TestWebpageUrl:
    """Non-PDF URLs (HTML, text, or HEAD-failure) are returned as kind="url"
    for downstream webpage extraction via trafilatura."""

    def test_html_content_type_returns_url_source(self):
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}

        with patch("requests.head", return_value=mock_resp):
            result = resolve_input("https://example.com/article")

        assert result == InputSource("url", "https://example.com/article")

    def test_head_failure_falls_through_to_webpage(self):
        with patch("requests.head", side_effect=_real_requests.RequestException("fail")):
            result = resolve_input("https://flaky.example.com/page")

        assert result == InputSource("url", "https://flaky.example.com/page")

    def test_non_pdf_content_type_returns_url_source(self):
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "text/plain"}

        with patch("requests.head", return_value=mock_resp):
            result = resolve_input("https://example.com/readme")

        assert result == InputSource("url", "https://example.com/readme")
