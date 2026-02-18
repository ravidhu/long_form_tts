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

Both pipelines use a composable config system. Settings are in `scripts/configs/`:

- `scripts/configs/common.py` — shared defaults (`PDF_PARSER_BACKEND`, `MAX_TOC_LEVEL`)
- `scripts/configs/audiobook.py` — audiobook-specific (voice, language, LLM, TTS)
- `scripts/configs/podcast.py` — podcast-specific (dialogue format, speakers, LLM, TTS)

### Audiobook example

```python
from shared.providers import OllamaLLM, KokoroTTS
from audiobook import AudiobookConfig, NarrationConfig

config = AudiobookConfig(
    narration=NarrationConfig(source_lang="en", target_lang="fr"),
    llm=OllamaLLM(model="qwen3:14b"),
    tts=KokoroTTS(voices=("ff_siwis",), speed=0.95),
)
```

### Podcast example

```python
from shared.providers import OllamaLLM, KokoroTTS
from podcast import PodcastConfig, DialogueConfig

config = PodcastConfig(
    dialogue=DialogueConfig(
        format="two_hosts",  # or "host_guest" — see [Dialogue formats](../reference/api_reference.md#dialogue-formats)
        speaker1_name="Alex",
        speaker2_name="Sam",
    ),
    llm=OllamaLLM(model="qwen3:14b"),
    tts=KokoroTTS(voices=("af_heart", "am_michael")),
)
```

### Switching backends

Swap the class to switch backend — no other changes needed:

```python
# Ollama — with optional tuning params
llm=OllamaLLM(model="qwen3:14b", num_ctx=40960, top_p=0.9, repeat_penalty=1.1)

# MLX (Apple Silicon local — HuggingFace MLX weights)
llm=MLXLLM(model="Qwen/Qwen3-14B-MLX-4bit")
```

When using `OllamaLLM`, the pipeline verifies connectivity and model availability at startup (before any PDF processing). See [API Reference — OllamaLLM](../reference/api_reference.md#ollallm) for all available fields.

Same for TTS:

```python
tts=KokoroTTS(voices=("af_heart", "am_michael"))      # pick any voice pair
tts=ChatterboxTTS()                                   # multilingual, voice cloning
```

### Other knobs

| Setting | Where | Default | Description |
|---|---|---|---|
| `PDF_PARSER_BACKEND` | `configs/common.py` | `"pymupdf"` | PDF extraction backend |
| `MAX_TOC_LEVEL` | `configs/common.py` | `1` | TOC depth (1=Parts, 2=Chapters) |
| `max_workers` | `NarrationConfig` | `1` | Parallel LLM requests (audiobook) |
| `segment_target_words` | `DialogueConfig` | `1200` | Words per podcast segment (~8 min) |
| `target_duration_min` | `DialogueConfig` | `None` | Optional hint for outline LLM |
| `inter_section_pause` | Stage 5/7 | `2.0` / `1.5` | Silence between segments (seconds) |

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
