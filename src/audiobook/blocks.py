"""Split markdown content into typed blocks for hybrid narration."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Heuristic patterns for metadata/boilerplate lines
_METADATA_RE = re.compile(
    r"(?i)"
    r"(?:copyright|"
    r"\u00a9|"                          # ©
    r"\bDOI\b|"
    r"10\.\d{4,}/|"                     # DOI prefix
    r"ACM Reference|"
    r"CCS Concepts|"
    r"\bISBN\b|"
    r"\bISSN\b|"
    r"Permission to make|"
    r"^\*\*Keywords\*\*|"
    r"^Keywords:|"
    r"Creative Commons|"
    r"This work is licensed|"
    r"^\[https?://|"                    # bare link lines
    r"^https?://\S+$"                   # bare URL lines
    r")"
)

_AUTHOR_LINE_RE = re.compile(
    r"(?:"
    r"[A-Za-z.]+@[A-Za-z.]+\.\w{2,}|"  # email
    r"\bUniversity\b|"
    r"\bInstitute\b|"
    r"\bResearch\b.{0,20}$|"           # "Microsoft Research" at end of line
    r"\bORCID\b|"
    r"orcid\.org"
    r")",
    re.IGNORECASE,
)

_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)]) ")


@dataclass
class Block:
    """A typed chunk of markdown content."""

    kind: str       # paragraph | table | code | list | heading | metadata
    content: str    # raw markdown text of this block
    level: int = 0  # heading level (1-6) for heading blocks, 0 otherwise


def split_into_blocks(content: str) -> list[Block]:
    """Split markdown content into a list of typed blocks.

    Walks the content line-by-line using a simple state machine to
    group consecutive lines into paragraph, heading, table, code,
    list, or metadata blocks.
    """
    blocks: list[Block] = []
    lines = content.split("\n")
    buf: list[str] = []
    state = "idle"          # idle | code | table | list | metadata

    def _flush(kind: str, level: int = 0) -> None:
        nonlocal buf
        text = "\n".join(buf).strip()
        if text:
            blocks.append(Block(kind=kind, content=text, level=level))
        buf = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # ── Code fences (highest priority) ──────────────────────
        if state == "code":
            buf.append(line)
            if line.strip().startswith("```"):
                _flush("code")
                state = "idle"
            i += 1
            continue

        if line.strip().startswith("```"):
            # Flush anything accumulated so far
            if buf:
                _flush(_current_kind(state))
            state = "code"
            buf = [line]
            i += 1
            continue

        # ── Blank line → flush current block ────────────────────
        if not line.strip():
            if buf and state != "idle":
                _flush(_current_kind(state))
                state = "idle"
            elif buf:
                _flush("paragraph")
            i += 1
            continue

        # ── Heading ─────────────────────────────────────────────
        heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading_match and state == "idle":
            if buf:
                _flush("paragraph")
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            blocks.append(Block(kind="heading", content=heading_text, level=level))
            i += 1
            continue

        # ── Table (lines starting with |) ───────────────────────
        if line.strip().startswith("|"):
            if state != "table" and buf:
                _flush(_current_kind(state))
            state = "table"
            buf.append(line)
            i += 1
            continue
        if state == "table":
            # Non-pipe line ends the table
            _flush("table")
            state = "idle"
            continue  # re-process this line

        # ── List items ──────────────────────────────────────────
        if _LIST_ITEM_RE.match(line):
            if state != "list" and buf:
                _flush(_current_kind(state))
            state = "list"
            buf.append(line)
            i += 1
            continue
        # Continuation lines for lists — PDF-extracted markdown often
        # wraps list item text without indentation, so any non-blank
        # non-structural line continues the current list item.
        if state == "list":
            is_heading = bool(re.match(r"^#{1,6}\s+", line))
            is_table = line.strip().startswith("|")
            is_code = line.strip().startswith("```")
            if not is_heading and not is_table and not is_code:
                buf.append(line)
                i += 1
                continue
            _flush("list")
            state = "idle"
            continue  # re-process this line

        # ── Metadata heuristic ──────────────────────────────────
        if _is_metadata_line(line):
            if state != "metadata" and buf:
                _flush(_current_kind(state))
            state = "metadata"
            buf.append(line)
            i += 1
            continue
        if state == "metadata":
            # Check if this looks like a continuation (short line after metadata)
            if len(line.strip()) < 80 and _is_metadata_line(line):
                buf.append(line)
                i += 1
                continue
            _flush("metadata")
            state = "idle"
            continue  # re-process this line

        # ── Default: paragraph ──────────────────────────────────
        if state not in ("idle", "metadata"):
            _flush(_current_kind(state))
            state = "idle"
        buf.append(line)
        i += 1

    # Flush remaining buffer
    if buf:
        _flush(_current_kind(state) if state != "idle" else "paragraph")

    return blocks


def _current_kind(state: str) -> str:
    """Map state machine state to block kind."""
    if state in ("code", "table", "list", "metadata"):
        return state
    return "paragraph"


def _is_metadata_line(line: str) -> bool:
    """Check if a line looks like document metadata/boilerplate."""
    stripped = line.strip()
    if not stripped:
        return False
    if _METADATA_RE.search(stripped):
        return True
    return bool(_AUTHOR_LINE_RE.search(stripped))
