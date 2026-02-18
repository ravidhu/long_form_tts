# Contributing to long_form_tts

Thanks for your interest in contributing! This guide will help you get started.

## Development setup

```bash
# Clone the repo
git clone https://github.com/ravidhu/long_form_tts.git
cd long_form_tts

# Install dependencies (including dev tools)
uv sync --group dev

# Install pre-commit hooks
uv run pre-commit install
```

## Running tests

```bash
uv run pytest
```

## Code style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configuration lives in `pyproject.toml`.

```bash
# Check for lint issues
uv run ruff check .

# Auto-fix lint issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

Pre-commit hooks run these checks automatically before each commit.

## Project structure

```
src/
  shared/             # Shared packages (used by both pipelines)
    providers/        # LLM and TTS provider configurations
    pdf_parser/       # PDF to markdown conversion and TOC extraction
    markdown_parser/  # Markdown section splitting
    web_parser/       # Web page fetching and section splitting
    audio_assembler/  # Final audio concatenation and export
  audiobook/          # Narration adaptation + single-speaker TTS (audiobook)
    prompts/          # Narration prompt (markdown)
  podcast/            # Dialogue generation + multi-speaker TTS (podcast)
    prompts/          # Dialogue, outline, intro/outro prompts (markdown)
scripts/
  audiobook.py        # Audiobook pipeline entry point
  podcast.py          # Podcast pipeline entry point
  configs/            # User-editable pipeline configurations
tests/                # pytest test suite
docs/                 # Documentation
```

## Submitting changes

1. Fork the repository
2. Create a feature branch (`git checkout -b my-feature`)
3. Make your changes
4. Run tests and linting (`uv run pytest && uv run ruff check .`)
5. Commit with a clear message
6. Open a pull request

## Reporting bugs

Open an issue on [GitHub](https://github.com/ravidhu/long_form_tts/issues) with:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Your environment (Python version, macOS version, chip)
