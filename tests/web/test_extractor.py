"""Tests for fetch_url_content() — mock trafilatura.

Uses monkeypatch to replace the ``trafilatura`` module reference inside the
already-imported ``fetch_url_content`` module so no real HTTP calls are made.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest

from shared.web_parser.fetch_url_content import fetch_url_content

# The __init__.py re-export shadows the submodule name, so grab the actual
# module object from sys.modules for monkeypatching.
_fetch_mod = sys.modules["shared.web_parser.fetch_url_content"]


@pytest.fixture
def mock_trafilatura(monkeypatch):
    """Patch the trafilatura reference inside the already-imported module."""
    mod = types.ModuleType("trafilatura")
    mod.fetch_url = MagicMock()
    mod.extract = MagicMock()
    monkeypatch.setattr(_fetch_mod, "trafilatura", mod)
    return mod


class TestSuccess:
    """Happy path — trafilatura fetches HTML and extracts markdown content."""

    def test_returns_extracted_markdown(self, mock_trafilatura):
        mock_trafilatura.fetch_url.return_value = "<html>hello</html>"
        mock_trafilatura.extract.return_value = "# Hello\n\nWorld"

        result = fetch_url_content("https://example.com")

        assert result == "# Hello\n\nWorld"
        mock_trafilatura.fetch_url.assert_called_once_with("https://example.com")
        mock_trafilatura.extract.assert_called_once()


class TestFetchFailure:
    """trafilatura.fetch_url returns None → RuntimeError raised."""

    def test_fetch_url_returns_none_raises_runtime_error(self, mock_trafilatura):
        mock_trafilatura.fetch_url.return_value = None

        with pytest.raises(RuntimeError, match="Failed to fetch URL"):
            fetch_url_content("https://bad.example.com")


class TestExtractFailure:
    """trafilatura.extract returns empty or None → RuntimeError raised."""

    def test_extract_returns_empty_raises_runtime_error(self, mock_trafilatura):
        mock_trafilatura.fetch_url.return_value = "<html>ok</html>"
        mock_trafilatura.extract.return_value = ""

        with pytest.raises(RuntimeError, match="No extractable content"):
            fetch_url_content("https://empty.example.com")

    def test_extract_returns_none_raises_runtime_error(self, mock_trafilatura):
        mock_trafilatura.fetch_url.return_value = "<html>ok</html>"
        mock_trafilatura.extract.return_value = None

        with pytest.raises(RuntimeError, match="No extractable content"):
            fetch_url_content("https://none.example.com")
