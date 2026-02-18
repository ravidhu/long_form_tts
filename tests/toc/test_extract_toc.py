"""Tests for extract_toc — mock pymupdf."""

from unittest.mock import MagicMock, patch

from shared.pdf_parser.extract_toc import extract_toc


class TestExtractToc:
    """Unit tests for extract_toc() with mocked pymupdf — verifies 1-based
    to 0-based page conversion, negative page filtering, empty TOC handling,
    and whitespace stripping."""

    def test_normal_entries_converted_to_0_indexed(self):
        mock_doc = MagicMock()
        mock_doc.get_toc.return_value = [
            [1, "Chapter 1", 10],
            [1, "Chapter 2", 25],
            [2, "Section 2.1", 26],
        ]

        with patch("shared.pdf_parser.extract_toc.pymupdf") as mock_pymupdf:
            mock_pymupdf.open.return_value = mock_doc
            entries = extract_toc("/fake/book.pdf")

        assert len(entries) == 3
        assert entries[0].page == 9   # 10 - 1
        assert entries[1].page == 24  # 25 - 1
        assert entries[2].page == 25  # 26 - 1
        assert entries[2].level == 2

    def test_skips_negative_pages(self):
        mock_doc = MagicMock()
        mock_doc.get_toc.return_value = [
            [1, "Bad Entry", 0],   # page_1based=0 → page_0=-1 → skip
            [1, "Good Entry", 1],  # page_1based=1 → page_0=0 → keep
        ]

        with patch("shared.pdf_parser.extract_toc.pymupdf") as mock_pymupdf:
            mock_pymupdf.open.return_value = mock_doc
            entries = extract_toc("/fake/book.pdf")

        assert len(entries) == 1
        assert entries[0].title == "Good Entry"

    def test_empty_toc(self):
        mock_doc = MagicMock()
        mock_doc.get_toc.return_value = []

        with patch("shared.pdf_parser.extract_toc.pymupdf") as mock_pymupdf:
            mock_pymupdf.open.return_value = mock_doc
            entries = extract_toc("/fake/book.pdf")

        assert entries == []

    def test_title_whitespace_stripped(self):
        mock_doc = MagicMock()
        mock_doc.get_toc.return_value = [
            [1, "  Chapter 1  ", 5],
        ]

        with patch("shared.pdf_parser.extract_toc.pymupdf") as mock_pymupdf:
            mock_pymupdf.open.return_value = mock_doc
            entries = extract_toc("/fake/book.pdf")

        assert entries[0].title == "Chapter 1"
