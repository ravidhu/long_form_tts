# API Reference

## shared.providers

Shared configuration classes for LLM and TTS backends. Used by both pipelines.

### LLM backends

```python
from shared.providers import OllamaLLM, MLXLLM
```

#### `OllamaLLM`

| Field | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | `"qwen3:14b"` | Ollama model name |
| `url` | `str` | `"http://localhost:11434"` | Ollama API URL |
| `num_ctx` | `int` | `40960` | Context window size |
| `temperature` | `float` | `0.7` | Sampling temperature |
| `timeout` | `int` | `600` | Request timeout in seconds (10 min default for large sections) |
| `num_predict` | `int` | `-1` | Max output tokens (`-1` = unlimited) |
| `top_k` | `int \| None` | `None` | Top-k sampling (omitted from request when `None`) |
| `top_p` | `float \| None` | `None` | Nucleus sampling (omitted when `None`) |
| `repeat_penalty` | `float \| None` | `None` | Repetition penalty (omitted when `None`) |
| `stop` | `list[str] \| None` | `None` | Stop sequences (omitted when `None`) |

Optional fields (`top_k`, `top_p`, `repeat_penalty`, `stop`) are only sent to Ollama when explicitly set. Existing behavior is unchanged unless you configure them.

**Robustness**: Requests include a configurable `timeout`, automatic retry (3 attempts with exponential backoff on connection errors, timeouts, and 5xx responses), and HTTP error messages that include the model name, status code, and truncated response body.

#### `MLXLLM`

| Field | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | `"Qwen/Qwen3-14B-MLX-4bit"` | HuggingFace repo with MLX weights |
| `max_tokens` | `int` | `8192` | Max output tokens |
| `temperature` | `float` | `0.7` | Sampling temperature |

Runs HuggingFace models locally on Apple Silicon via `mlx-lm`. The model is downloaded on first use (cached in `~/.cache/huggingface/`) and stays loaded in memory across all calls within a run.

### `llm_generate(system, prompt, llm) -> str`

Unified LLM text generation. Dispatches on `isinstance(llm, ...)`.

| Parameter | Type | Description |
|---|---|---|
| `system` | `str` | System prompt |
| `prompt` | `str` | User prompt |
| `llm` | `OllamaLLM \| MLXLLM` | Backend config |

**Reasoning model support**: `<think>...</think>` blocks emitted by reasoning models (e.g. Qwen3) are automatically stripped from the output, so downstream stages only receive the final answer.

### `ollama_preflight(llm: OllamaLLM) -> None`

Verify that Ollama is reachable and the requested model is available. Raises `RuntimeError` with actionable messages on failure:

- `"Ollama not reachable at {url} — is it running? (ollama serve)"`
- `"Model '{model}' not found. Available: [...]. Pull it with ollama pull {model}"`

Results are cached per `(url, model)` pair — only the first call does network I/O. Both pipeline scripts call this at startup (Stage 1) when the LLM backend is `OllamaLLM`.

### TTS backends

```python
from shared.providers import KokoroTTS, ChatterboxTTS
```

#### `KokoroTTS`

| Field | Type | Default | Description |
|---|---|---|---|
| `lang` | `str \| None` | `None` | Auto-select voices from `KOKORO_VOICE_PRESETS`. Set by pipeline config from `target_lang`. |
| `voices` | `tuple[str, ...] \| None` | `None` | Voice names. Auto-resolved from `lang` if not set. 1 for audiobook, 2 for podcast. |
| `speed` | `float` | `0.95` | Global speech speed multiplier |
| `speeds` | `tuple[float, ...] \| None` | `None` | Per-voice speeds (overrides `speed`). Index matches `voices`. |

Voice naming convention: `{accent}{gender}_{name}`

| Prefix | Accent | Gender |
|---|---|---|
| `af` | American | Female |
| `am` | American | Male |
| `bf` | British | Female |
| `bm` | British | Male |
| `ff` | French | Female |
| `hf` | Hindi | Female |
| `hm` | Hindi | Male |
| `jf` | Japanese | Female |
| `jm` | Japanese | Male |
| `zf` | Chinese | Female |
| `zm` | Chinese | Male |

