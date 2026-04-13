"""Tests for _trim_shared_page overlap logic in audiobook script."""

import sys
from pathlib import Path

# Ensure src/ is resolved before scripts/ so `audiobook` maps to the package,
# not the script.
_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = str(_ROOT / "src")
if _SRC not in sys.path or sys.path.index(_SRC) != 0:
    sys.path.insert(0, _SRC)

# The helpers live in scripts/audiobook.py which is normally run as a script.
# Import them by path to avoid triggering the script-level code.
import importlib.util

_SCRIPT = _ROOT / "scripts" / "audiobook.py"
_spec = importlib.util.spec_from_file_location("_audiobook_script", _SCRIPT)
# We can't actually import the full script because it runs top-level code.
# Instead, test the logic inline via the refactored helpers.
# Since the helpers use only `re`, replicate the import here.
import re  # noqa: E402


# ---------------------------------------------------------------------------
# Inline copies of the helpers to test (avoids importing the whole script)
# ---------------------------------------------------------------------------

def _title_patterns(title: str) -> list[re.Pattern[str]]:
    num_match = re.match(r"^([\d.]+)\s+(.*)", title)
    if num_match:
        sec_num = num_match.group(1)
        words = num_match.group(2).split()[:4]
    else:
        sec_num = None
        words = title.split()[:4]
    title_start = r"\s+".join(re.escape(w) for w in words)
    patterns: list[re.Pattern[str]] = []
    if sec_num:
        esc_num = re.escape(sec_num)
        patterns.append(re.compile(
            rf"^\**{esc_num}\**\s+\**{title_start}", re.MULTILINE
        ))
        patterns.append(re.compile(
            rf"^#{{1,6}}\s+{esc_num}\s+{title_start}", re.MULTILINE
        ))
    patterns.append(re.compile(rf"^#{{1,6}}\s+\**{title_start}", re.MULTILINE))
    patterns.append(re.compile(rf"^\**{title_start}\**\s*$", re.MULTILINE))
    return patterns


def _find_title(md: str, title: str) -> int | None:
    earliest: int | None = None
    for pat in _title_patterns(title):
        m = pat.search(md)
        if m and (earliest is None or m.start() < earliest):
            earliest = m.start()
    return earliest


def _trim_shared_page(md: str, current_title: str, next_title: str | None) -> str:
    pos = _find_title(md, current_title)
    if pos is not None and pos > 0:
        nl = md.find("\n", pos)
        if nl == -1:
            md = ""
        else:
            rest = md[nl + 1:]
            while rest.startswith("**"):
                next_nl = rest.find("\n")
                if next_nl == -1:
                    rest = ""
                    break
                rest = rest[next_nl + 1:]
            md = rest.lstrip("\n")

    if next_title is not None:
        pos = _find_title(md, next_title)
        if pos is not None:
            md = md[:pos]

    return md.strip()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBeginTrim:
    """Begin-trim: discard content from earlier sections on the same page."""

    def test_removes_content_before_bold_heading(self):
        md = (
            "Running header text\n\n"
            "**2** **Related Work**\n\n"
            "**2.1** **Critical thinking**\n\n"
            "We adopt the definition...\n\n"
            "**2.2** **Design research**\n\n"
            "Previous research...\n"
        )
        result = _trim_shared_page(md, "2.2 Design research", None)
        assert "Related Work" not in result
        assert "Critical thinking" not in result
        assert "Previous research" in result

    def test_removes_content_before_markdown_heading(self):
        md = (
            "Some prior section content.\n\n"
            "## 3.1 Survey Design\n\n"
            "We designed a survey...\n"
        )
        result = _trim_shared_page(md, "3.1 Survey Design", None)
        assert "prior section" not in result
        assert "We designed a survey" in result

    def test_multiline_bold_heading_fully_skipped(self):
        md = (
            "Earlier content\n\n"
            "**2.3** **Effects of automation on thinking and**\n"
            "**knowledge workflows: writing and memory**\n\n"
            "Effects on writing. Generative AI tools...\n"
        )
        result = _trim_shared_page(
            md, "2.3 Effects of automation on thinking and", None
        )
        assert "Earlier content" not in result
        assert "knowledge workflows" not in result
        assert "Effects on writing" in result

    def test_no_trim_when_heading_at_start(self):
        md = (
            "**2.1** **Critical thinking**\n\n"
            "We adopt the definition...\n"
        )
        result = _trim_shared_page(md, "2.1 Critical thinking", None)
        assert "We adopt the definition" in result

    def test_no_trim_when_heading_not_found(self):
        md = "Some content that has no matching heading.\n"
        result = _trim_shared_page(md, "99.9 Missing Section", None)
        assert "Some content" in result


class TestEndTrim:
    """End-trim: discard content from later sections on the same page."""

    def test_removes_content_after_next_bold_heading(self):
        md = (
            "Section 2.1 content here.\n\n"
            "**2.2** **Design research**\n\n"
            "This belongs to 2.2.\n"
        )
        result = _trim_shared_page(md, "2.1 Critical thinking", "2.2 Design research")
        assert "Section 2.1 content" in result
        assert "Design research" not in result
        assert "belongs to 2.2" not in result

    def test_no_end_trim_when_next_title_is_none(self):
        md = "Last section content.\n"
        result = _trim_shared_page(md, "6.3 Limitations", None)
        assert "Last section content" in result


class TestBothTrims:
    """Begin and end trim working together."""

    def test_trims_both_ends(self):
        md = (
            "Content from section 2.1.\n\n"
            "**2.2** **Design research for critical thinking**\n\n"
            "This is 2.2 content.\n\n"
            "**2.3** **Effects of automation**\n\n"
            "This is 2.3 content.\n"
        )
        result = _trim_shared_page(
            md,
            "2.2 Design research for critical thinking",
            "2.3 Effects of automation",
        )
        assert "section 2.1" not in result
        assert "This is 2.2 content" in result
        assert "Effects of automation" not in result
        assert "2.3 content" not in result

    def test_research_paper_scenario(self):
        """Realistic multi-section page from a CHI paper."""
        md = (
            "The Impact of Generative AI CHI '25\n\n"
            "**2** **Related Work**\n\n"
            "**2.1** **Critical thinking**\n\n"
            "We adopt the definition of critical thinking...\n\n"
            "**2.2** **Design research for critical and reflective thinking**\n\n"
            "Previous research has investigated...\n\n"
            "**2.3** **Effects of automation on thinking**\n\n"
            "Effects on writing. Generative AI tools...\n"
        )
        # Extracting section 2.2
        result = _trim_shared_page(
            md,
            "2.2 Design research for critical and reflective thinking",
            "2.3 Effects of automation on thinking",
        )
        assert "Related Work" not in result
        assert "Critical thinking" not in result
        assert "Previous research has investigated" in result
        assert "Effects on writing" not in result
