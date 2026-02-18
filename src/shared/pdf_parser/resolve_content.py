"""Resolve content page ranges and split PDFs into sections using the TOC."""

import pymupdf

from .classify_entry import classify_entry
from .extract_toc import extract_toc
from .infer_toc import infer_toc
from .types import ContentRange, TOCEntry, TOCSection


def _get_toc(pdf_path: str, min_coverage: float = 0.3) -> list[TOCEntry]:
    """Get TOC entries: embedded bookmarks first, inferred headings as fallback.

    Falls back to inference when the embedded TOC is missing or only
    covers the first ``min_coverage`` fraction of the document
    (e.g. preface-only bookmarks).

    Args:
        pdf_path: Path to the PDF file.
        min_coverage: Minimum fraction (0.0–1.0) of pages the embedded TOC
                      must span to be trusted. Default 0.3 (30%).
    """
    entries = extract_toc(pdf_path)
    if entries:
        doc = pymupdf.open(pdf_path)
        total_pages = len(doc)
        doc.close()
        max_page = max(e.page for e in entries)
        if max_page >= total_pages * min_coverage:
            return entries
        # Embedded TOC too sparse — fall through to inference
    return infer_toc(pdf_path)


def resolve_content_pages(
    pdf_path: str,
    min_coverage: float = 0.3,
) -> ContentRange:
    """Analyze the PDF TOC to find the page range of actual content.

    Skips front matter (cover, copyright, TOC pages, ads) and
    back matter (index, glossary, about the author, colophon).
    Includes preamble (foreword, preface) as content.

    Falls back to all pages if no TOC is found.

    Args:
        pdf_path: Path to the PDF file.
        min_coverage: Minimum fraction (0.0–1.0) of pages the embedded TOC
                      must span to be trusted. Passed through to ``_get_toc``.
    """
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    entries = _get_toc(pdf_path, min_coverage=min_coverage)

    if not entries:
        # No embedded or inferred TOC — return all pages
        return ContentRange(
            start_page=0,
            end_page=total_pages - 1,
            total_pages=total_pages,
        )

    # Classify top-level entries only for boundary detection
    for entry in entries:
        entry.kind = classify_entry(entry)

    # Find content start: first entry that is "preamble" or "content"
    # among top-level (L1) entries
    top_level = [e for e in entries if e.level == 1]

    start_page = 0
    skipped_front = []
    for entry in top_level:
        if entry.kind in ("preamble", "content"):
            start_page = entry.page
            break
        skipped_front.append(f"p.{entry.page}: {entry.title} [{entry.kind}]")

    # Find content end: last entry before back matter starts
    end_page = total_pages - 1
    skipped_back = []
    for entry in reversed(top_level):
        if entry.kind == "back":
            end_page = entry.page - 1
            skipped_back.append(f"p.{entry.page}: {entry.title} [{entry.kind}]")
        else:
            break

    skipped_back.reverse()

    return ContentRange(
        start_page=start_page,
        end_page=end_page,
        total_pages=total_pages,
        skipped_front=skipped_front,
        skipped_back=skipped_back,
    )


def _estimate_tokens(doc: pymupdf.Document, start_page: int, end_page: int) -> int:
    """Estimate token count for a page range using raw text extraction.

    Uses ~4 chars per token as a rough approximation for English text.
    PyMuPDF text extraction is very fast (milliseconds per page).
    """
    chars = 0
    for page_num in range(start_page, end_page + 1):
        chars += len(doc[page_num].get_text())
    return chars // 4


