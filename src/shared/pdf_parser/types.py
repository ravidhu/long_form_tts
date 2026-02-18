"""Shared dataclasses for TOC analysis."""

from dataclasses import dataclass, field


@dataclass
class TOCEntry:
    level: int
    title: str
    page: int  # 0-indexed
    kind: str = ""  # "front", "back", "preamble", "content"


@dataclass
class ContentRange:
    """The resolved page range of actual book content."""

    start_page: int  # inclusive, 0-indexed
    end_page: int  # inclusive, 0-indexed
    total_pages: int
    skipped_front: list[str] = field(default_factory=list)
    skipped_back: list[str] = field(default_factory=list)


@dataclass
class TOCSection:
    """A content section defined by the TOC, with its page range."""

    title: str
    level: int
    start_page: int  # inclusive, 0-indexed
    end_page: int  # inclusive, 0-indexed