67 voices total. To list all available voices, run:

```python
from huggingface_hub import list_repo_tree
[f.path for f in list_repo_tree("hexgrad/Kokoro-82M", path_in_repo="voices")]
```

#### `ChatterboxTTS`

| Field | Type | Default | Description |
|---|---|---|---|
| `audio_prompts` | `tuple[str, ...] \| None` | `None` | Reference audio paths for voice cloning (1 for audiobook, 2 for podcast) |
| `exaggeration` | `float` | `0.5` | Emotion exaggeration control |
| `cfg` | `float` | `0.5` | Classifier-free guidance strength |
| `lang` | `str \| None` | `None` | Language code (e.g. "en", "fr") |

Multilingual TTS with voice cloning support. 23 languages. Use `audio_prompts` to clone voices from reference audio files. No native speed control — the model uses a fixed token-to-mel mapping with no duration predictor.

---

## shared.pdf_parser

### `pdf_to_markdown(pdf_path, backend="pymupdf", pages=None) -> str`

Convert a PDF file to markdown text using the selected backend.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pdf_path` | `str` | required | Path to the PDF file |
| `backend` | `"pymupdf" \| "docling"` | `"pymupdf"` | Conversion engine |
| `pages` | `list[int] \| None` | `None` | 0-indexed page numbers to extract. `None` = all pages |

### `extract_toc(pdf_path) -> list[TOCEntry]`

Extract the Table of Contents from a PDF's embedded bookmarks. Returns an empty list if the PDF has no embedded TOC.

### `resolve_content_pages(pdf_path, min_coverage=0.3) -> ContentRange`

Analyze the TOC to find the page range of actual content. Skips front matter (cover, copyright, TOC) and back matter (index, glossary, colophon). Includes preamble (foreword, preface).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pdf_path` | `str` | required | Path to the PDF file |
| `min_coverage` | `float` | `0.3` | Min fraction (0.0–1.0) of pages the embedded TOC must span to be trusted |

### `resolve_content_sections(pdf_path, max_level=1, max_tokens=24000, min_coverage=0.3) -> list[TOCSection]`

Split the PDF into content sections with page ranges, driven by the TOC. Auto-subdivides oversized sections using deeper TOC levels or page-level chunking.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pdf_path` | `str` | required | Path to the PDF file |
| `max_level` | `int` | `1` | Max TOC depth. 1 = Parts, 2 = Chapters |
| `max_tokens` | `int \| None` | `24000` | Max estimated tokens per section. `None` = no limit. |
| `min_coverage` | `float` | `0.3` | Min fraction (0.0–1.0) of pages the embedded TOC must span to be trusted |

### Data classes

```python
@dataclass
class TOCEntry:
    level: int        # TOC depth (1 = top-level)
    title: str        # Bookmark title
    page: int         # 0-indexed page number
    kind: str         # "front", "back", "preamble", or "content"

@dataclass
class ContentRange:
    start_page: int           # inclusive, 0-indexed
    end_page: int             # inclusive, 0-indexed
    total_pages: int
    skipped_front: list[str]  # descriptions of skipped front matter entries
    skipped_back: list[str]   # descriptions of skipped back matter entries

@dataclass
class TOCSection:
    title: str        # Section title from TOC
    level: int        # TOC depth
    start_page: int   # inclusive, 0-indexed
    end_page: int     # inclusive, 0-indexed
```

### Front/back matter classification

TOC entries are classified by matching their title against regex patterns:

**Front matter** (skipped): Cover, Half Title, Title Page, Copyright, Table of Contents, Contents, List of Figures/Tables, Dedication, Epigraph, Praise, Endorsements, Also By, About the Cover

**Back matter** (skipped): Index, Glossary, Bibliography, References, About the Author(s), Colophon, Appendix

**Preamble** (included as content): Foreword, Preface, Introduction, Acknowledgments

---

## shared.markdown_parser

### `parse_markdown(text, default_lang="en") -> list[Section]`

Split markdown text by `## ` headers and detect structural elements.

> **Note**: In the current pipeline, this is only used for building `Section` objects from pre-extracted per-section markdown. The TOC drives the actual section splitting, not `## ` headers.

