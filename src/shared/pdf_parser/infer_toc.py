"""Infer a TOC via Docling AI layout analysis when no embedded TOC exists."""

import re
from collections import Counter
from functools import lru_cache

import pymupdf
from docling.document_converter import DocumentConverter
from docling_core.types.doc.labels import DocItemLabel

from .types import TOCEntry


def _lookup_font_size(doc: pymupdf.Document, title: str, page_num: int) -> float | None:
    """Find the font size of a heading by matching its text on the given page.

    Searches each text line on the page for the title (case-insensitive
    substring match) and returns the maximum span font size of the first
    matching line.  Returns None if not found.
    """
    page = doc[page_num]
    title_lower = title.lower()
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            if title_lower in line_text.lower():
                return max(span["size"] for span in line["spans"])
    return None


@lru_cache(maxsize=4)
def infer_toc(pdf_path: str) -> list[TOCEntry]:
    """Infer a TOC using Docling AI layout analysis when no embedded TOC exists.

    Uses Docling (IBM) to detect headings via document layout analysis,
    then assigns hierarchy levels using two strategies:

      1. **Numbering-based** (when majority of headings have section numbers
         like "3.1.2"): level = dot-count + 1.  Headings without numbering
         (e.g. "Preface") get level 1.
      2. **Font-size fallback** (no numbering): looks up each heading's font
         size in PyMuPDF, finds distinct sizes, largest = L1, rest = L2.

    Noise filters (running headers, math labels, short text, duplicates) are
    applied before level assignment.

    Cached so repeated calls for the same file are free.
    """
    print("  No embedded TOC found — inferring with Docling layout analysis...")

    # 1. Docling heading detection
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    ddoc = result.document

    raw_headings: list[tuple[str, int | None]] = []  # (title, page_0indexed)
    for item, _level in ddoc.iterate_items():
        if item.label in (DocItemLabel.TITLE, DocItemLabel.SECTION_HEADER):
            page = None
            if hasattr(item, "prov") and item.prov:
                page = item.prov[0].page_no - 1  # convert 1-based → 0-indexed
            title = item.text.strip()
            if title:
                raw_headings.append((title, page))

    if not raw_headings:
        print("  Docling found no headings.")
        return []

    print(f"  Docling detected {len(raw_headings)} raw headings.")

    # 2. Noise filters
    # 2a. Min length: < 3 chars → discard
    raw_headings = [(t, p) for t, p in raw_headings if len(t) >= 3]

    # 2b. Math/axis labels (e.g. "x(2)", "f(x)") → discard
    raw_headings = [(t, p) for t, p in raw_headings
                    if not re.match(r"^[a-z]\(.+\)$", t)]

    # 2c. Running headers/footers — titles appearing >2 times → discard
    title_counts: Counter[str] = Counter(t for t, _ in raw_headings)
    raw_headings = [(t, p) for t, p in raw_headings if title_counts[t] <= 2]

    # 2d. Deduplicate — keep first occurrence only
    seen: set[str] = set()
    headings: list[tuple[str, int | None]] = []
    for title, page in raw_headings:
        if title not in seen:
            seen.add(title)
            headings.append((title, page))

    if not headings:
        print("  No usable headings after filtering.")
        return []

    # 3. Hierarchy assignment
    # Check if majority of headings have section numbering (e.g. "3.1.2 Title")
    num_pattern = re.compile(r"^(\d+(?:\.\d+)*)\s")
    numbered = [(num_pattern.match(t), t, p) for t, p in headings]
    num_count = sum(1 for m, _, _ in numbered if m)
    use_numbering = num_count > len(headings) * 0.5

    entries: list[TOCEntry] = []

    if use_numbering:
        # Numbering-based: level = dot-count + 1
        print("  Using section-numbering for hierarchy.")
        for match, title, page in numbered:
            level = match.group(1).count(".") + 1 if match else 1
            entries.append(TOCEntry(level=level, title=title, page=page or 0))
    else:
        # Font-size fallback: look up sizes in PyMuPDF, largest = L1, rest = L2
        print("  No section numbering — using font-size for hierarchy.")
        doc = pymupdf.open(pdf_path)
        sized: list[tuple[float, str, int]] = []
        for title, page in headings:
            fs = _lookup_font_size(doc, title, page) if page is not None else None
            sized.append((fs or 0.0, title, page or 0))
        doc.close()

        # Find distinct font sizes among headings
        distinct_sizes = sorted({s for s, _, _ in sized if s > 0}, reverse=True)
        if len(distinct_sizes) >= 2:
            largest = distinct_sizes[0]
            for size, title, page in sized:
                level = 1 if size >= largest else 2
                entries.append(TOCEntry(level=level, title=title, page=page))
        else:
            # Single size or no sizes found — all level 1
            for _size, title, page in sized:
                entries.append(TOCEntry(level=1, title=title, page=page))

    print(f"  Inferred {len(entries)} TOC entries.")
    return entries
