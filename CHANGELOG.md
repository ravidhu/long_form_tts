# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.3.2] — 2026-04-14

### Added

- CLI reference documentation (`docs/reference/cli_reference.md`) — comprehensive guide to all flags for `audiobook.py` and `podcast.py`, including supported models and resume workflow
- Tests for audiobook block splitting with research paper metadata scenarios (`tests/blocks/test_blocks.py`)
- Tests for section overlap trimming (`tests/blocks/test_trim_overlap.py`)
- `stitch_broken_lines()` preprocessing step that rejoins sentences split by PDF column extraction — orphaned citations (`[49]`), column-break blank lines, and dash continuations are stitched back to their preceding sentence before block splitting
- Tests for line stitching (`tests/blocks/test_stitch.py`)
- `inline_enum_to_spoken()` converts inline enumerations (`1)`, `(2)`, `(a)`) to spoken ordinals ("first,", "second,") in narration — runs before `number_to_spoken` to avoid producing "one)" from TTS
- Tests for inline enumeration conversion (`tests/blocks/test_inline_enum.py`)

### Fixed

- Research paper metadata (author affiliations, conference venue lines, name lists) no longer leaks into audiobook narration — relaxed metadata continuation logic so short non-structural lines stay grouped within the metadata block they belong to
- Added detection patterns for IEEE attributions, `Proceedings of` references, running headers ending with "et al.", and submission history lines
- Section overlap: content from earlier sections on the same start page no longer bleeds into subsequent sections — added begin-trim to `_trim_shared_page` that finds the current section's heading and discards everything before it
- Fixed broken `#{1,6}` regex quantifier in f-strings (was silently producing `#(1, 6)` instead of matching 1-6 `#` characters) — markdown heading patterns now match correctly
- Removed `\bResearch\b` from author-line metadata pattern — the case-insensitive match caused false positives on regular prose (e.g. "Much research on"), breaking paragraphs mid-sentence and swallowing content as metadata. Institution names like "Microsoft Research" are still captured via metadata continuation
- "Python quit unexpectedly" crash dialog on macOS at script exit — explicitly delete TTS model and clear MLX Metal cache before Python's GC destroys GPU resources in arbitrary order
- Qwen 3.5 model support: `qwen3.5:35b-a3b`, `qwen3.5:27b`, `qwen3.5:9b` (Ollama) and MLX 4-bit variants — 262K native context window
- Gemma 4 model support: `gemma4:26b` (MoE), `gemma4:31b` (Dense) (Ollama) and MLX 4-bit variants — 256K context window
- LLM model selection guide (`docs/backends/llm_models.md`) with hardware recommendations, advantages per family, and context window analysis

### Fixed

- Documentation: `adapt_narration_section` return type updated to `tuple[str, int]` (was incorrectly documented as `str`)
- Documentation: `AudiobookConfig.tts` type corrected to `KokoroTTS | ChatterboxTTS` (was showing only `KokoroTTS`)
- Documentation: broken relative links (`../src/` → `../../src/`) in architecture and pipeline docs
- Documentation: stale Python constant references (`MAX_TOC_LEVEL`, `CONTEXT_BUDGET`, `PDF_PARSER_BACKEND`) replaced with current YAML field names
- Documentation: troubleshooting examples updated from Python constructor syntax to YAML config syntax
- Documentation: added `content_extractor.py` and `extract.py` to architecture package map
- Documentation: reduced redundancy — extracted shared Stages 1-2 into `docs/architecture/content_extraction.md`, replaced duplicated TTS config fields and data class definitions with cross-references, replaced duplicated model tables and `--only` descriptions with cross-references

### Changed

- Increased MLX default `max_tokens` from 8192 to 16384 to prevent output truncation on large sections — aligns with the large context windows (128K-262K) of supported models
- Extracted shared content extraction (Stages 1-2) into `src/shared/content_extractor.py`, eliminating ~320 lines of duplicated resume/URL/PDF logic between audiobook and podcast scripts
- Extracted shared CLI argument parsing and config resolution into `scripts/configs/cli_arg_parser.py`
- Slimmed `scripts/audiobook.py` from 547 to ~330 lines and `scripts/podcast.py` from 666 to ~460 lines

