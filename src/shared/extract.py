"""Shared content extraction — PDF or URL to list of (title, content) tuples.

Wraps pdf_parser and web_parser into simple entry points for pipelines and notebooks.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

import requests

from .pdf_parser import pdf_to_markdown, resolve_content_sections
from .web_parser import fetch_url_content, split_by_headings


@dataclass
class InputSource:
    """Resolved input — either a local PDF or a webpage URL."""

    kind: str  # "pdf" or "url"
    path: str  # local file path (for PDF) or original URL (for webpage)


def resolve_input(value: str, dest_dir: str = "inputs") -> InputSource:
    """Detect whether *value* is a local path, a PDF URL, or a webpage URL.

    - Local path → ``InputSource("pdf", value)``
    - PDF URL (Content-Type or .pdf extension) → download to *dest_dir*,
      return ``InputSource("pdf", local_path)``
    - Webpage URL → ``InputSource("url", value)``
    """
    if not value.startswith(("http://", "https://")):
        return InputSource("pdf", value)

    # Rewrite GitHub blob URLs to raw URLs so we get the actual file
    # e.g. github.com/.../blob/main/f.pdf → raw.githubusercontent.com/.../main/f.pdf
    gh_blob = re.match(
        r"https?://github\.com/([^/]+/[^/]+)/blob/(.+)", value
    )
    if gh_blob:
        value = f"https://raw.githubusercontent.com/{gh_blob.group(1)}/{gh_blob.group(2)}"
        print(f"Resolved GitHub URL → {value}")

    # Determine content type with a HEAD request
    is_pdf = value.lower().endswith(".pdf")
    if not is_pdf:
        try:
            resp = requests.head(value, allow_redirects=True, timeout=10)
            content_type = resp.headers.get("Content-Type", "")
            is_pdf = "application/pdf" in content_type
        except requests.RequestException:
            pass  # fall through — will try as webpage

    if is_pdf:
        # Derive a filename from the URL
        url_path = urlparse(value).path
        filename = os.path.basename(unquote(url_path)) or "download.pdf"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        # Sanitise filename
        filename = re.sub(r"[^\w.\-]", "_", filename)

        os.makedirs(dest_dir, exist_ok=True)
        local_path = os.path.join(dest_dir, filename)

        if os.path.isfile(local_path):
            print(f"Using cached PDF: {local_path}")
        else:
            print(f"Downloading PDF: {value}")
            resp = requests.get(value, timeout=120, stream=True)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            size_mb = os.path.getsize(local_path) / (1 << 20)
            print(f"Saved to {local_path} ({size_mb:.1f} MB)")

        return InputSource("pdf", local_path)

    return InputSource("url", value)


def extract_sections(
    source: str,
    max_toc_level: int = 1,
    context_budget: int = 20_000,
    backend: str = "pymupdf",
    dest_dir: str = "inputs",
) -> list[tuple[str, str]]:
    """Extract sections from a PDF path, PDF URL, or webpage URL.

    Auto-detects the input type:
    - Local file path → PDF extraction
    - URL ending in .pdf (or serving application/pdf) → download + PDF extraction
    - Other URL → webpage fetch + heading split

    Parameters
    ----------
    source : str
        Local PDF path, PDF URL, or webpage URL.
    max_toc_level : int
        Maximum TOC depth (1 = chapters, 2 = sub-chapters).
    context_budget : int
        Max tokens per section (PDF only).
    backend : str
        PDF parser backend ("pymupdf" or "docling").
    dest_dir : str
        Directory to cache downloaded PDFs.

    Returns
    -------
    list of (title, content) tuples
    """
    resolved = resolve_input(source, dest_dir=dest_dir)

    if resolved.kind == "pdf":
        return extract_sections_from_pdf(
            resolved.path,
            max_toc_level=max_toc_level,
            context_budget=context_budget,
            backend=backend,
        )
    else:
        return extract_sections_from_url(
            resolved.path,
            max_toc_level=max_toc_level,
        )


def extract_sections_from_pdf(
    pdf_path: str,
    max_toc_level: int = 1,
    context_budget: int = 20_000,
    backend: str = "pymupdf",
) -> list[tuple[str, str]]:
    """PDF → TOC analysis → per-section markdown extraction.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.
    max_toc_level : int
        Maximum TOC depth (1 = chapters, 2 = sub-chapters).
    context_budget : int
        Max tokens per section (for splitting large TOC entries).
    backend : str
        PDF parser backend ("pymupdf" or "docling").

    Returns
    -------
    list of (title, content) tuples
    """
    toc_sections = resolve_content_sections(
        pdf_path, max_level=max_toc_level, max_tokens=context_budget,
    )

    sections: list[tuple[str, str]] = []
    for toc_sec in toc_sections:
        pages = list(range(toc_sec.start_page, toc_sec.end_page + 1))
        md = pdf_to_markdown(pdf_path, backend=backend, pages=pages)
        sections.append((toc_sec.title, md.strip()))

    return sections


def extract_sections_from_url(
    url: str,
    max_toc_level: int = 1,
) -> list[tuple[str, str]]:
    """URL → fetch → split by headings → list of (title, content) tuples.

    Parameters
    ----------
    url : str
        Webpage URL to fetch.
    max_toc_level : int
        Maximum heading depth to split on.

    Returns
    -------
    list of (title, content) tuples
    """
    markdown = fetch_url_content(url)
    web_sections = split_by_headings(markdown, max_level=max_toc_level)
    return [(ws.title, ws.content.strip()) for ws in web_sections]
