# Content Extraction (Stages 1-2)

These two stages are shared by both the [audiobook](audiobook_pipeline.md) and [podcast](podcast_pipeline.md) pipelines. The implementation lives in [`src/shared/content_extractor.py`](../../src/shared/content_extractor.py).

---

### Stage 1: Input Resolution & Content Extraction

**What it does**: Resolves the input (local PDF, PDF URL, or web page URL) and determines the document's structure.

**Input types**:
- **Local PDF** → TOC analysis and section resolution (below)
- **PDF URL** → Downloaded and cached in `inputs/`, then processed as a local PDF. GitHub blob URLs are auto-rewritten to raw download URLs.
- **Web page URL** → Fetched via trafilatura, content split by headings into sections (requires `[web]` extra)

**How it works** (PDF path):
1. Embedded bookmarks are extracted via `PyMuPDF.get_toc()`. If bookmarks are missing or cover less than 30% of the document, the pipeline falls back to Docling AI layout analysis to detect headings from font sizes and section numbering.
2. Each bookmark is classified by regex on its title:
   - **Front matter** (skipped): Cover, Title Page, Copyright, Table of Contents, etc.
   - **Back matter** (skipped): Index, Glossary, Bibliography, Appendix, etc.
   - **Preamble** (included): Foreword, Preface, Introduction, Acknowledgments
   - **Content** (included): everything else
3. `resolve_content_sections(max_level)` splits content into sections with page ranges
4. Sections that exceed the context budget are auto-subdivided

**Output**: A list of sections in memory, each with a title and page range. Nothing is written to disk yet.

**Key config**: `max_toc_level` and `context_budget` (derived from the LLM's context window) — see [TOC Analysis — Section splitting](../backends/toc_analysis.md#section-splitting) for how these interact (level-based splitting, auto-subdivision of oversized sections, page-level chunking fallback).

| Pipeline | Default `max_toc_level` | Why |
|----------|------------------------|-----|
| Audiobook | `2` | Chapter-granularity — each chapter is narrated independently with no cross-section context |
| Podcast | `1` | Part-level — fewer, larger sections give each conversation segment more material to discuss |

---

### Stage 2: Markdown Extraction

**What it does**: Converts each section's PDF pages into markdown text.

**How it works**:
1. For each section, the page range is passed to `pdf_to_markdown(pdf_path, backend, pages)`
2. The selected backend extracts text, tables, and structure into markdown
3. Each section is saved as a separate `.md` file in `sections/`
4. Structural features are detected: `has_table` (pipe + dashes), `has_list` (bullet/numbered patterns)

**Backends**:
| Backend | Speed | Quality | Notes |
|---|---|---|---|
| `pymupdf` | Very fast | Good | Default, no GPU needed |
| `docling` | Moderate | Very good | Better section detection |

**Output**: `sections/00_Foreword.md`, `sections/01_Chapter_1.md`, etc.

**Cache**: If a section's `.md` file already exists, it's loaded from disk instead of re-extracted.

**Key config**: `pdf_parser` YAML field — see [`pdf_to_markdown()`](../reference/api_reference.md#pdf_to_markdownpdf_path-backendpymupdf-pagesnone---str)