def resolve_content_sections(
    pdf_path: str,
    max_level: int = 1,
    max_tokens: int | None = 24000,
    min_coverage: float = 0.3,
) -> list[TOCSection]:
    """Use the TOC to split the PDF into content sections with page ranges.

    Each section is a top-level TOC entry (or up to max_level depth) with
    its start and end pages resolved from the next entry's position.
    Front matter and back matter entries are excluded.

    Sections whose estimated token count exceeds max_tokens are
    automatically subdivided using deeper TOC levels (up to the deepest
    level available). Token count is estimated from raw text extraction
    at ~4 chars/token.

    Args:
        pdf_path: Path to the PDF file.
        max_level: Maximum TOC depth to use for splitting (default 1 = Parts/Chapters).
                   Use 2 to split at sub-chapter level, etc.
        max_tokens: Maximum estimated tokens per section. Sections exceeding
                    this are subdivided using deeper TOC levels. Should be set
                    to the LLM context length minus overhead for system prompt
                    and response. Set to None to disable.
        min_coverage: Minimum fraction (0.0–1.0) of pages the embedded TOC
                      must span to be trusted. Default 0.3 (30%).

    Returns:
        List of TOCSection with title, level, start_page, end_page.
    """
    content_range = resolve_content_pages(pdf_path, min_coverage=min_coverage)
    all_entries = _get_toc(pdf_path, min_coverage=min_coverage)

    if not all_entries:
        # No embedded or inferred TOC — single section for entire document
        return [TOCSection(
            title="Full Document",
            level=1,
            start_page=content_range.start_page,
            end_page=content_range.end_page,
        )]

    # Classify all entries
    for entry in all_entries:
        entry.kind = classify_entry(entry)

    deepest_level = max(e.level for e in all_entries)

    # Start with entries at max_level
    content_entries = [
        e for e in all_entries
        if e.level <= max_level
        and e.kind in ("preamble", "content")
        and content_range.start_page <= e.page <= content_range.end_page
    ]

    if not content_entries:
        return [TOCSection(
            title="Full Document",
            level=1,
            start_page=content_range.start_page,
            end_page=content_range.end_page,
        )]

    # Build initial sections
    sections = []
    for i, entry in enumerate(content_entries):
        if i + 1 < len(content_entries):
            end_page = max(entry.page, content_entries[i + 1].page - 1)
        else:
            end_page = content_range.end_page
        sections.append(TOCSection(
            title=entry.title,
            level=entry.level,
            start_page=entry.page,
            end_page=end_page,
        ))

    if max_tokens is None:
        return sections

    # Open the document once for token estimation
    doc = pymupdf.open(pdf_path)
    try:
        # Subdivide oversized sections using deeper TOC levels
        changed = True
        while changed:
            changed = False
            new_sections = []
            for sec in sections:
                tokens = _estimate_tokens(doc, sec.start_page, sec.end_page)
                if tokens <= max_tokens:
                    new_sections.append(sec)
                    continue

                # Find child entries one level deeper within this section's range
                children = [
                    e for e in all_entries
                    if e.level == sec.level + 1
                    and e.kind in ("preamble", "content")
                    and sec.start_page <= e.page <= sec.end_page
                ]

                if not children and sec.level >= deepest_level:
                    # No deeper TOC levels — fall back to page-level splitting.
                    # Group consecutive pages into chunks that fit the token budget.
                    chunk_start = sec.start_page
                    part = 1
                    for pg in range(sec.start_page, sec.end_page + 1):
                        chunk_tokens = _estimate_tokens(doc, chunk_start, pg)
                        # If adding this page overflows AND we have at least one page,
                        # close the current chunk and start a new one.
                        if chunk_tokens > max_tokens and pg > chunk_start:
                            new_sections.append(TOCSection(
                                title=f"{sec.title} (part {part})",
                                level=sec.level,
                                start_page=chunk_start,
                                end_page=pg - 1,
                            ))
                            chunk_start = pg
                            part += 1
                    # Final chunk
                    new_sections.append(TOCSection(
                        title=f"{sec.title} (part {part})" if part > 1 else sec.title,
                        level=sec.level,
                        start_page=chunk_start,
                        end_page=sec.end_page,
                    ))
                    changed = part > 1
                    continue

                if not children:
                    new_sections.append(sec)
                    continue

                # Keep the parent as a short intro section if it has pages
                # before the first child
                if children[0].page > sec.start_page:
                    new_sections.append(TOCSection(
                        title=sec.title,
                        level=sec.level,
                        start_page=sec.start_page,
                        end_page=children[0].page - 1,
                    ))

                # Add child sections
                for i, child in enumerate(children):
                    if i + 1 < len(children):
                        end_page = max(child.page, children[i + 1].page - 1)
                    else:
                        end_page = sec.end_page
                    new_sections.append(TOCSection(
                        title=child.title,
                        level=child.level,
                        start_page=child.page,
                        end_page=end_page,
                    ))
                changed = True

            sections = new_sections
    finally:
        doc.close()

    return sections
