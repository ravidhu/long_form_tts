"""Tests for stitch_broken_lines — rejoining PDF hard-wrapped sentences."""

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent.parent.parent / "src")
if _SRC not in sys.path or sys.path.index(_SRC) != 0:
    sys.path.insert(0, _SRC)

from audiobook.preprocess import stitch_broken_lines  # noqa: E402


# ---------------------------------------------------------------------------
# Orphaned citations (blank line between sentence and [number])
# ---------------------------------------------------------------------------


class TestOrphanedCitations:
    """A citation on its own line after a blank should be stitched back."""

    def test_single_blank_before_citation(self):
        text = (
            "introduce critical thinking prompts without an explicit user request\n"
            "\n"
            "[69, 109]. Or the extent to which user participation"
        )
        result = stitch_broken_lines(text)
        assert "\n\n" not in result
        assert "request\n[69" in result

    def test_two_blanks_before_citation(self):
        """Column breaks sometimes produce two blank lines."""
        text = (
            "Research has also explored the extent\n"
            "\n"
            "\n"
            "to which interventions ought to be presented"
        )
        result = stitch_broken_lines(text)
        assert "extent\nto which" in result

    def test_multiple_orphaned_citations_in_sequence(self):
        text = (
            "attention checks promote systematic thinking\n"
            "\n"
            "[49], conflict-filled discussion induces critical thinking [78], and\n"
            "in general increased engagement results in behavioural changes\n"
            "\n"
            "[82, 92]. Research has explored the effectiveness"
        )
        result = stitch_broken_lines(text)
        assert "thinking\n[49]" in result
        assert "changes\n[82" in result

    def test_dash_continuation_after_blank(self):
        text = (
            "solution that merely meets a baseline aspirational threshold [6, 119]\n"
            "\n"
            "- in such cases, the AI solution is correct"
        )
        result = stitch_broken_lines(text)
        assert "119]\n- in such" in result


# ---------------------------------------------------------------------------
# Structural elements must NOT be stitched
# ---------------------------------------------------------------------------


class TestStructuralPreservation:
    """Headings, lists, tables, code fences must not be joined."""

    def test_heading_after_blank_preserved(self):
        text = (
            "End of a paragraph.\n"
            "\n"
            "## Next Section"
        )
        result = stitch_broken_lines(text)
        assert "\n\n## Next Section" in result

    def test_list_items_not_stitched(self):
        text = (
            "The contributions are:\n"
            "\n"
            "- First contribution\n"
            "- Second contribution"
        )
        result = stitch_broken_lines(text)
        assert "- First contribution" in result
        assert "- Second contribution" in result

    def test_table_not_stitched(self):
        text = (
            "See the table below\n"
            "\n"
            "| Col A | Col B |"
        )
        result = stitch_broken_lines(text)
        assert "\n\n| Col A" in result

    def test_code_fence_not_stitched(self):
        text = (
            "Here is an example\n"
            "\n"
            "```python\nprint('hello')\n```"
        )
        result = stitch_broken_lines(text)
        assert "\n\n```python" in result


# ---------------------------------------------------------------------------
# Complete sentences must NOT be stitched
# ---------------------------------------------------------------------------


class TestCompleteSentences:
    """Lines ending with terminal punctuation should keep the paragraph break."""

    def test_period_ends_sentence(self):
        text = (
            "This is a complete sentence.\n"
            "\n"
            "This is a new paragraph."
        )
        result = stitch_broken_lines(text)
        assert "\n\n" in result

    def test_question_mark_ends_sentence(self):
        text = (
            "Is this a question?\n"
            "\n"
            "This answers it."
        )
        result = stitch_broken_lines(text)
        assert "\n\n" in result


# ---------------------------------------------------------------------------
# Real-world excerpt from CHI paper
# ---------------------------------------------------------------------------


class TestRealWorldExcerpt:
    """Full excerpt from the CHI paper section the user reported."""

    def test_chi_paper_section_22(self):
        text = (
            "Previous research has investigated how interaction design can\n"
            "encourage critical or reflective thinking. Various dimensions of\n"
            "the space of critical thinking interventions have been explored.\n"
            "For instance, whether the system should be proactive, i.e., introduce critical thinking prompts without an explicit user request\n"
            "\n"
            "[69, 109]. Or the extent to which user participation and engagement is important in creating critical thinking outcomes, e.g., presenting AI explanations as questions rather than statements improves logical discernment [24], questions also improve critical\n"
            "reading [110, 142], attention checks promote systematic thinking\n"
            "\n"
            "[49], conflict-filled discussion induces critical thinking [78], and\n"
            "in general increased engagement results in behavioural changes\n"
            "\n"
            "[82, 92]. Research has explored the effectiveness of gamification of\n"
            "critical thinking [31, 91, 129]. Research has also explored the extent\n"
            "\n"
            "\n"
            "\n"
            "to which interventions ought to be presented in an agentised or\n"
            "anthropomimetic manner [99, 131, 141]."
        )
        result = stitch_broken_lines(text)
        # All orphaned citations should be stitched
        assert "request\n[69, 109]" in result
        assert "thinking\n[49]" in result
        assert "changes\n[82, 92]" in result
        # Column break should be collapsed
        assert "extent\n" in result
        lines = result.split("\n")
        # No isolated blank lines should remain inside the paragraph
        blank_runs = [
            i for i, l in enumerate(lines)
            if not l.strip()
            and i > 0 and lines[i-1].strip()
            and i < len(lines)-1 and lines[i+1].strip()
        ]
        assert len(blank_runs) == 0, f"Unexpected blank lines at positions: {blank_runs}"
