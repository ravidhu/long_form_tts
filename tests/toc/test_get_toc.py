"""Tests for _get_toc — chooses embedded vs inferred."""

from unittest.mock import MagicMock, patch

from shared.pdf_parser.resolve_content import _get_toc
from shared.pdf_parser.types import TOCEntry


class TestGetToc:
    """Unit tests for _get_toc() dispatch logic — uses embedded TOC when page
    coverage exceeds 30%, falls back to infer_toc when sparse or empty."""

    def test_uses_embedded_when_coverage_above_30_percent(self):
        embedded = [
            TOCEntry(level=1, title="Ch1", page=5),
            TOCEntry(level=1, title="Ch2", page=50),
        ]
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=100)

        with patch("shared.pdf_parser.resolve_content.extract_toc", return_value=embedded), \
             patch("shared.pdf_parser.resolve_content.pymupdf") as mock_pymupdf, \
             patch("shared.pdf_parser.resolve_content.infer_toc") as mock_infer:
            mock_pymupdf.open.return_value = mock_doc
            result = _get_toc("/fake/book.pdf")

        assert result == embedded
        mock_infer.assert_not_called()

    def test_falls_back_when_embedded_sparse(self):
        # Embedded TOC only covers first 20% of pages
        embedded = [
            TOCEntry(level=1, title="Preface", page=5),
            TOCEntry(level=1, title="Intro", page=15),
        ]
        inferred = [
            TOCEntry(level=1, title="Ch1", page=30),
            TOCEntry(level=1, title="Ch2", page=60),
        ]
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=100)

        with patch("shared.pdf_parser.resolve_content.extract_toc", return_value=embedded), \
             patch("shared.pdf_parser.resolve_content.pymupdf") as mock_pymupdf, \
             patch("shared.pdf_parser.resolve_content.infer_toc", return_value=inferred):
            mock_pymupdf.open.return_value = mock_doc
            result = _get_toc("/fake/book.pdf")

        assert result == inferred

    def test_falls_back_when_embedded_empty(self):
        inferred = [TOCEntry(level=1, title="Ch1", page=10)]

        with patch("shared.pdf_parser.resolve_content.extract_toc", return_value=[]), \
             patch("shared.pdf_parser.resolve_content.infer_toc", return_value=inferred):
            result = _get_toc("/fake/book.pdf")

        assert result == inferred

    def test_coverage_boundary_at_exactly_30_percent(self):
        # max_page=29 on a 100-page doc → 29 < 30 → sparse
        embedded = [TOCEntry(level=1, title="Ch", page=29)]
        inferred = [TOCEntry(level=1, title="Inferred", page=50)]
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=100)

        with patch("shared.pdf_parser.resolve_content.extract_toc", return_value=embedded), \
             patch("shared.pdf_parser.resolve_content.pymupdf") as mock_pymupdf, \
             patch("shared.pdf_parser.resolve_content.infer_toc", return_value=inferred):
            mock_pymupdf.open.return_value = mock_doc
            result = _get_toc("/fake/book.pdf")

        assert result == inferred
