# PDF Backends

Two PDF-to-markdown conversion backends are available behind a single interface. The backend is selected at the top of the config and can be swapped without changing any other code.

## pymupdf (default)

**Library**: `pymupdf4llm` (wraps PyMuPDF)

Fast, rule-based extraction. No ML models, no GPU. Detects headers by font size heuristics, handles tables, lists, and multi-column layouts.

- **Speed**: ~0.1s per document
- **Quality**: Good for well-structured text PDFs
- **License**: AGPL-3.0 (commercial license available from Artifex)
- **Install**: Included in base dependencies

Best for: Quick iteration, text-heavy PDFs with clean formatting.

## docling

**Library**: `docling` (IBM)

AI-based document understanding using two models from [`docling-project/docling-models`](https://huggingface.co/docling-project/docling-models):

- **Layout model** (RT-DETR) — detects page regions (titles, section headers, tables, figures, lists, footnotes, etc.) via object detection
- **TableFormer** — reconstructs table structure from detected table regions (95.4% TEDS on simple tables, 90.1% on complex)

Models are downloaded from HuggingFace on first use and cached in `~/.cache/docling/models`. Two ways to pre-fetch for offline use:

```bash
# Docling's own CLI — downloads layout, table, OCR, and classifier models
docling-tools models download

# Or fetch a specific HuggingFace repo directly
huggingface-cli download docling-project/docling-models
```

To use a custom cache path, set `DOCLING_ARTIFACTS_PATH` or pass `--artifacts-path` to the CLI.

- **Speed**: Moderate (faster with GPU)
- **Quality**: Very good, especially for section detection
- **License**: MIT (code), CDLA-Permissive-2.0 + Apache-2.0 (models)
- **Install**: Included in base dependencies

Best for: PDFs with complex layouts, when you need the most accurate section boundaries.

## Comparison

| | pymupdf | docling |
|---|---|---|
| Speed | Very fast | Moderate |
| Tables | Good | Very good |
| Headers | Font-size heuristic | AI layout detection |
| Math/equations | No | Yes |
| GPU required | No | Recommended |
| License | AGPL-3.0 | MIT |

## Usage

```python
from shared.pdf_parser import pdf_to_markdown

# Default (pymupdf)
md = pdf_to_markdown("book.pdf", backend="pymupdf")

# Docling
md = pdf_to_markdown("book.pdf", backend="docling")

# Specific pages (0-indexed)
md = pdf_to_markdown("book.pdf", backend="pymupdf", pages=[14, 15, 16])
```

## Note on TOC analysis

TOC extraction is independent of the markdown conversion backend. It first tries PyMuPDF's embedded bookmarks (`get_toc()`), which reads the PDF's own structure in milliseconds. If bookmarks are missing or cover less than 30% of the document, it falls back to Docling AI layout analysis (`infer_toc()`) to detect headings from font sizes and section numbering.
