# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Qwen 3.5 model support: `qwen3.5:35b-a3b`, `qwen3.5:27b`, `qwen3.5:9b` (Ollama) and MLX 4-bit variants — 262K native context window
- Gemma 4 model support: `gemma4:26b` (MoE), `gemma4:31b` (Dense) (Ollama) and MLX 4-bit variants — 256K context window
- LLM model selection guide (`docs/backends/llm_models.md`) with hardware recommendations, advantages per family, and context window analysis

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
