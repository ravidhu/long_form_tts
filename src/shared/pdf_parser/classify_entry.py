"""Classify TOC entries as front matter, back matter, preamble, or content."""

import re

from .types import TOCEntry

# Patterns that identify non-content pages (case-insensitive)
FRONT_MATTER_PATTERNS = [
    r"^cover$",
    r"^half\s*title",
    r"^title\s*page",
    r"^copyright",
    r"^table\s*of\s*contents$",
    r"^contents$",
    r"^list\s*of\s*(figures|tables|illustrations)",
    r"^dedication",
    r"^epigraph",
    r"^praise\b",
    r"^endorsements?$",
    r"^also\s*by\b",
    r"^about\s*the\s*cover",
]

BACK_MATTER_PATTERNS = [
    r"^index$",
    r"^glossary$",
    r"^bibliography$",
    r"^references$",
    r"^about\s*the\s*authors?$",
    r"^colophon$",
    r"^appendix",
]

# These are content even though they appear before chapter 1
PREAMBLE_PATTERNS = [
    r"^foreword",
    r"^preface",
    r"^introduction$",
    r"^acknowledgments?$",
]


def _compiled_patterns(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_FRONT = _compiled_patterns(FRONT_MATTER_PATTERNS)
_BACK = _compiled_patterns(BACK_MATTER_PATTERNS)
_PREAMBLE = _compiled_patterns(PREAMBLE_PATTERNS)


def classify_entry(entry: TOCEntry) -> str:
    title = entry.title.strip()
    for pat in _FRONT:
        if pat.search(title):
            return "front"
    for pat in _BACK:
        if pat.search(title):
            return "back"
    for pat in _PREAMBLE:
        if pat.search(title):
            return "preamble"
    return "content"
