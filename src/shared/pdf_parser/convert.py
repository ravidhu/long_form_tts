"""Convert a PDF to markdown text using pluggable backends."""

import importlib
from typing import Literal

Backend = Literal["pymupdf", "docling"]

BACKENDS = {
    "pymupdf": "shared.pdf_parser._convert_pymupdf",
    "docling": "shared.pdf_parser._convert_docling",
}


def pdf_to_markdown(
    pdf_path: str,
    backend: Backend = "pymupdf",
    pages: list[int] | None = None,
) -> str:
    """Convert a PDF file to markdown text.

    Args:
        pdf_path: Path to the PDF file.
        backend: Which conversion engine to use:
            - "pymupdf" (default): Fast, rule-based, no GPU. Good for text PDFs.
            - "docling": AI-based, best section detection, MIT license.
        pages: Optional list of page numbers (0-indexed) to extract.
               If None, extracts all pages.

    Returns:
        Markdown string with headers, tables, and lists preserved.
    """
    if backend not in BACKENDS:
        raise ValueError(f"Unknown backend: {backend!r}. Choose from: {list(BACKENDS)}")

    module = importlib.import_module(BACKENDS[backend])
    return module.convert(pdf_path, pages=pages)
