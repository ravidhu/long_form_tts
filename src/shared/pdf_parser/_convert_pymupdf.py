import pymupdf4llm


def convert(pdf_path: str, pages: list[int] | None = None) -> str:
    """Convert PDF to markdown using pymupdf4llm.

    Fast, rule-based, no GPU required. Good for well-structured text PDFs.
    """
    return pymupdf4llm.to_markdown(pdf_path, pages=pages)
