"""Shared CLI argument parsing and config resolution for pipeline scripts."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .common import MODELS, TeeLogger, resolve_input
from shared.extract import InputSource
from shared.providers import KokoroTTS, OllamaLLM, ollama_preflight


def add_common_args(
    parser: argparse.ArgumentParser,
    *,
    output_prefix: str,
    default_config_display: str,
) -> None:
    """Register CLI arguments shared by both pipeline scripts.

    Adds: ``--input``, ``--output``, ``--config``, ``--source-lang``,
    ``--target-lang``, ``--model``, ``--temperature``, ``--speed``.
    """
    parser.add_argument(
        "--input", "-i", default=None,
        help="Input PDF file or URL (required unless resuming a partial run)",
    )
    parser.add_argument(
        "--output", "-o",
        default=f"output/{output_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="Output directory (pass an existing dir to resume a partial run)",
    )
    parser.add_argument(
        "--config", "-c", default=None,
        help=f"YAML config file (default: {default_config_display})",
    )
    parser.add_argument("--source-lang", default=None, help="Source language code")
    parser.add_argument("--target-lang", default=None, help="Target language code")
    parser.add_argument("--model", default=None, help="Ollama model name (e.g. qwen3:14b)")
    parser.add_argument("--temperature", type=float, default=None, help="LLM temperature")
    parser.add_argument("--speed", type=float, default=None, help="TTS playback speed")


@dataclass
class ResolvedPipeline:
    """Everything both scripts need after config resolution."""

    output_dir: str
    sections_dir: str
    input_source: InputSource | None
    context_budget: int
    max_toc_level: int
    pdf_parser: str


def resolve_pipeline(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    *,
    default_config: Path,
    default_fallback: Path,
    load_config_fn: Callable[[str | Path], Any],
) -> tuple[ResolvedPipeline, Any, Any]:
    """Load config, resolve input, set up directories and logging.

    Returns ``(pipeline, config, loaded)`` where *config* is the
    domain-specific config object (``AudiobookConfig`` / ``PodcastConfig``)
    and *loaded* is the full loader result for accessing extra fields.
    """
    output_dir = args.output

    # Config file resolution: --config > default_config > default_fallback
    config_path = args.config or str(default_config)
    if not os.path.isfile(config_path):
        if args.config:
            parser.error(f"Config file not found: {config_path}")
        config_path = str(default_fallback)
    if not os.path.isfile(config_path):
        parser.error(f"Config file not found: {config_path}")

    loaded = load_config_fn(config_path)
    config = loaded.config

    # --input is required unless resuming (output dir already has sections/)
    if args.input is None:
        sections_dir_check = os.path.join(output_dir, "sections")
        if not os.path.isdir(sections_dir_check):
            parser.error(
                "--input is required (omit only when resuming a partial run with --output)"
            )

    input_source = resolve_input(args.input) if args.input else None

    if input_source and input_source.kind == "pdf" and not os.path.isfile(input_source.path):
        parser.error(f"Input file not found: {input_source.path}")

    # Set up directories and logging
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    sys.stdout = TeeLogger(log_path)
    sys.stderr = TeeLogger(log_path, stream=sys.stderr)

    sections_dir = os.path.join(output_dir, "sections")
    os.makedirs(sections_dir, exist_ok=True)

    pipeline = ResolvedPipeline(
        output_dir=output_dir,
        sections_dir=sections_dir,
        input_source=input_source,
        context_budget=loaded.context_budget,
        max_toc_level=loaded.max_toc_level,
        pdf_parser=loaded.pdf_parser,
    )

    return pipeline, config, loaded


def apply_common_overrides(
    args: argparse.Namespace,
    config: Any,
    *,
    lang_config: Any,
) -> None:
    """Apply shared CLI overrides to config.

    Parameters
    ----------
    args
        Parsed CLI arguments.
    config
        The domain config (``AudiobookConfig`` or ``PodcastConfig``).
    lang_config
        The sub-config with ``source_lang`` / ``target_lang``
        (``config.narration`` or ``config.dialogue``).
    """
    if args.source_lang:
        lang_config.source_lang = args.source_lang
    if args.target_lang:
        lang_config.target_lang = args.target_lang
        if isinstance(config.tts, KokoroTTS):
            config.tts.lang = args.target_lang
            config.tts.voices = None
            config.tts.__post_init__()

    if args.model and isinstance(config.llm, OllamaLLM):
        config.llm.model = args.model
        if args.model in MODELS:
            config.llm.num_ctx = MODELS[args.model]
    if args.temperature is not None:
        config.llm.temperature = args.temperature

    if args.speed is not None and hasattr(config.tts, "speed"):
        config.tts.speed = args.speed


def print_llm_info(config: Any) -> None:
    """Print LLM backend info and run Ollama preflight if applicable."""
    print(f"LLM: {type(config.llm).__name__} / {config.llm.model}")
    if isinstance(config.llm, OllamaLLM):
        print(f"  Ollama URL: {config.llm.url}")
        ollama_preflight(config.llm)
        print("  Ollama connection verified, model available")
