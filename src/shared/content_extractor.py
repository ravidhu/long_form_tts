"""Stages 1-2: Extract content from PDF/URL with section-file caching.

Handles three modes:
1. Resume  -- reload (title, content) pairs from existing .md files
2. URL     -- fetch + split by headings + write section files
3. PDF     -- TOC analysis + per-section markdown extraction + write section files

Each section is persisted as ``sections_dir/NN_title.md`` with format::

    # Title

    content

Subsequent runs skip already-cached sections.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .extract import InputSource
from .pdf_parser import (
    pdf_to_markdown,
    resolve_content_pages,
    resolve_content_sections,
)
from .web_parser import fetch_url_content, split_by_headings


@dataclass
class ExtractedSection:
    """A content section extracted from the source material."""

    title: str
    content: str  # raw markdown


@dataclass
class ExtractionResult:
    """Return value of :func:`extract_content`."""

    sections: list[ExtractedSection]
    source_kind: str | None = None  # "pdf", "url", or None (resume)


def _fmt_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS or sub-second."""
    if seconds < 1:
        return f"{seconds:.2f}s"
    h, remainder = divmod(int(seconds), 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _safe_filename(title: str) -> str:
    return title.replace("/", "-").replace(" ", "_")[:50]


def _read_cached_section(section_path: str, expected_title: str) -> str:
    """Read a cached section file and return just the content text."""
    raw = Path(section_path).read_text()
    prefix = f"# {expected_title}\n\n"
    if raw.startswith(prefix):
        return raw[len(prefix):]
    if raw.startswith("# "):
        first_nl = raw.index("\n")
        return raw[first_nl:].strip()
    return raw.strip()


def _write_section_file(section_path: str, title: str, content: str) -> None:
    """Write a section file in the standard ``# Title\\n\\ncontent`` format."""
    with open(section_path, "w") as f:
        f.write(f"# {title}\n\n{content}")


# ---------------------------------------------------------------------------
# Resume mode
# ---------------------------------------------------------------------------


def _resume_sections(sections_dir: str) -> list[ExtractedSection]:
    """Reload sections from cached .md files (resume mode)."""
    print("\nResuming from cached sections")
    print("=" * 60)

    sections: list[ExtractedSection] = []
    for section_path in sorted(Path(sections_dir).glob("*.md")):
        raw = section_path.read_text()
        if raw.startswith("# "):
            first_nl = raw.index("\n")
            title = raw[2:first_nl]
            content_text = raw[first_nl:].strip()
        else:
            title = section_path.stem
            content_text = raw.strip()
        sections.append(ExtractedSection(title=title, content=content_text))
        print(f"  {len(sections)}. {title} (cached)")

    if not sections:
        print("ERROR: No section files found in", sections_dir)
        raise SystemExit(1)

    print(f"\n{len(sections)} sections loaded from {sections_dir}/")
    return sections


# ---------------------------------------------------------------------------
# URL mode
# ---------------------------------------------------------------------------


def _extract_from_url(
    url: str,
    sections_dir: str,
    max_toc_level: int,
) -> list[ExtractedSection]:
    """Fetch a webpage and split into sections with caching."""
    print("\nStage 1: Fetching webpage content")
    print("=" * 60)

    step_t0 = time.time()
    markdown = fetch_url_content(url)
    print(f"Extracted {len(markdown):,} chars of markdown from {url}")

    web_sections = split_by_headings(markdown, max_level=max_toc_level)
    print(f"\nContent sections ({len(web_sections)}):\n")
    for i, ws in enumerate(web_sections):
        print(f"  {i+1}. {ws.title} ({len(ws.content):,} chars)")

    print()
    print("=" * 60)
    print("Stage 2: Writing section files")
    print("=" * 60)

    sections: list[ExtractedSection] = []
    for i, ws in enumerate(web_sections):
        safe_title = _safe_filename(ws.title)
        section_path = os.path.join(sections_dir, f"{i:02d}_{safe_title}.md")

        if os.path.exists(section_path):
            content_text = _read_cached_section(section_path, ws.title)
            sections.append(ExtractedSection(title=ws.title, content=content_text))
            print(f"  {i+1}. {ws.title} (cached)")
        else:
            content_text = ws.content.strip()
            sections.append(ExtractedSection(title=ws.title, content=content_text))
            _write_section_file(section_path, ws.title, content_text)
            chars = len(content_text)
            tokens_est = chars // 4
            print(
                f"  {i+1}. {ws.title}"
                f" ({chars:,} chars, ~{tokens_est:,} tokens) → {section_path}"
            )

    step_elapsed = time.time() - step_t0
    print(
        f"\n{len(sections)} sections saved to"
        f" {sections_dir}/ ({_fmt_time(step_elapsed)} total)"
    )
    return sections


# ---------------------------------------------------------------------------
# PDF mode
# ---------------------------------------------------------------------------


def _extract_from_pdf(
    pdf_file: str,
    sections_dir: str,
    max_toc_level: int,
    context_budget: int,
    pdf_parser: str,
    trim_overlap: Callable[[str, str, str | None], str] | None,
) -> list[ExtractedSection]:
    """Extract sections from a PDF with TOC analysis and caching."""
    print("Stage 1: TOC analysis & section resolution")
    print("=" * 60)

    content = resolve_content_pages(pdf_file)
    print(f"PDF: {content.total_pages} total pages")

    if content.skipped_front:
        print("\nSkipped (front matter):")
        for s in content.skipped_front:
            print(f"  {s}")
    if content.skipped_back:
        print("\nSkipped (back matter):")
        for s in content.skipped_back:
            print(f"  {s}")

    toc_sections = resolve_content_sections(
        pdf_file, max_level=max_toc_level, max_tokens=context_budget
    )

    print(f"\nContent sections ({len(toc_sections)}):\n")
    for i, s in enumerate(toc_sections):
        pages = s.end_page - s.start_page + 1
        indent = "  " * (s.level - 1)
        print(f"  {i+1}. {indent}{s.title} (p.{s.start_page}-{s.end_page}, {pages} pages)")

    # --- Stage 2: Markdown extraction per section ---

    print()
    print("=" * 60)
    print("Stage 2: Markdown extraction per section")
    print("=" * 60)

    step_t0 = time.time()
    sections: list[ExtractedSection] = []

    for i, toc_sec in enumerate(toc_sections):
        safe_title = _safe_filename(toc_sec.title)
        section_path = os.path.join(sections_dir, f"{i:02d}_{safe_title}.md")

        if os.path.exists(section_path):
            content_text = _read_cached_section(section_path, toc_sec.title)
            sections.append(ExtractedSection(title=toc_sec.title, content=content_text))
            chars = len(content_text)
            tokens_est = chars // 4
            budget_pct = tokens_est / context_budget * 100
            print(f"  {i+1}. {toc_sec.title} (cached)")
            print(
                f"     {chars:,} chars, ~{tokens_est:,} tokens"
                f" ({budget_pct:.0f}% of budget) → {section_path}"
            )
        else:
            t0 = time.time()
            pages = list(range(toc_sec.start_page, toc_sec.end_page + 1))
            md = pdf_to_markdown(pdf_file, backend=pdf_parser, pages=pages)

            # Apply overlap trimming if a callback was provided
            if trim_overlap is not None:
                next_title = None
                if i + 1 < len(toc_sections):
                    nxt = toc_sections[i + 1]
                    if nxt.start_page <= toc_sec.end_page:
                        next_title = nxt.title
                content_text = trim_overlap(md, toc_sec.title, next_title).strip()
            else:
                content_text = md.strip()

            chars = len(content_text)
            tokens_est = chars // 4

            sections.append(ExtractedSection(title=toc_sec.title, content=content_text))
            _write_section_file(section_path, toc_sec.title, content_text)

            elapsed = time.time() - t0
            budget_pct = tokens_est / context_budget * 100
            print(f"  {i+1}. {toc_sec.title}")
            print(
                f"     {chars:,} chars, ~{tokens_est:,} tokens"
                f" ({budget_pct:.0f}% of budget),"
                f" {_fmt_time(elapsed)} → {section_path}"
            )

    step_elapsed = time.time() - step_t0
    print(
        f"\n{len(sections)} sections saved to"
        f" {sections_dir}/ ({_fmt_time(step_elapsed)} total)"
    )
    return sections


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_content(
    input_source: InputSource | None,
    sections_dir: str,
    *,
    max_toc_level: int = 2,
    context_budget: int = 20_000,
    pdf_parser: str = "pymupdf",
    trim_overlap: Callable[[str, str, str | None], str] | None = None,
) -> ExtractionResult:
    """Unified content extraction with file-level caching.

    Parameters
    ----------
    input_source
        ``None`` for resume mode, otherwise an :class:`InputSource` with
        ``kind`` of ``"pdf"`` or ``"url"``.
    sections_dir
        Directory for cached ``.md`` section files.
    max_toc_level
        Max TOC depth for splitting (PDF and URL).
    context_budget
        Max tokens per section (PDF only, for TOC splitting).
    pdf_parser
        Backend for ``pdf_to_markdown`` (``"pymupdf"`` or ``"docling"``).
    trim_overlap
        Optional ``(md, current_title, next_title) -> trimmed_md`` callback
        for trimming shared-page overlap in PDF extraction.  Audiobook uses
        this; podcast does not.
    """
    if input_source is None:
        sections = _resume_sections(sections_dir)
        return ExtractionResult(sections=sections, source_kind=None)

    if input_source.kind == "url":
        sections = _extract_from_url(
            input_source.path, sections_dir, max_toc_level,
        )
        return ExtractionResult(sections=sections, source_kind="url")

    # PDF path (local file or downloaded PDF URL)
    sections = _extract_from_pdf(
        input_source.path, sections_dir,
        max_toc_level=max_toc_level,
        context_budget=context_budget,
        pdf_parser=pdf_parser,
        trim_overlap=trim_overlap,
    )
    return ExtractionResult(sections=sections, source_kind="pdf")
