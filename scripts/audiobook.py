#!/usr/bin/env python3
"""Audiobook pipeline — PDF/URL to audio.

PDF → TOC analysis → content page extraction → Markdown → LLM narration → TTS → audio assembly.

Usage:
    uv run python scripts/audiobook.py -i docs/book.pdf
    uv run python scripts/audiobook.py -i https://example.com/article
    uv run python scripts/audiobook.py -i docs/book.pdf -o output/my_run
    uv run python scripts/audiobook.py -o output/my_run   # resume (--input not needed)

Configuration:
    cp scripts/configs/audiobook.example.yaml scripts/configs/audiobook.yaml
    Edit audiobook.yaml (LLM backend, TTS voice, language, pipeline settings).
    Or pass --config path/to/custom.yaml.
"""

import argparse
import logging
import os
import re
import sys
import time

logging.getLogger("phonemizer").setLevel(logging.ERROR)
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import soundfile as sf

# Add src/ to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from configs.common import (  # noqa: E402
    AUDIOBOOK_CONFIG,
    AUDIOBOOK_DEFAULT,
    fmt_time,
)
from configs.cli_arg_parser import (  # noqa: E402
    add_common_args,
    apply_common_overrides,
    print_llm_info,
    resolve_pipeline,
)
from configs.loader import load_audiobook_config  # noqa: E402

from audiobook import (  # noqa: E402
    SAMPLE_RATE,
    adapt_narration_section,
    load_tts_model,
    render_section,
)
from shared.audio_assembler import assemble_audiobook  # noqa: E402
from shared.content_extractor import extract_content  # noqa: E402
from shared.markdown_parser import Section  # noqa: E402

# =============================================================================
# CLI setup
# =============================================================================

parser = argparse.ArgumentParser(description="Audiobook pipeline — PDF/URL to audio")
add_common_args(parser, output_prefix="audiobook", default_config_display=str(AUDIOBOOK_CONFIG))
# Audiobook-specific args
parser.add_argument("--voice", default=None, help="TTS voice name (e.g. af_heart)")
parser.add_argument("--max-workers", type=int, default=None, help="Parallel LLM requests")
args = parser.parse_args()

# =============================================================================
# Config resolution and overrides
# =============================================================================

pipeline, config, loaded = resolve_pipeline(
    args, parser,
    default_config=AUDIOBOOK_CONFIG,
    default_fallback=AUDIOBOOK_DEFAULT,
    load_config_fn=load_audiobook_config,
)
apply_common_overrides(args, config, lang_config=config.narration)

# Audiobook-specific overrides
if args.voice and hasattr(config.tts, "voices"):
    config.tts.voices = (args.voice,)
if args.max_workers is not None:
    config.narration.max_workers = args.max_workers

output_dir = pipeline.output_dir
sections_dir = pipeline.sections_dir

# =============================================================================
# Print config info
# =============================================================================

print("=" * 60)
narr = config.narration
print(f"Output: {output_dir}")
print(f"Source language: {narr.source_lang}, Target language: {narr.target_lang}")
if narr.source_lang != narr.target_lang:
    print(f"  → Cross-language mode: {narr.source_lang} → {narr.target_lang}")
print_llm_info(config)
print(f"TTS: {type(config.tts).__name__}")
print(f"Context budget: {pipeline.context_budget:,} tokens per section")


# =============================================================================
# Audiobook-specific helpers
# =============================================================================


def _title_patterns(title: str) -> list[re.Pattern[str]]:
    """Build regex patterns that match a section title in extracted markdown.

    Handles numbered headings (``**3.1** **Survey Design**``),
    markdown headings (``## 3.1 Survey Design``), and plain bold titles.
    """
    num_match = re.match(r"^([\d.]+)\s+(.*)", title)
    if num_match:
        sec_num = num_match.group(1)
        words = num_match.group(2).split()[:4]
    else:
        sec_num = None
        words = title.split()[:4]

    title_start = r"\s+".join(re.escape(w) for w in words)

    patterns: list[re.Pattern[str]] = []
    if sec_num:
        esc_num = re.escape(sec_num)
        patterns.append(re.compile(
            rf"^\**{esc_num}\**\s+\**{title_start}", re.MULTILINE
        ))
        patterns.append(re.compile(
            rf"^#{{1,6}}\s+{esc_num}\s+{title_start}", re.MULTILINE
        ))
    patterns.append(re.compile(rf"^#{{1,6}}\s+\**{title_start}", re.MULTILINE))
    patterns.append(re.compile(rf"^\**{title_start}\**\s*$", re.MULTILINE))
    return patterns


