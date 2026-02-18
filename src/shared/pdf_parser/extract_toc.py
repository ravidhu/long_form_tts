"""Extract the embedded TOC from a PDF's bookmarks via PyMuPDF."""

import pymupdf

from .types import TOCEntry


def extract_toc(pdf_path: str) -> list[TOCEntry]:
    """Extract the Table of Contents from a PDF's embedded bookmarks.

    Returns a list of TOCEntry with level, title, and 0-indexed page number.
    Returns an empty list if the PDF has no embedded TOC.
    """
    doc = pymupdf.open(pdf_path)
    try:
        raw_toc = doc.get_toc()
    finally:
        doc.close()

    entries = []
    for level, title, page_1based in raw_toc:
        page_0 = page_1based - 1
        if page_0 < 0:
            continue  # skip invalid/corrupt bookmarks
        entries.append(TOCEntry(
            level=level,
            title=title.strip(),
            page=page_0,
        ))
    return entries
