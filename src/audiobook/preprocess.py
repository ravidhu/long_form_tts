"""Deterministic text transformations for narration-ready prose.

These functions handle the 80%+ of content that is already well-written
prose and only needs markdown stripped, numbers spoken, and abbreviations
expanded — no LLM required.
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Rejoin PDF hard-wrapped sentences
# ---------------------------------------------------------------------------

# A line that does NOT end with sentence-terminating punctuation.
# Allows trailing markdown (bold/italic closers), whitespace, and
# optional citation like [42] at the very end.
_INCOMPLETE_LINE_RE = re.compile(
    r".*[a-zA-Z,;:()\[\]\u2014\u2013\-]"  # ends with letter, comma, paren, bracket, dash
    r"(?:\*{1,2}|_{1,2})?"                 # optional markdown closer
    r"\s*$"
)

# A line that is clearly a continuation: starts with a citation bracket,
# lowercase word, dash (list continuation), or closing paren/bracket.
_CONTINUATION_RE = re.compile(
    r"^\s*(?:"
    r"\[\d|"                # citation: [49, ...
    r"[a-z]|"              # lowercase continuation
    r"- [a-z]|"            # dash continuation: "- in such cases"
    r"[)\]]"               # closing bracket/paren
    r")"
)


def stitch_broken_lines(text: str) -> str:
    """Rejoin lines that PDF column extraction broke mid-sentence.

    PDF extractors (pymupdf4llm, Docling) faithfully reproduce the
    column width, inserting hard line breaks and sometimes blank lines
    where the original two-column layout wrapped.  When a citation
    like ``[49]`` lands on the next line — possibly after a blank line —
    the block splitter sees separate paragraphs and the narration
    loses sentence coherence.

    This function collapses spurious blank lines between an incomplete
    sentence and its continuation, then joins adjacent lines that form
    a single sentence.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip structural lines (headings, tables, code fences, list items)
        stripped = line.strip()
        if (
            stripped.startswith("#")
            or stripped.startswith("|")
            or stripped.startswith("```")
            or re.match(r"^\s*[-*+]\s", line)
            or re.match(r"^\s*\d+[.)]\s", line)
        ):
            out.append(line)
            i += 1
            continue

        # Look ahead: if this line is incomplete, check for blank lines
        # followed by a continuation line and collapse them.
        if stripped and _INCOMPLETE_LINE_RE.match(stripped):
            # Count consecutive blank lines ahead
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1

            # If there were 1-2 blank lines and the next line continues
            # the sentence, stitch them together.
            blanks = j - (i + 1)
            if (
                0 < blanks <= 2
                and j < len(lines)
                and _CONTINUATION_RE.match(lines[j].strip())
            ):
                # Join: current line + " " + continuation (skip blanks)
                out.append(line.rstrip())
                i = j  # jump to the continuation line (will be processed next iteration)
                continue

        out.append(line)
        i += 1

    # Second pass: join adjacent non-blank lines where the first is
    # incomplete and the second is a continuation.  This handles the
    # case where there's no blank line between them (simple hard wrap).
    merged: list[str] = []
    for line in out:
        if (
            merged
            and merged[-1].strip()
            and not merged[-1].strip().startswith("#")
            and not merged[-1].strip().startswith("|")
            and not merged[-1].strip().startswith("```")
            and _INCOMPLETE_LINE_RE.match(merged[-1].strip())
            and line.strip()
            and _CONTINUATION_RE.match(line.strip())
        ):
            merged[-1] = merged[-1].rstrip() + "\n" + line
        else:
            merged.append(line)

    return "\n".join(merged)

# ---------------------------------------------------------------------------
# Markdown stripping
# ---------------------------------------------------------------------------

# Order matters: process links before bold/italic to avoid partial matches
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")       # [text](url) → text
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")      # ![alt](url) → remove
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")      # **bold** or __bold__
_ITALIC_RE = re.compile(r"(?<!\w)\*(.+?)\*(?!\w)|(?<!\w)_(.+?)_(?!\w)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")              # `code` → code
_STRIKETHROUGH_RE = re.compile(r"~~(.+?)~~")
_FOOTNOTE_REF_RE = re.compile(r"\[\^[^\]]+\]")          # [^1]
_HR_RE = re.compile(r"^[\s]*[-*_]{3,}\s*$", re.MULTILINE)