def _find_title(md: str, title: str) -> int | None:
    """Return the character offset where *title* first appears, or ``None``."""
    earliest: int | None = None
    for pat in _title_patterns(title):
        m = pat.search(md)
        if m and (earliest is None or m.start() < earliest):
            earliest = m.start()
    return earliest


def _trim_shared_page(md: str, current_title: str, next_title: str | None) -> str:
    """Trim extracted markdown so only *current_title*'s content remains.

    When consecutive TOC entries share the same page(s), pdf_to_markdown
    extracts the full page for each section.  This function:

    1. **Begin-trim** — finds *current_title*'s heading and discards
       everything before it (content belonging to earlier sections on
       the same start page).
    2. **End-trim** — finds *next_title*'s heading and discards everything
       from that point on (content belonging to later sections on the
       same end page).
    """
    # ── Begin-trim: discard content before this section's heading ──
    pos = _find_title(md, current_title)
    if pos is not None and pos > 0:
        # Skip past the heading line (and any continuation bold lines)
        nl = md.find("\n", pos)
        if nl == -1:
            md = ""
        else:
            rest = md[nl + 1:]
            # Multi-line bold headings: skip continuation lines starting with **
            while rest.startswith("**"):
                next_nl = rest.find("\n")
                if next_nl == -1:
                    rest = ""
                    break
                rest = rest[next_nl + 1:]
            md = rest.lstrip("\n")

    # ── End-trim: discard content after the next section's heading ──
    if next_title is not None:
        pos = _find_title(md, next_title)
        if pos is not None:
            md = md[:pos]

    return md.strip()


# =============================================================================
# Stage 1–2: Content extraction
# =============================================================================

result = extract_content(
    input_source=pipeline.input_source,
    sections_dir=sections_dir,
    max_toc_level=pipeline.max_toc_level,
    context_budget=pipeline.context_budget,
    pdf_parser=pipeline.pdf_parser,
    trim_overlap=_trim_shared_page,
)
sections = [
    Section.from_content(s.title, s.content, language=narr.target_lang)
    for s in result.sections
]


# =============================================================================
# Stage 3: LLM narration adaptation (parallel)
# =============================================================================

print()
print("=" * 60)
print("Stage 3: LLM narration adaptation")
print("=" * 60)

narrations_dir = os.path.join(output_dir, "narrations")
os.makedirs(narrations_dir, exist_ok=True)

narr = config.narration


def adapt_and_save(idx_section):
    idx, section = idx_section
    t0 = time.time()
    narration, llm_calls = adapt_narration_section(
        section, llm=config.llm,
        source_lang=narr.source_lang, target_lang=narr.target_lang,
    )
    elapsed = time.time() - t0
    narr_path = os.path.join(narrations_dir, f"{idx:02d}_narration.txt")
    with open(narr_path, "w") as f:
        f.write(narration)
    return idx, section.title, narr_path, len(narration), elapsed, llm_calls


narrations = [None] * len(sections)

# Pre-fill from cached narration files
to_adapt = []
for i in range(len(sections)):
    narr_path = os.path.join(narrations_dir, f"{i:02d}_narration.txt")
    if os.path.exists(narr_path):
        narrations[i] = Path(narr_path).read_text()
        print(f"  [{i+1}/{len(sections)}] {sections[i].title} (cached, {len(narrations[i])} chars)")
    else:
        to_adapt.append(i)

print(
    f"\nAdapting {len(sections)} sections with"
    f" {type(config.llm).__name__} / {config.llm.model}"
    f" ({narr.max_workers} workers)..."
)
if narr.source_lang != narr.target_lang:
    print(f"  Cross-language: {narr.source_lang} → {narr.target_lang}")
if to_adapt:
    print(f"  {len(sections) - len(to_adapt)} cached, {len(to_adapt)} to generate")
