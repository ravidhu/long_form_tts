# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

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
