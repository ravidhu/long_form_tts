"""Tests for resolve_input() — PDF URL detection and download."""

import os
from unittest.mock import MagicMock, patch

import requests as _real_requests  # noqa: F401
from configs.common import InputSource, resolve_input


class TestPdfUrl:
    """PDF URL detection — URLs ending in .pdf are downloaded; URLs with
    Content-Type application/pdf are detected via HEAD; cached files
    skip re-download."""

    def test_url_ending_pdf_downloads(self, tmp_path):
        dest = str(tmp_path / "downloads")
        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [b"fake-pdf-data"]
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = resolve_input(
                "https://example.com/papers/book.pdf", dest_dir=dest
            )

        assert result.kind == "pdf"
        assert result.path.endswith("book.pdf")
        assert os.path.dirname(result.path) == dest

    def test_cached_pdf_skips_download(self, tmp_path):
        dest = str(tmp_path / "downloads")
        os.makedirs(dest)
        cached = os.path.join(dest, "book.pdf")
        with open(cached, "wb") as f:
            f.write(b"cached")

        with patch("requests.get") as mock_get:
            result = resolve_input(
                "https://example.com/papers/book.pdf", dest_dir=dest
            )
            mock_get.assert_not_called()

        assert result == InputSource("pdf", cached)

    def test_content_type_pdf_on_non_pdf_url(self, tmp_path):
        dest = str(tmp_path / "downloads")
        mock_head_resp = MagicMock()
        mock_head_resp.headers = {"Content-Type": "application/pdf"}

        mock_get_resp = MagicMock()
        mock_get_resp.iter_content.return_value = [b"data"]
        mock_get_resp.raise_for_status = MagicMock()

        with patch("requests.head", return_value=mock_head_resp), \
             patch("requests.get", return_value=mock_get_resp):
            result = resolve_input(
                "https://cdn.example.com/serve?id=123", dest_dir=dest
            )

        assert result.kind == "pdf"
