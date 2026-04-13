"""Tests for audiobook block splitting, focusing on research paper metadata detection."""

import sys
from pathlib import Path

# Ensure src/ is resolved before scripts/ so `audiobook` maps to the package,
# not the script.
_SRC = str(Path(__file__).resolve().parent.parent.parent / "src")
if _SRC not in sys.path or sys.path.index(_SRC) != 0:
    sys.path.insert(0, _SRC)

from audiobook.blocks import Block, split_into_blocks  # noqa: E402


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _kinds(blocks: list[Block]) -> list[str]:
    """Return just the kind of each block for easy assertion."""
    return [b.kind for b in blocks]


# ---------------------------------------------------------------------------
# Author affiliation blocks
# ---------------------------------------------------------------------------


class TestAuthorAffiliationBlocks:
    """Author blocks with ORCID links, affiliations, and emails."""

    SINGLE_AUTHOR = (
        "[Advait Sarkar](https://orcid.org/0000-0002-5401-3478)\n"
        "Microsoft Research\n"
        "Cambridge, United Kingdom\n"
        "advait@microsoft.com"
    )

    def test_single_author_block_is_metadata(self):
        blocks = split_into_blocks(self.SINGLE_AUTHOR)
        assert len(blocks) == 1
        assert blocks[0].kind == "metadata"
        assert "Cambridge, United Kingdom" in blocks[0].content

    def test_multiple_authors_separated_by_blank_lines(self):
        text = (
            "[Advait Sarkar](https://orcid.org/0000-0002-5401-3478)\n"
            "Microsoft Research\n"
            "Cambridge, United Kingdom\n"
            "advait@microsoft.com\n"
            "\n"
            "[Sean Rintel](https://orcid.org/0000-0003-0840-0546)\n"
            "Microsoft Research\n"
            "Cambridge, United Kingdom\n"
            "serintel@microsoft.com"
        )
        blocks = split_into_blocks(text)
        # Each author separated by blank line → two metadata blocks
        assert all(b.kind == "metadata" for b in blocks)
        assert len(blocks) == 2

    def test_author_with_us_affiliation(self):
        text = (
            "[Hao-Ping (Hank) Lee](https://orcid.org/0000-0002-8063-1034)\n"
            "Carnegie Mellon University\n"
            "Pittsburgh, Pennsylvania, USA\n"
            "haopingl@cs.cmu.edu"
        )
        blocks = split_into_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "metadata"


# ---------------------------------------------------------------------------
# ACM / IEEE reference format blocks
# ---------------------------------------------------------------------------


class TestReferenceFormatBlocks:
    """ACM Reference Format and similar bibliographic blocks."""

    def test_acm_reference_block(self):
        text = (
            "**ACM Reference Format:**\n"
            "Hao-Ping (Hank) Lee, Advait Sarkar, Lev Tankelevitch, Ian Drosos, Sean\n"
            "Rintel, Richard Banks, and Nicholas Wilson. 2025. The Impact of Generative\n"
            "AI on Critical Thinking: Self-Reported Reductions in Cognitive Effort and"
        )
        blocks = split_into_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "metadata"

    def test_license_and_venue_block(self):
        text = (
            "[This work is licensed under a Creative Commons Attribution 4.0 "
            "International License.](https://creativecommons.org/licenses/by/4.0)\n"
            "_CHI '25, Yokohama, Japan_\n"
            "\u00a9 2025 Copyright held by the owner/author(s).\n"
            "ACM ISBN 979-8-4007-1394-1/25/04\n"
            "[https://doi.org/10.1145/3706598.3713778]"
            "(https://doi.org/10.1145/3706598.3713778)"
        )
        blocks = split_into_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "metadata"
        assert "Yokohama" in blocks[0].content


# ---------------------------------------------------------------------------
# Running headers
# ---------------------------------------------------------------------------


class TestRunningHeaders:
    """Page headers/footers common in academic papers."""

    def test_running_header_et_al(self):
        text = "CHI '25, April 26\u2013May 01, 2025, Yokohama, Japan Lee et al."
        blocks = split_into_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "metadata"


# ---------------------------------------------------------------------------
# Keywords & CCS Concepts
# ---------------------------------------------------------------------------


class TestKeywordsAndCCS:
    """Keywords and CCS Concepts lines."""

    def test_keywords_heading_is_metadata(self):
        text = "**Keywords**"
        blocks = split_into_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "metadata"

    def test_ccs_concepts_is_metadata(self):
        text = "CCS Concepts"
        blocks = split_into_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "metadata"


# ---------------------------------------------------------------------------
# Real content is NOT captured as metadata
# ---------------------------------------------------------------------------


class TestContentNotCaptured:
    """Ensure real paragraphs after metadata are not swallowed."""

    def test_paragraph_after_metadata_block(self):
        text = (
            "advait@microsoft.com\n"
            "\n"
            "The rise of Generative AI in knowledge workflows raises "
            "questions about its impact on critical thinking skills."
        )
        blocks = split_into_blocks(text)
        kinds = _kinds(blocks)
        assert kinds == ["metadata", "paragraph"]

    def test_long_line_breaks_metadata(self):
        """A line >= 80 chars that isn't a metadata match should end the block."""
        long_line = "A" * 85
        text = (
            "advait@microsoft.com\n"
            f"{long_line}"
        )
        blocks = split_into_blocks(text)
        kinds = _kinds(blocks)
        assert "paragraph" in kinds

    def test_heading_breaks_metadata(self):
        text = (
            "advait@microsoft.com\n"
            "## 1 Introduction"
        )
        blocks = split_into_blocks(text)
        kinds = _kinds(blocks)
        assert "metadata" in kinds
        assert "heading" in kinds

    def test_list_breaks_metadata(self):
        text = (
            "advait@microsoft.com\n"
            "- First item\n"
            "- Second item"
        )
        blocks = split_into_blocks(text)
        kinds = _kinds(blocks)
        assert "metadata" in kinds
        assert "list" in kinds

    def test_research_word_in_prose_not_metadata(self):
        """The word 'research' in regular prose must not trigger metadata."""
        text = (
            "Moreover, we focus on critical thinking for knowledge work (as\n"
            "conceptualised by Drucker [30] and Kidd [67]). Much research on\n"
            "the effect of GenAI on thinking skills is focused on educational\n"
            "settings, where concern for skill cultivation is most acute."
        )
        blocks = split_into_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].kind == "paragraph"
        assert "Much research on" in blocks[0].content
