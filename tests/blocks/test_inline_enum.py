"""Tests for inline enumeration to spoken ordinal conversion."""

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent.parent / "src")
if _SRC not in sys.path or sys.path.index(_SRC) != 0:
    sys.path.insert(0, _SRC)

from audiobook.preprocess import inline_enum_to_spoken, preprocess_paragraph  # noqa: E402


class TestNumericParenEnums:
    """Patterns: 1), 2), (1), (2)"""

    def test_n_paren_inline(self):
        text = "to investigate 1) when and how, and 2) when and why"
        result = inline_enum_to_spoken(text)
        assert "first, when and how" in result
        assert "second, when and why" in result

    def test_paren_n_paren_inline(self):
        text = "grouped into (1) for creation, (2) to find info, (3) to get advice"
        result = inline_enum_to_spoken(text)
        assert "first, for creation" in result
        assert "second, to find info" in result
        assert "third, to get advice" in result

    def test_higher_numbers(self):
        text = "items 4) alpha and 5) beta"
        result = inline_enum_to_spoken(text)
        assert "fourth, alpha" in result
        assert "fifth, beta" in result

    def test_beyond_10_left_as_is(self):
        text = "item 11) is too high"
        result = inline_enum_to_spoken(text)
        assert "11)" in result


class TestAlphaEnums:
    """Patterns: (a), (b), (c)"""

    def test_alpha_inline(self):
        text = "we consider (a) task factors, (b) user factors"
        result = inline_enum_to_spoken(text)
        assert "first, task factors" in result
        assert "second, user factors" in result

    def test_alpha_beyond_j_left_as_is(self):
        text = "option (k) is rare"
        result = inline_enum_to_spoken(text)
        assert "(k)" in result


class TestLineStartNotAffected:
    """Enumerations at line start are list items, not inline enums."""

    def test_line_start_n_paren_unchanged(self):
        text = "1) First item at line start"
        result = inline_enum_to_spoken(text)
        # No preceding whitespace → regex doesn't match
        assert "1)" in result

    def test_line_start_paren_n_paren_unchanged(self):
        text = "(1) First item at line start"
        result = inline_enum_to_spoken(text)
        assert "(1)" in result


class TestFullPipeline:
    """Verify inline enums are converted in the full preprocess_paragraph pipeline."""

    def test_chi_paper_abstract(self):
        text = (
            "We survey 319 knowledge workers to investigate 1) when and "
            "how they perceive the enaction of critical thinking when using "
            "GenAI, and 2) when and why GenAI affects their effort to do so."
        )
        result = preprocess_paragraph(text)
        assert "first," in result
        assert "second," in result
        assert "1)" not in result
        assert "2)" not in result
