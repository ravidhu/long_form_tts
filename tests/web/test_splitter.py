"""Tests for split_by_headings() — pure function, no mocks needed."""

from shared.web_parser.split_by_headings import WebSection, split_by_headings


class TestNoHeadings:
    """Markdown with no headings (or invalid heading syntax) returns a single
    "Full article" section containing all content."""

    def test_plain_text_returns_single_section(self):
        md = "Just some plain text without any headings."
        result = split_by_headings(md)
        assert len(result) == 1
        assert result[0].title == "Full article"
        assert result[0].content == md

    def test_empty_string(self):
        result = split_by_headings("")
        assert len(result) == 1
        assert result[0].title == "Full article"
        assert result[0].content == ""

    def test_hashes_without_space_not_treated_as_heading(self):
        md = "##not a heading\n\nSome text."
        result = split_by_headings(md)
        assert len(result) == 1
        assert result[0].title == "Full article"


class TestPreamble:
    """Text appearing before the first heading is captured as an
    "Introduction" section; no preamble section when the heading is first."""

    def test_text_before_first_heading_becomes_introduction(self):
        md = "Some preamble text.\n\n# First Section\n\nContent here."
        result = split_by_headings(md, max_level=1)
        assert result[0].title == "Introduction"
        assert result[0].content == "Some preamble text."
        assert result[1].title == "First Section"

    def test_no_preamble_when_heading_is_first(self):
        md = "# Title\n\nContent."
        result = split_by_headings(md, max_level=1)
        assert result[0].title == "Title"
        assert len(result) == 1


class TestMaxLevel:
    """max_level controls which heading depths trigger splits — level 1 splits
    only on #, level 2 splits on # and ##, deeper headings are folded in."""

    def test_max_level_1_ignores_h2(self):
        md = "# Chapter 1\n\nIntro.\n\n## Section 1.1\n\nDetail.\n\n# Chapter 2\n\nMore."
        result = split_by_headings(md, max_level=1)
        titles = [s.title for s in result]
        assert "Chapter 1" in titles
        assert "Chapter 2" in titles
        assert "Section 1.1" not in titles

    def test_max_level_2_splits_on_h1_and_h2(self):
        md = "# Chapter 1\n\nIntro.\n\n## Section 1.1\n\nDetail.\n\n# Chapter 2\n\nMore."
        result = split_by_headings(md, max_level=2)
        titles = [s.title for s in result]
        assert "Chapter 1" in titles
        assert "Section 1.1" in titles
        assert "Chapter 2" in titles

    def test_max_level_2_ignores_h3(self):
        md = "## A\n\nText.\n\n### B\n\nMore.\n\n## C\n\nEnd."
        result = split_by_headings(md, max_level=2)
        titles = [s.title for s in result]
        assert "A" in titles
        assert "C" in titles
        assert "B" not in titles


class TestEmptySections:
    """Headings with no content (immediately followed by another heading or
    containing only whitespace) are dropped from the output."""

    def test_heading_immediately_followed_by_heading_is_skipped(self):
        md = "# Empty\n# Has Content\n\nSome text."
        result = split_by_headings(md, max_level=1)
        titles = [s.title for s in result]
        assert "Empty" not in titles
        assert "Has Content" in titles

    def test_heading_with_only_whitespace_is_skipped(self):
        md = "# Empty\n\n   \n\n# Real\n\nContent."
        result = split_by_headings(md, max_level=1)
        titles = [s.title for s in result]
        assert "Empty" not in titles
        assert "Real" in titles


class TestContentBoundaries:
    """Each section receives exactly the text between its heading and the
    next heading, with no overlap or loss."""

    def test_each_section_gets_exactly_its_text(self):
        md = "# A\n\nAlpha text.\n\n# B\n\nBeta text.\n\n# C\n\nGamma text."
        result = split_by_headings(md, max_level=1)
        assert len(result) == 3
        assert result[0] == WebSection("A", "Alpha text.")
        assert result[1] == WebSection("B", "Beta text.")
        assert result[2] == WebSection("C", "Gamma text.")
