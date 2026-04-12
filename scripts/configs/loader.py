"""Load pipeline configuration from YAML files.

Converts a flat YAML dict into the typed dataclass hierarchy used by
the audiobook and podcast pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from shared.providers import MLXLLM, ChatterboxTTS, KokoroTTS, OllamaLLM

# Known model context windows (for budget calculation)
MODELS: dict[str, int] = {
    # ── Qwen 3 (Ollama) ──
    "qwen3:32b":        40960,
    "qwen3:14b":        40960,
    "qwen3:8b":         40960,
    "qwen3:30b-a3b":    262144,
    # ── Qwen 3.5 (Ollama) ──
    "qwen3.5:35b-a3b":  262144,
    "qwen3.5:27b":      262144,
    "qwen3.5:9b":       262144,
    # ── Gemma 4 (Ollama) ──
    "gemma4:26b":       262144,
    "gemma4:31b":       262144,
    # ── Mistral (Ollama) ──
    "mistral-small3.2:24b-instruct-2506-q8_0": 131072,
    "mistral-nemo":     131072,
    # ── Qwen 3 (MLX) ──
    "Qwen/Qwen3-8B-MLX-4bit":      40960,
    "Qwen/Qwen3-14B-MLX-4bit":     40960,
    "Qwen/Qwen3-32B-MLX-4bit":     40960,
    "Qwen/Qwen3-30B-A3B-MLX-4bit": 262144,
    # ── Qwen 3.5 (MLX) ──
    "mlx-community/Qwen3.5-35B-A3B-4bit":   262144,
    "mlx-community/Qwen3.5-27B-4bit":  262144,
    "mlx-community/Qwen3.5-9B-MLX-4bit": 262144,
    # ── Gemma 4 (MLX) ──
    "unsloth/gemma-4-26b-a4b-it-UD-MLX-4bit": 262144,
    "unsloth/gemma-4-31b-it-UD-MLX-4bit":     262144,
    # ── Mistral (MLX) ──
    "mlx-community/Mistral-Nemo-Instruct-2407-4bit": 131072,
    "mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit": 131072,
}


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def load_yaml(path: str | Path) -> dict:
    """Read a YAML config file and return a plain dict."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


def build_llm(cfg: dict) -> OllamaLLM | MLXLLM:
    """Build an LLM backend from a YAML ``llm:`` section."""
    cfg = dict(cfg)  # don't mutate caller's dict
    backend = cfg.pop("backend", "ollama")
    if backend == "mlx":
        return MLXLLM(**cfg)
    if backend == "ollama":
        model = cfg.get("model", "qwen3:14b")
        if "num_ctx" not in cfg and model in MODELS:
            cfg["num_ctx"] = MODELS[model]
        return OllamaLLM(**cfg)
    raise ValueError(f"Unknown LLM backend: {backend!r}. Use 'ollama' or 'mlx'.")


def build_tts(
    cfg: dict | None, lang: str = "en",
) -> KokoroTTS | ChatterboxTTS:
    """Build a TTS backend from a YAML ``tts:`` section.

    If cfg is None, auto-selects KokoroTTS from the target language.
    """
    if cfg is None:
        return KokoroTTS(lang=lang)

    cfg = dict(cfg)
    backend = cfg.pop("backend", "kokoro")

    if backend == "kokoro":
        if "voices" in cfg:
            cfg["voices"] = tuple(cfg["voices"])
        if "speeds" in cfg:
            cfg["speeds"] = tuple(cfg["speeds"])
        return KokoroTTS(**cfg)

    if backend == "chatterbox":
        if "audio_prompts" in cfg:
            cfg["audio_prompts"] = tuple(cfg["audio_prompts"])
        return ChatterboxTTS(**cfg)

    raise ValueError(
        f"Unknown TTS backend: {backend!r}. Use 'kokoro' or 'chatterbox'."
    )


def context_budget(
    llm: OllamaLLM | MLXLLM, system_prompt_tokens: int = 350,
) -> int:
    """Calculate the per-section token budget from the LLM context window."""
    num_ctx = getattr(llm, "num_ctx", 40960)
    return (num_ctx - system_prompt_tokens) // 2


# ---------------------------------------------------------------------------
# Pipeline-specific loaders
# ---------------------------------------------------------------------------


@dataclass
class AudiobookResult:
    """Everything the audiobook script needs from the YAML config."""

    config: object            # AudiobookConfig
    pdf_parser: str
    max_toc_level: int
    context_budget: int


def load_audiobook_config(path: str | Path) -> AudiobookResult:
    """Load an audiobook YAML config and return typed objects."""
    from audiobook import AudiobookConfig, NarrationConfig

    raw = load_yaml(path)

    source_lang = raw.get("source_lang", "en")
    target_lang = raw.get("target_lang", "en")
    narration = raw.get("narration", {})

    cfg = AudiobookConfig(
        narration=NarrationConfig(
            source_lang=source_lang,
            target_lang=target_lang,
            max_workers=narration.get("max_workers", 1),
        ),
        llm=build_llm(raw.get("llm", {})),
        tts=build_tts(raw.get("tts"), lang=target_lang),
    )

    return AudiobookResult(
        config=cfg,
        pdf_parser=raw.get("pdf_parser", "pymupdf"),
        max_toc_level=raw.get("max_toc_level", 2),
        context_budget=context_budget(cfg.llm),
    )


@dataclass
class PodcastResult:
    """Everything the podcast script needs from the YAML config."""

    config: object            # PodcastConfig
    pdf_parser: str
    max_toc_level: int
    context_budget: int


def load_podcast_config(path: str | Path) -> PodcastResult:
    """Load a podcast YAML config and return typed objects."""
    from podcast import DialogueConfig, PodcastConfig

    raw = load_yaml(path)

    dialogue = raw.get("dialogue", {})
    target_lang = dialogue.get("target_lang", "en")

    cfg = PodcastConfig(
        dialogue=DialogueConfig(
            format=dialogue.get("format", "two_hosts"),
            speaker1_name=dialogue.get("speaker1_name", "Alex"),
            speaker2_name=dialogue.get("speaker2_name", "Sam"),
            source_lang=dialogue.get("source_lang", "en"),
            target_lang=target_lang,
            target_duration_min=dialogue.get("target_duration_min"),
            words_per_minute=dialogue.get("words_per_minute", 150),
            segment_target_words=dialogue.get("segment_target_words", 1200),
        ),
        llm=build_llm(raw.get("llm", {})),
        tts=build_tts(raw.get("tts"), lang=target_lang),
    )

    return PodcastResult(
        config=cfg,
        pdf_parser=raw.get("pdf_parser", "pymupdf"),
        max_toc_level=raw.get("max_toc_level", 1),
        context_budget=context_budget(cfg.llm),
    )