## [0.3.1] - 2026-04-11

### Fixed

- Electron Windows/Linux builds missing bundled Python project files (Docker volume mounts used wrong paths)
- Electron builds missing bundled `uv` binary (`${platform}` → `${os}` in electron-builder extraResources)

## [0.3.0] - 2026-04-10

### Added

- Hybrid narration pipeline: rule-based preprocessing for paragraphs/headings, LLM only for tables, code, lists, and metadata blocks
- Block splitter (`blocks.py`) to classify markdown into typed blocks (paragraph, heading, table, code, list, metadata)
- Deterministic text preprocessor (`preprocess.py`) for markdown stripping, number-to-spoken conversion, and abbreviation expansion
- Block-specific LLM prompts for table-to-prose, code-to-description, list-to-prose, metadata classification, and translation
- Stage 3 output now shows "rule-based" or LLM call count per section
- YAML-based configuration (`audiobook.yaml`, `podcast.yaml`) replacing Python config files
- `--config` CLI flag to pass a custom YAML config file
- Default configs (`audiobook.default.yaml`, `podcast.default.yaml`)

### Removed

- Acknowledgments, appendices, and references sections are now classified as back matter and skipped in both audiobook and podcast pipelines
- Python config files (`scripts/configs/audiobook.py`, `scripts/configs/podcast.py`) replaced by YAML

### Fixed

- Duplicate narration content when TOC entries share the same PDF page (parent/child and sibling overlaps)
- Shared-page trimming in Stage 2 to cut extracted markdown at the next section's heading
- `fmt_time()` now shows sub-second durations (e.g. `0.35s`) instead of truncating to `00:00:00`

### Changed

- `adapt_narration_section` returns `(str, int)` tuple (narration text + LLM call count)
- Upgraded docling 2.72→2.86, mlx-lm 0.29→0.31, mlx-audio 0.2.10→0.4.2, transformers 4.57→5.5, huggingface-hub 0.36→1.10
- Removed mlx-audio version pin (docling >=2.86 relaxed huggingface_hub constraint)

## [0.2.0] - 2026-03-31

### Added

- Electron desktop app with configuration panel, job queue, and setup wizard
- Tab-based UI layout (Configuration / Queue) with Radix UI Tabs
- Job queue with start, stop, re-queue, clear done, and clear all controls
- Stage progress list showing all pipeline stages with checkmarks for completed ones
- Queue tab badge showing count of running + queued jobs
- Tooltip explanations for Target Duration and Words per Segment fields
- Stderr capture to log files in output folder via TeeLogger
- First-launch setup flow: bundled uv copies project source, installs Python, and syncs dependencies
- CLI overrides for LLM, TTS, and pipeline settings in audiobook and podcast scripts

### Fixed

- Cross-language voice resolution: `--target-lang` now re-resolves TTS voices for the target language
- Single-voice languages (e.g. French) work in podcast mode by duplicating the voice with a slight speed offset
- Clear All no longer removes running tasks
- Stopped tasks show distinct status (yellow icon) instead of appearing as errors
- Tooltip backgrounds now use solid dark background instead of transparent

### Changed

- Renamed `speaker1`/`speaker2` config fields to `voice1name`/`voice2name`
- Log viewer filters out noisy terminal output (separators, config headers, stage banners)

## [0.1.0] - 2025-02-14

### Added

- Audiobook pipeline: PDF to single-narrator audio via LLM adaptation and Kokoro TTS
- Podcast pipeline: PDF to two-speaker conversational audio via LLM dialogue generation
- PDF parsing with pymupdf and docling backends
- TOC extraction, inference, and content resolution
- Web page fetching and section splitting
- LLM backends: Ollama (local), MLX (Apple Silicon local)
- TTS backends: Kokoro, Dia, Chatterbox (MLX and PyTorch)
- Resumable pipelines with per-section caching
- Cross-language narration and translation support
- Audio assembly with inter-section pauses