```python
@dataclass
class Section:
    title: str        # Section title
    content: str      # Markdown content
    has_table: bool   # True if content contains markdown tables
    has_list: bool    # True if content contains bullet/numbered lists
    language: str     # "en" or "fr"
```

---

## audiobook

### Config classes

```python
from audiobook import AudiobookConfig, NarrationConfig

@dataclass
class NarrationConfig:
    source_lang: str = "en"    # language of the PDF
    target_lang: str = "en"    # language for the audiobook
    max_workers: int = 1       # parallel LLM requests

@dataclass
class AudiobookConfig:
    narration: NarrationConfig
    llm: OllamaLLM | MLXLLM
    tts: KokoroTTS | ChatterboxTTS
```

### `adapt_narration_section(section, llm, source_lang="en", target_lang="en") -> str`

Send a `Section` to an LLM for narration conversion. Works with any LLM backend (Ollama, MLX).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `section` | `Section` | required | Section to adapt |
| `llm` | `LLMBackend` | required | LLM config (OllamaLLM or MLXLLM) |
| `source_lang` | `str` | `"en"` | PDF language |
| `target_lang` | `str` | `"en"` | Audiobook language |

Returns narration text with `[PAUSE_SHORT]`, `[PAUSE_MEDIUM]`, `[PAUSE_LONG]` markers.

Supports any language pair the LLM can handle. A dynamic language instruction is appended to the base English prompt for non-English targets.

### Constants

- `NARRATION_SYSTEM_PROMPT` — Narrator adaptation prompt loaded from [`prompts/narration_system.md`](../../src/audiobook/prompts/narration_system.md) (language instruction appended dynamically)

---

### `load_tts_model(tts) -> model`

Load a TTS model based on config type. Call once, pass to `render_section()`.

| Parameter | Type | Description |
|---|---|---|
| `tts` | `KokoroTTS \| ChatterboxTTS` | TTS config |

### `render_section(narration, tts, model=None) -> np.ndarray`

Render narration text with pause markers into a numpy audio array.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `narration` | `str` | required | Text with pause markers |
| `tts` | `KokoroTTS \| ChatterboxTTS` | required | TTS config |
| `model` | TTS model | required | From `load_tts_model()` |

Returns a float32 numpy array at 24kHz sample rate.

### Constants

| Constant | Value |
|---|---|
| `SAMPLE_RATE` | `24000` |

### Pause markers

| Marker | Duration |
|---|---|
| `[PAUSE_SHORT]` | 0.5s |
| `[PAUSE_MEDIUM]` | 1.2s |
| `[PAUSE_LONG]` | 2.0s |

---

## podcast

### Config classes

```python
from podcast import PodcastConfig, DialogueConfig

@dataclass
class DialogueConfig:
    format: str = "two_hosts"          # "two_hosts" | "host_guest"
    speaker1_name: str = "Alex"
    speaker2_name: str = "Sam"
    source_lang: str = "en"            # language of the PDF
    target_lang: str = "en"            # language for the podcast dialogue
    target_duration_min: int | None = None  # optional hint for outline LLM
    words_per_minute: int = 150
    segment_target_words: int = 1200   # ~8 min per segment

@dataclass
class PodcastConfig:
    dialogue: DialogueConfig
    llm: OllamaLLM | MLXLLM
    tts: KokoroTTS | ChatterboxTTS
```

### `generate_outline(sections_markdown, config) -> PodcastOutline`

Generate a global podcast outline from section titles and content.

| Parameter | Type | Description |
|---|---|---|
| `sections_markdown` | `list[tuple[str, str]]` | List of (title, content) tuples |
| `config` | `PodcastConfig` | Pipeline config |

Returns a `PodcastOutline` with `raw_text` (full LLM output) and `title` (parsed episode title).

### `generate_dialogue_segment(section_content, section_title, outline, segment_index, rolling_summary, covered_topics, config) -> DialogueSegment`

Generate dialogue for one segment with rolling context.

