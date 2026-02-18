from docling.document_converter import DocumentConverter


def convert(pdf_path: str, pages: list[int] | None = None) -> str:
    """Convert PDF to markdown using Docling (IBM).

    AI-based layout analysis with native hierarchical chunking.
    Best section-level splitting via heading metadata.
    """
    converter = DocumentConverter()

    # Docling uses 1-based page numbers in PaginatedPipelineOptions,
    # but the simplest approach is to convert then filter.
    # For now, convert the full document regardless of pages arg.
    result = converter.convert(pdf_path)

    return result.document.export_to_markdown()