def strip_markdown(text: str) -> str:
    """Remove markdown formatting, keeping inner text."""
    text = _IMAGE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _BOLD_RE.sub(lambda m: m.group(1) or m.group(2), text)
    text = _ITALIC_RE.sub(lambda m: m.group(1) or m.group(2), text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _STRIKETHROUGH_RE.sub(r"\1", text)
    text = _FOOTNOTE_REF_RE.sub("", text)
    text = _HR_RE.sub("", text)
    # Clean up leftover whitespace
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Number-to-spoken conversion
# ---------------------------------------------------------------------------

_ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = [
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
    "eighty", "ninety",
]


def _int_to_words(n: int) -> str:
    """Convert a non-negative integer to English words (up to 999,999,999)."""
    if n == 0:
        return "zero"
    if n < 0:
        return f"negative {_int_to_words(-n)}"

    parts = []
    if n >= 1_000_000:
        millions = n // 1_000_000
        parts.append(f"{_int_to_words(millions)} million")
        n %= 1_000_000
    if n >= 1_000:
        thousands = n // 1_000
        parts.append(f"{_int_to_words(thousands)} thousand")
        n %= 1_000
    if n >= 100:
        hundreds = n // 100
        parts.append(f"{_ONES[hundreds]} hundred")
        n %= 100
    if n >= 20:
        parts.append(_TENS[n // 10])
        if n % 10:
            parts.append(_ONES[n % 10])
    elif n > 0:
        parts.append(_ONES[n])

    return " ".join(parts)


def _is_year(s: str) -> bool:
    """Check if a string looks like a year (1800-2099)."""
    try:
        n = int(s)
        return 1800 <= n <= 2099
    except ValueError:
        return False


# Percentage: 87.61% or 45%
_PCT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")

# Suffix multipliers: 32K, 1.5M, 2.3B, 4T
_SUFFIX_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*([KkMmBbTt])\b")
_SUFFIX_MAP = {"k": "thousand", "m": "million", "b": "billion", "t": "trillion"}

# Comma-separated integers: 1,234 or 1,234,567
_COMMA_INT_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})+)\b")

# Decimal numbers (not part of a larger pattern): 3.14
_DECIMAL_RE = re.compile(r"\b(\d+)\.(\d+)\b")

# Plain integers (1-6 digits, not years)
_PLAIN_INT_RE = re.compile(r"\b(\d{1,6})\b")


def number_to_spoken(text: str) -> str:
    """Convert numeric expressions to spoken English form."""

    # Percentages first
    def _pct_repl(m: re.Match) -> str:
        val = float(m.group(1))
        rounded = round(val)
        prefix = "roughly " if abs(val - rounded) > 0.4 else ""
        return f"{prefix}{_int_to_words(rounded)} percent"

    text = _PCT_RE.sub(_pct_repl, text)

    # Suffix multipliers (32K → thirty-two thousand)
    def _suffix_repl(m: re.Match) -> str:
        num = float(m.group(1))
        suffix = m.group(2).lower()
        word = _SUFFIX_MAP.get(suffix, suffix)
        if num == int(num):
            return f"{_int_to_words(int(num))} {word}"
        # e.g. 1.5M → one point five million
        int_part = int(num)
        frac = str(num).split(".")[1]
        frac_words = " ".join(_ONES[int(d)] for d in frac if d != "0") or "zero"
        return f"{_int_to_words(int_part)} point {frac_words} {word}"

    text = _SUFFIX_RE.sub(_suffix_repl, text)

    # Comma-separated integers (1,234,567 → about one point two million)
    def _comma_repl(m: re.Match) -> str:
        n = int(m.group(1).replace(",", ""))
        return _int_to_words(n)

    text = _COMMA_INT_RE.sub(_comma_repl, text)

    # Decimals (3.14 → three point one four) — skip if looks like a version
    def _decimal_repl(m: re.Match) -> str:
        whole = m.group(1)
        frac = m.group(2)
        # Skip version-like patterns (e.g. 3.11.2) — let them pass through
        if _is_year(whole):
            return m.group(0)
        int_part = _int_to_words(int(whole))
        frac_words = " ".join(_ONES[int(d)] for d in frac)
        return f"{int_part} point {frac_words}"

    text = _DECIMAL_RE.sub(_decimal_repl, text)

    # Plain integers (skip years)
    def _plain_repl(m: re.Match) -> str:
        s = m.group(1)
        if _is_year(s):
            return s  # TTS handles years well
        n = int(s)
        if n > 999_999_999:
            return s  # too large, leave as-is
        return _int_to_words(n)

    text = _PLAIN_INT_RE.sub(_plain_repl, text)

    return text


