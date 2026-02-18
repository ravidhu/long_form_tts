"""Tests for resolve_input() — local file paths."""

from configs.common import InputSource, resolve_input


class TestLocalPath:
    """Local file paths (absolute and relative) are returned as-is with
    kind="pdf", no network calls."""

    def test_local_path_returns_pdf_source(self):
        result = resolve_input("/some/local/file.pdf")
        assert result == InputSource("pdf", "/some/local/file.pdf")

    def test_relative_path_returns_pdf_source(self):
        result = resolve_input("inputs/book.pdf")
        assert result == InputSource("pdf", "inputs/book.pdf")
