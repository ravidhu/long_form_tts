# Getting Started

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- [Ollama](https://ollama.com/) installed and running (for local LLM inference)
- **For TTS**: Apple Silicon Mac (MLX) **or** NVIDIA GPU / CPU (PyTorch)

## Installation

```bash
# Clone and enter the project
cd long_form_tts

# Install base dependencies + TTS runtime for your platform:
uv sync --extra mlx    # Apple Silicon (MLX via mlx-audio)
uv sync --extra torch  # NVIDIA CUDA / AMD ROCm / CPU (PyTorch)

# Pull an LLM model (if using Ollama)
ollama pull qwen3:14b
```

The TTS runtime is auto-detected at startup. Override with `TTS_RUNTIME=mlx` or `TTS_RUNTIME=torch` if both are installed.

### Optional web page extraction

To use web page URLs as input (instead of PDFs), install the `web` extra:

```bash
uv sync --extra web
```

This pulls in [trafilatura](https://trafilatura.readthedocs.io/) for extracting article content from web pages.

### Optional PDF backends

Both PDF backends (`pymupdf` and `docling`) are included in the base dependencies. No extra install needed.

## Running the pipelines

### Input types

Both pipelines accept three kinds of input via `--input` / `-i`:

| Input | Example | Notes |
|-------|---------|-------|
| Local PDF | `-i docs/book.pdf` | |
| PDF URL | `-i https://example.com/paper.pdf` | Auto-downloaded and cached in `inputs/` |
| Web page URL | `-i https://example.com/article` | Extracted via trafilatura (requires `[web]` extra) |

GitHub blob URLs (e.g. `github.com/user/repo/blob/main/file.pdf`) are automatically rewritten to raw download URLs.

### Audiobook

```bash
# From a local PDF
uv run python scripts/audiobook.py -i docs/book.pdf

# From a URL
uv run python scripts/audiobook.py -i https://example.com/paper.pdf

# From a web page
uv run python scripts/audiobook.py -i https://example.com/article

# Specify both input and output
uv run python scripts/audiobook.py -i docs/book.pdf -o output/my_run

# Resume a partial run (--input not needed, reuses cached stages)
uv run python scripts/audiobook.py -o output/my_run

# Cross-language: English PDF → French audiobook
uv run python scripts/audiobook.py -i docs/book.pdf --source-lang en --target-lang fr
```

### Podcast

```bash
uv run python scripts/podcast.py -i docs/book.pdf
uv run python scripts/podcast.py -i https://example.com/article
uv run python scripts/podcast.py -i docs/book.pdf -o output/my_podcast
uv run python scripts/podcast.py -o output/my_podcast  # resume (--input not needed)

# Render only specific segments (partial re-render)
uv run python scripts/podcast.py --output output/my_podcast --only intro,1-3,outro
```

### CLI flags

| Flag | Pipelines | Description |
|------|-----------|-------------|
| `--input`, `-i` | Both | Input PDF file, PDF URL, or web page URL (required unless resuming) |
| `--output`, `-o` | Both | Output directory (pass existing dir to resume) |
| `--source-lang` | Both | Source language code (overrides config) |
| `--target-lang` | Both | Target language code (overrides config, also updates TTS voice) |
| `--only` | Podcast only | Render specific segments: `intro`, `outro`, or 1-based section numbers. Comma-separated, ranges supported (e.g. `intro,1-3,outro`). Outputs `podcast_partial.wav`. |

Short flags `-i` and `-o` are also available. `--input` is required for fresh runs but can be omitted when resuming a partial run (pass `--output` pointing to an existing output directory with cached sections).

## Configuration

Both pipelines use YAML config files. Copy the example and edit:

```bash
cp scripts/configs/audiobook.example.yaml scripts/configs/audiobook.yaml
cp scripts/configs/podcast.example.yaml scripts/configs/podcast.yaml
```

Or pass a custom config with `--config path/to/custom.yaml`.

### Audiobook example (`audiobook.yaml`)

```yaml
source_lang: en
target_lang: fr

llm:
  backend: ollama
  model: qwen3:14b

tts:
  backend: kokoro
  voices: [ff_siwis]
  speed: 0.95
```

### Podcast example (`podcast.yaml`)

```yaml
dialogue:
  format: two_hosts
  speaker1_name: Alex
  speaker2_name: Sam

llm:
  backend: ollama
  model: qwen3:14b

tts:
  backend: kokoro
  voices: [af_heart, am_michael]
```

### Switching backends

Change one line in the YAML:

```yaml
# Ollama (local server)
llm:
  backend: ollama
  model: qwen3:14b
  # num_ctx: 40960          # optional — auto-filled from known models

# MLX (Apple Silicon local)
llm:
  backend: mlx
  model: Qwen/Qwen3-14B-MLX-4bit
```

When using `ollama`, the pipeline verifies connectivity and model availability at startup (before any PDF processing). See [API Reference — OllamaLLM](../reference/api_reference.md#ollallm) for all available fields.

Same for TTS:

```yaml
# Kokoro — lightweight, multi-language
tts:
  backend: kokoro
  voices: [af_heart, am_michael]

# Chatterbox — multilingual, voice cloning
tts:
  backend: chatterbox
  audio_prompts: [voices/host.wav, voices/guest.wav]
```

### Other knobs

| Setting | Where | Default | Description |
|---|---|---|---|
| `pdf_parser` | YAML root | `pymupdf` | PDF extraction backend (`pymupdf` or `docling`) |
| `max_toc_level` | YAML root | `1` / `2` | TOC depth (1=Parts, 2=Chapters) |
| `narration.max_workers` | audiobook YAML | `1` | Parallel LLM requests |
| `dialogue.segment_target_words` | podcast YAML | `1200` | Words per podcast segment (~8 min) |
| `dialogue.target_duration_min` | podcast YAML | (none) | Optional hint for outline LLM |

## Output

Generated files go to `output/` (git-ignored), in a timestamped directory per run. Each invocation also creates a timestamped log file (`run_*.log`) that mirrors all terminal output, so you have a full record even if a run is interrupted:

```
output/audiobook_20260208_120000/   # audiobook run
├── run_20260208_120000.log   # Log of first run
├── run_20260208_130000.log   # Log of resumed run
├── sections/       # Markdown per section
├── narrations/     # LLM narration scripts
├── audio/          # Per-section wav files
└── audiobook.wav   # Final assembled audiobook

output/podcast_20260208_120000/    # podcast run
├── run_20260208_120000.log
├── sections/       # Markdown per section
├── dialogue/       # Dialogue segments + intro/outro
├── audio/          # Per-segment wav files
├── podcast_outline.md
└── podcast.wav     # Final assembled podcast
```

## Troubleshooting

See [Troubleshooting](../reference/troubleshooting.md) for common errors and how to fix them.