| Parameter | Type | Description |
|---|---|---|
| `section_content` | `str` | Markdown content for this section |
| `section_title` | `str` | Section title |
| `outline` | `PodcastOutline` | Global outline (stays constant) |
| `segment_index` | `int` | 0-based segment index |
| `rolling_summary` | `str` | Summary of all previous segments |
| `covered_topics` | `list[str]` | Topics already discussed |
| `config` | `PodcastConfig` | Pipeline config |

Returns a `DialogueSegment` with `dialogue`, `updated_summary`, and `covered_topics`.

### `generate_intro_outro(outline, all_topics, config) -> tuple[str, str]`

Generate intro and outro dialogue. Returns `(intro, outro)` tuple.

### Data classes

```python
@dataclass
class PodcastOutline:
    raw_text: str           # Full LLM output
    title: str = ""         # Parsed episode title
    segments: list[dict] = field(default_factory=list)

@dataclass
class DialogueSegment:
    dialogue: str           # Dialogue with [S1]/[S2] tags
    updated_summary: str    # Rolling summary after this segment
    covered_topics: list[str]  # All topics covered so far
```

### Dialogue formats

- **`two_hosts`** — two equal hosts discussing. Both knowledgeable, build on each other's points.
- **`host_guest`** — interviewer + expert. Host asks questions, guest provides expertise.

### Speaker tags

All dialogue uses `[S1]` and `[S2]` as universal speaker tags:

- Parseable for Kokoro (split and alternate voices)
- Parseable for Chatterbox (split and alternate reference audio)

### `load_tts_model(tts) -> model`

Load a TTS model based on the config type. Call once, pass to `render_dialogue()`.

| Parameter | Type | Description |
|---|---|---|
| `tts` | `KokoroTTS \| ChatterboxTTS` | TTS config |

Models loaded (MLX):

| Config | Model |
|---|---|
| `KokoroTTS` | `mlx-community/Kokoro-82M-bf16` |
| `ChatterboxTTS` | `mlx-community/chatterbox-fp16` |

### `render_dialogue(dialogue, tts, model=None) -> np.ndarray`

Render podcast dialogue to audio.

| Parameter | Type | Description |
|---|---|---|
| `dialogue` | `str` | Text with `[S1]`/`[S2]` tags and `[PAUSE_*]` markers |
| `tts` | `KokoroTTS \| ChatterboxTTS` | TTS config |
| `model` | TTS model | From `load_tts_model()` |

Returns a float32 numpy array at 24kHz sample rate.

### Constants

| Constant | Value |
|---|---|
| `SAMPLE_RATE` | `24000` |

---

## shared.web_parser

Web page content extraction and section splitting. Requires the `web` optional dependency (`uv sync --extra web`).

```python
from shared.web_parser import fetch_url_content, split_by_headings, WebSection
```

### `fetch_url_content(url) -> str`

Download a web page and extract its main content as Markdown via [trafilatura](https://trafilatura.readthedocs.io/). Links and images are removed; formatting and tables are preserved.

| Parameter | Type | Description |
|---|---|---|
| `url` | `str` | Web page URL to fetch |

Raises `RuntimeError` if the page cannot be fetched or yields no extractable content. Raises `ImportError` if trafilatura is not installed.

### `split_by_headings(markdown, max_level=2) -> list[WebSection]`

Split Markdown text into sections at headings up to the specified depth.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `markdown` | `str` | required | Markdown text to split |
| `max_level` | `int` | `2` | Max heading depth (`1` = `#` only, `2` = `#` and `##`, etc.) |

Text before the first heading becomes an "Introduction" section. If no headings are found, the entire text is returned as a single "Full article" section.

### Data classes

```python
@dataclass
class WebSection:
    title: str      # Section title (from heading)
    content: str    # Markdown body (without the heading line)
```

---

## shared.audio_assembler

### `assemble_audiobook(audio_segments, output_path, sample_rate=24000, inter_section_pause=2.0) -> None`

Concatenate audio arrays with silence between them and write to wav. Used by both pipelines.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `audio_segments` | `list[np.ndarray]` | required | One array per section/segment |
| `output_path` | `str` | required | Output wav file path |
| `sample_rate` | `int` | `24000` | Sample rate |
| `inter_section_pause` | `float` | `2.0` | Seconds of silence between sections |
