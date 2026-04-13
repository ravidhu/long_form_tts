# CLI Reference

Both pipeline scripts accept CLI flags that override values from the YAML config file. This lets you tweak a run without editing the config.

## Quick start

```bash
# Audiobook — minimal
uv run python scripts/audiobook.py -i docs/book.pdf

# Podcast — minimal
uv run python scripts/podcast.py -i docs/book.pdf

# Override model and voice on the fly
uv run python scripts/audiobook.py -i docs/book.pdf --model qwen3:14b --voice af_heart

# Resume a partial run (no --input needed)
uv run python scripts/podcast.py -o output/podcast_20260413_100000
```

## Shared flags

These flags are available on **both** `audiobook.py` and `podcast.py`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--input`, `-i` | string | *(required)* | Input PDF file path or URL. Can be omitted when resuming a partial run with `--output`. |
| `--output`, `-o` | string | `output/<pipeline>_<timestamp>` | Output directory. Pass an existing directory to resume a partial run — cached sections, narrations, and audio are reused automatically. |
| `--config`, `-c` | string | `scripts/configs/<pipeline>.yaml` | Path to a YAML config file. Falls back to the built-in default config if not provided. |
| `--source-lang` | string | `en` (from config) | Source language code of the input document (e.g. `en`, `fr`, `de`). |
| `--target-lang` | string | `en` (from config) | Target language code for the output audio. Also updates the TTS voice language when using Kokoro. |
| `--model` | string | from config | LLM model name. For Ollama: e.g. `qwen3:14b`, `qwen3.5:35b`. Context window is auto-filled for known models. |
| `--temperature` | float | from config | LLM sampling temperature. Lower values (e.g. `0.3`) produce more deterministic output; higher values (e.g. `0.7`) increase creativity. |
| `--speed` | float | from config | TTS playback speed multiplier. `1.0` is normal speed, `0.95` is slightly slower. For podcasts, this overrides per-voice speeds if set. |

### Config resolution order

CLI flags always take priority over the YAML config file:

1. **`--config`** flag, if provided
2. **`scripts/configs/<pipeline>.yaml`** (user's local config)
3. **`scripts/configs/<pipeline>.default.yaml`** (built-in fallback)

Values from the YAML are loaded first, then any CLI flags override them.

## Audiobook flags

These flags are specific to `audiobook.py`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--voice` | string | from config | TTS voice name for narration. Kokoro examples: `af_heart`, `bf_emma`, `ff_siwis`. Overrides the `tts.voices` config value. |
| `--max-workers` | int | `1` (from config) | Number of parallel LLM requests for narration adaptation. Increase to speed up processing if your hardware supports it. |

### Audiobook examples

```bash
# Basic run
uv run python scripts/audiobook.py -i docs/book.pdf

# From a URL
uv run python scripts/audiobook.py -i https://example.com/article

# Custom output directory
uv run python scripts/audiobook.py -i docs/book.pdf -o output/my_audiobook

# French audiobook from an English PDF
uv run python scripts/audiobook.py -i docs/book.pdf --source-lang en --target-lang fr

# Use a specific model and voice
uv run python scripts/audiobook.py -i docs/book.pdf --model qwen3:14b --voice af_heart

# Speed up LLM processing with parallel workers
uv run python scripts/audiobook.py -i docs/book.pdf --max-workers 4

# Slower narration speed
uv run python scripts/audiobook.py -i docs/book.pdf --speed 0.9

# Resume a partial run (reuses cached sections/narrations/audio)
uv run python scripts/audiobook.py -o output/audiobook_20260413_100000
```

## Podcast flags

These flags are specific to `podcast.py`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--only` | string | *(all segments)* | Render only specific segments. Accepts `intro`, `outro`, or 1-based section numbers. Comma-separated, ranges supported. Output file is named `podcast_partial.wav`. |
| `--voice1` | string | from config | Speaker 1 TTS voice (e.g. `bf_emma`). |
| `--voice2` | string | from config | Speaker 2 TTS voice (e.g. `bm_george`). |
| `--format` | string | `two_hosts` | Dialogue format. Choices: `two_hosts` (equal co-hosts) or `host_guest` (interviewer + expert). |
| `--voice1name` | string | `Alex` | Display name for speaker 1, used in the generated dialogue. |
| `--voice2name` | string | `Sam` | Display name for speaker 2, used in the generated dialogue. |
| `--duration` | int | *(auto)* | Target podcast duration in minutes. Hints the outline LLM to aim for this length. When omitted, the podcast covers all sections. |
| `--segment-words` | int | `1200` | Target words per dialogue segment. At 150 wpm, 1200 words is roughly 8 minutes of audio. |

### The `--only` flag

The `--only` flag lets you re-render specific segments without regenerating the entire podcast. This is useful for fixing a single section or regenerating just the intro/outro.

```
Segment mapping:
  intro     → the intro segment
  1, 2, 3   → 1-based section numbers (matching the TOC sections)
  outro     → the outro segment
```

Values can be combined with commas and ranges:

```bash
# Render only the intro
--only intro

# Render sections 1 through 3
--only 1-3

# Render intro, sections 1-3, and outro
--only intro,1-3,outro

# Render just section 5 and the outro
--only 5,outro
```

### Podcast examples

```bash
# Basic run
uv run python scripts/podcast.py -i docs/book.pdf

# From a URL
uv run python scripts/podcast.py -i https://example.com/article

# Host-guest format with custom names
uv run python scripts/podcast.py -i docs/book.pdf --format host_guest \
  --voice1name "Dr. Lee" --voice2name "Jordan"

# Custom voices
uv run python scripts/podcast.py -i docs/book.pdf --voice1 af_heart --voice2 am_michael

# Target a 30-minute podcast
uv run python scripts/podcast.py -i docs/book.pdf --duration 30

# Shorter segments (more frequent topic changes)
uv run python scripts/podcast.py -i docs/book.pdf --segment-words 800

# Re-render only the intro and outro
uv run python scripts/podcast.py -o output/podcast_20260413_100000 --only intro,outro

# Resume a partial run
uv run python scripts/podcast.py -o output/podcast_20260413_100000
```

## Resuming partial runs

Both pipelines cache intermediate results (sections, narrations/dialogue, audio) in the output directory. To resume a run that was interrupted:

```bash
# Resume — just point --output to the existing directory
uv run python scripts/audiobook.py -o output/audiobook_20260413_100000
uv run python scripts/podcast.py -o output/podcast_20260413_100000
```

When resuming, `--input` can be omitted. The pipeline detects cached files and skips completed stages. This also means you can change flags like `--voice` or `--speed` and re-render only the TTS stage by deleting the `audio/` subdirectory before resuming.

## Supported models

The `--model` flag accepts any model name. For known models (Qwen 3, Qwen 3.5, Gemma 4, Mistral), the context window (`num_ctx`) is auto-configured — no need to set it manually.

For the full list of supported models with context windows, VRAM requirements, and hardware recommendations, see the [LLM Models guide](../backends/llm_models.md).

For unlisted models, set `num_ctx` explicitly in your YAML config.