else:
    print("  All narrations cached — nothing to generate")
print()

total_t0 = time.time()
if to_adapt:
    with ThreadPoolExecutor(max_workers=narr.max_workers) as pool:
        futures = {pool.submit(adapt_and_save, (i, sections[i])): i for i in to_adapt}
        for future in as_completed(futures):
            idx, title, path, nchars, elapsed, llm_calls = future.result()
            narrations[idx] = Path(path).read_text()
            mode = f"{llm_calls} LLM calls" if llm_calls else "rule-based"
            print(
                f"  [{idx+1}/{len(sections)}] {title}"
                f" → {path} ({nchars} chars, {fmt_time(elapsed)}, {mode})"
            )

total_elapsed = time.time() - total_t0
print(
    f"\nAll {len(narrations)} narration scripts saved to"
    f" {narrations_dir}/ ({fmt_time(total_elapsed)} total)"
)


# =============================================================================
# Stage 4: TTS rendering (sequential)
# =============================================================================

print()
print("=" * 60)
print("Stage 4: TTS rendering")
print("=" * 60)

audio_dir = os.path.join(output_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)

# Check which sections need rendering
to_render = []
for i in range(len(sections)):
    audio_path = os.path.join(audio_dir, f"{i:02d}_audio.wav")
    if not os.path.exists(audio_path):
        to_render.append(i)

# Only load the TTS model if there's work to do
tts_model = None
if to_render:
    print(f"Loading {type(config.tts).__name__} model...")
    t0 = time.time()
    tts_model = load_tts_model(config.tts)
    print(f"Model loaded ({fmt_time(time.time() - t0)}).")
    print(f"  {len(sections) - len(to_render)} cached, {len(to_render)} to render\n")
else:
    print("All audio cached — nothing to render\n")

# TTS is GPU/Metal-bound — sequential rendering per section,
# but each section's pause-split chunks are processed in one pass.
audio_segments = []
step_t0 = time.time()

for i, (section, narration) in enumerate(zip(sections, narrations, strict=False)):
    audio_path = os.path.join(audio_dir, f"{i:02d}_audio.wav")

    if os.path.exists(audio_path):
        audio, _ = sf.read(audio_path, dtype="float32")
        audio_segments.append(audio)
        audio_dur = fmt_time(len(audio) / SAMPLE_RATE)
        print(f"  {i+1}/{len(sections)}: {section.title} (cached, {audio_dur} audio)")
    else:
        print(f"  {i+1}/{len(sections)}: {section.title}...", end=" ", flush=True)
        t0 = time.time()
        audio = render_section(narration, tts=config.tts, model=tts_model)
        elapsed = time.time() - t0
        audio_segments.append(audio)

        sf.write(audio_path, audio, SAMPLE_RATE)
        print(f"saved ({fmt_time(len(audio)/SAMPLE_RATE)} audio, {fmt_time(elapsed)} elapsed)")

step_elapsed = time.time() - step_t0
total_audio = sum(len(a) for a in audio_segments) / SAMPLE_RATE
print(
    f"\nRendered {len(audio_segments)} sections to {audio_dir}/"
    f" ({fmt_time(total_audio)} audio, {fmt_time(step_elapsed)} total)"
)


# =============================================================================
# Stage 5: Audio assembly
# =============================================================================

print()
print("=" * 60)
print("Stage 5: Audio assembly")
print("=" * 60)

final_output = os.path.join(output_dir, "audiobook.wav")

t0 = time.time()
assemble_audiobook(
    audio_segments=audio_segments,
    output_path=final_output,
    sample_rate=SAMPLE_RATE,
    inter_section_pause=2.0,
)
elapsed = time.time() - t0
print(f"Assembly completed in {fmt_time(elapsed)}")
print(f"\nAudiobook saved to {final_output}")


# =============================================================================
# Cleanup: release TTS model before Python's GC runs
# =============================================================================
# MLX/Metal GPU resources segfault if destroyed in arbitrary GC order at exit.
# Explicitly deleting the model and clearing the MLX cache prevents this.

del tts_model
del audio_segments

try:
    import mlx.core as mx
    mx.metal.clear_cache()
except Exception:
    pass