# ---------------------------------------------------------------------------
# Abbreviation expansion
# ---------------------------------------------------------------------------

# Common technical abbreviations — extend as needed
ABBREVIATIONS: dict[str, str] = {
    "tok/s": "tokens per second",
    "RAG": "retrieval augmented generation",
    "LLM": "large language model",
    "LLMs": "large language models",
    "GPU": "graphics processing unit",
    "GPUs": "graphics processing units",
    "CPU": "central processing unit",
    "CPUs": "central processing units",
    "API": "application programming interface",
    "APIs": "application programming interfaces",
    "SQL": "structured query language",
    "URL": "uniform resource locator",
    "URLs": "uniform resource locators",
    "GenAI": "generative AI",
    "AI": "A I",  # spell out for TTS clarity
    "e.g.": "for example",
    "i.e.": "that is",
    "et al.": "and others",
    "etc.": "and so on",
    "vs.": "versus",
    "Fig.": "Figure",
    "fig.": "figure",
}

# Build a single pattern from the dictionary (longest match first)
_ABBREV_PATTERN = re.compile(
    "|".join(
        re.escape(k)
        for k in sorted(ABBREVIATIONS, key=len, reverse=True)
    )
)


def expand_abbreviations(text: str) -> str:
    """Expand known abbreviations to their spoken forms."""
    return _ABBREV_PATTERN.sub(lambda m: ABBREVIATIONS[m.group(0)], text)


# ---------------------------------------------------------------------------
# Heading → transition phrase
# ---------------------------------------------------------------------------


def heading_to_transition(title: str, level: int) -> str:
    """Convert a section heading into a spoken transition phrase."""
    clean = strip_markdown(title)
    if level == 1:
        return f"[PAUSE_LONG]\nLet's begin our discussion of {clean}."
    if level == 2:
        return f"[PAUSE_MEDIUM]\nLet's now turn our attention to {clean}."
    return f"[PAUSE_MEDIUM]\nMoving on to {clean}."


# ---------------------------------------------------------------------------
# Inline enumeration → spoken ordinals
# ---------------------------------------------------------------------------

_ORDINALS = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
}

# Matches inline enumerations: "1)", "2)", "(1)", "(2)", "(a)", "(b)"
# Must NOT be at the start of a line (those are list items handled by blocks.py).
_INLINE_NUM_ENUM_RE = re.compile(
    r"(?<=\s)"             # preceded by whitespace (inline, not line-start)
    r"(?:"
    r"\((\d{1,2})\)"       # (1), (2) — group 1
    r"|(\d{1,2})\)"        # 1), 2)   — group 2
    r")"
)

_INLINE_ALPHA_ENUM_RE = re.compile(
    r"(?<=\s)"
    r"\(([a-z])\)"         # (a), (b) — group 1
)

_ALPHA_ORDINALS = {
    "a": "first", "b": "second", "c": "third", "d": "fourth", "e": "fifth",
    "f": "sixth", "g": "seventh", "h": "eighth", "i": "ninth", "j": "tenth",
}


def inline_enum_to_spoken(text: str) -> str:
    """Convert inline enumerations to spoken ordinals.

    ``1)`` / ``(1)`` → "first,", ``2)`` / ``(2)`` → "second," etc.
    ``(a)`` → "first,", ``(b)`` → "second," etc.
    """
    def _num_repl(m: re.Match) -> str:
        n = int(m.group(1) or m.group(2))
        word = _ORDINALS.get(n)
        if word is None:
            return m.group(0)  # 11+, leave as-is
        return f"{word},"

    def _alpha_repl(m: re.Match) -> str:
        word = _ALPHA_ORDINALS.get(m.group(1))
        if word is None:
            return m.group(0)
        return f"{word},"

    text = _INLINE_NUM_ENUM_RE.sub(_num_repl, text)
    text = _INLINE_ALPHA_ENUM_RE.sub(_alpha_repl, text)
    return text


# ---------------------------------------------------------------------------
# Top-level preprocessing pipeline
# ---------------------------------------------------------------------------


def preprocess_paragraph(text: str) -> str:
    """Full deterministic pipeline for a paragraph block."""
    text = strip_markdown(text)
    text = expand_abbreviations(text)
    text = inline_enum_to_spoken(text)
    text = number_to_spoken(text)
    return text
