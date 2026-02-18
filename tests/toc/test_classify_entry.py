"""Tests for _classify_entry — parametrized pattern matching."""

import pytest

from shared.pdf_parser.classify_entry import classify_entry
from shared.pdf_parser.types import TOCEntry


class TestClassifyEntry:
    """Verify classify_entry regex patterns correctly bucket TOC titles
    into front matter, back matter, preamble, or content categories."""

    @pytest.mark.parametrize("title,expected", [
        ("Cover", "front"),
        ("cover", "front"),
        ("Half Title", "front"),
        ("Title Page", "front"),
        ("Copyright", "front"),
        ("Table of Contents", "front"),
        ("Contents", "front"),
        ("List of Figures", "front"),
        ("List of Tables", "front"),
        ("Dedication", "front"),
        ("Epigraph", "front"),
        ("Praise for the Book", "front"),
        ("Endorsements", "front"),
        ("Also by Author", "front"),
        ("About the Cover", "front"),
    ])
    def test_front_matter(self, title, expected):
        entry = TOCEntry(level=1, title=title, page=0)
        assert classify_entry(entry) == expected

    @pytest.mark.parametrize("title,expected", [
        ("Index", "back"),
        ("Glossary", "back"),
        ("Bibliography", "back"),
        ("References", "back"),
        ("About the Author", "back"),
        ("About the Authors", "back"),
        ("Colophon", "back"),
        ("Appendix A", "back"),
    ])
    def test_back_matter(self, title, expected):
        entry = TOCEntry(level=1, title=title, page=100)
        assert classify_entry(entry) == expected

    @pytest.mark.parametrize("title,expected", [
        ("Foreword", "preamble"),
        ("Preface", "preamble"),
        ("Introduction", "preamble"),
        ("Acknowledgments", "preamble"),
    ])
    def test_preamble(self, title, expected):
        entry = TOCEntry(level=1, title=title, page=5)
        assert classify_entry(entry) == expected

    @pytest.mark.parametrize("title", [
        "Chapter 1: Getting Started",
        "1. Foundations",
        "Part I",
        "Data Pipelines",
        "Advanced Topics",
    ])
    def test_content(self, title):
        entry = TOCEntry(level=1, title=title, page=10)
        assert classify_entry(entry) == "content"
