# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

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
