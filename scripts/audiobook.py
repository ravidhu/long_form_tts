#!/usr/bin/env python3
"""Audiobook pipeline — PDF/URL to audio.

PDF → TOC analysis → content page extraction → Markdown → LLM narration → TTS → audio assembly.

Usage:
    uv run python scripts/audiobook.py -i docs/book.pdf
    uv run python scripts/audiobook.py -i https://example.com/article
    uv run python scripts/audiobook.py -i docs/book.pdf -o output/my_run
    uv run python scripts/audiobook.py -o output/my_run   # resume (--input not needed)

Configuration:
    Edit scripts/configs/audiobook.py (narrator voice, language, LLM, TTS)
    and scripts/configs/common.py (PDF_PARSER_BACKEND, MODELS).
"""

import argparse
import logging
import os
import sys
import time

logging.getLogger("phonemizer").setLevel(logging.ERROR)
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import soundfile as sf

# Add src/ to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from configs.audiobook import (  # noqa: E402
    CONTEXT_BUDGET,
    MAX_TOC_LEVEL,
    PDF_PARSER_BACKEND,
    config,
)
from configs.common import TeeLogger, fmt_time, resolve_input  # noqa: E402

from audiobook import (  # noqa: E402
    SAMPLE_RATE,
    adapt_narration_section,
    load_tts_model,
    render_section,
)
from shared.audio_assembler import assemble_audiobook  # noqa: E402
from shared.markdown_parser import Section  # noqa: E402
from shared.pdf_parser import (  # noqa: E402
    pdf_to_markdown,
    resolve_content_pages,
    resolve_content_sections,
)
from shared.providers import OllamaLLM, ollama_preflight  # noqa: E402
from shared.web_parser import fetch_url_content, split_by_headings  # noqa: E402

parser = argparse.ArgumentParser(description="Audiobook pipeline — PDF/URL to audio")
parser.add_argument(
    "--input", "-i", default=None,
    help="Input PDF file or URL (required unless resuming a partial run)",
)
parser.add_argument(
    "--output", "-o",
    default=f"output/audiobook_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    help="Output directory (pass an existing dir to resume a partial run)",
)
parser.add_argument(
    "--source-lang", default=None,
    help=f"Source language code (default: {config.narration.source_lang} from config)",
)
parser.add_argument(
    "--target-lang", default=None,
    help=f"Target language code (default: {config.narration.target_lang} from config)",
)
args = parser.parse_args()
output_dir = args.output

# --input is required unless resuming (output dir already has sections/)
if args.input is None:
    sections_dir_check = os.path.join(output_dir, "sections")
    if not os.path.isdir(sections_dir_check):
        parser.error("--input is required (omit only when resuming a partial run with --output)")

input_source = resolve_input(args.input) if args.input else None

# Override language settings from CLI if provided
if args.source_lang:
    config.narration.source_lang = args.source_lang
if args.target_lang:
    config.narration.target_lang = args.target_lang
    if hasattr(config.tts, "lang"):
        config.tts.lang = args.target_lang

if input_source and input_source.kind == "pdf" and not os.path.isfile(input_source.path):
    parser.error(f"Input file not found: {input_source.path}")

os.makedirs(output_dir, exist_ok=True)
log_path = os.path.join(output_dir, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
sys.stdout = TeeLogger(log_path)

sections_dir = os.path.join(output_dir, "sections")
os.makedirs(sections_dir, exist_ok=True)


def _make_section(title, content_text):
    """Build a Section from title + markdown content."""
    return Section.from_content(title, content_text, language=config.narration.target_lang)


# =============================================================================
# Stage 1–2: Content extraction (PDF branch vs URL branch)
# =============================================================================

print("=" * 60)
narr = config.narration

# --- Print common config info ---
print(f"Output: {output_dir}")
print(f"Source language: {narr.source_lang}, Target language: {narr.target_lang}")
if narr.source_lang != narr.target_lang:
    print(f"  → Cross-language mode: {narr.source_lang} → {narr.target_lang}")
print(f"LLM: {type(config.llm).__name__} / {config.llm.model}")
if isinstance(config.llm, OllamaLLM):
    print(f"  Ollama URL: {config.llm.url}")
    ollama_preflight(config.llm)
    print("  Ollama connection verified, model available")
print(f"TTS: {type(config.tts).__name__}")
print(f"Context budget: {CONTEXT_BUDGET:,} tokens per section")

sections: list[Section] = []

if input_source is None:
    # ----- Resume mode: reload sections from cached files -----
    print("\nResuming from cached sections")
    print("=" * 60)

    for section_path in sorted(Path(sections_dir).glob("*.md")):
        raw = section_path.read_text()
        # Extract title from "# Title\n\n..." header
        if raw.startswith("# "):
            first_nl = raw.index("\n")
            title = raw[2:first_nl]
            content_text = raw[first_nl:].strip()
        else:
            title = section_path.stem
            content_text = raw.strip()
        sections.append(_make_section(title, content_text))
        print(f"  {len(sections)}. {title} (cached)")

    if not sections:
        print("ERROR: No section files found in", sections_dir)
        sys.exit(1)

    print(f"\n{len(sections)} sections loaded from {sections_dir}/")

elif input_source.kind == "url":
    # ----- Webpage URL path -----
    print("\nStage 1: Fetching webpage content")
    print("=" * 60)

    step_t0 = time.time()
    markdown = fetch_url_content(input_source.path)
    print(f"Extracted {len(markdown):,} chars of markdown from {input_source.path}")

    web_sections = split_by_headings(markdown, max_level=MAX_TOC_LEVEL)
    print(f"\nContent sections ({len(web_sections)}):\n")
    for i, ws in enumerate(web_sections):
        print(f"  {i+1}. {ws.title} ({len(ws.content):,} chars)")

    print()
    print("=" * 60)
    print("Stage 2: Writing section files")
    print("=" * 60)

    for i, ws in enumerate(web_sections):
        safe_title = ws.title.replace("/", "-").replace(" ", "_")[:50]
        section_path = os.path.join(sections_dir, f"{i:02d}_{safe_title}.md")

        if os.path.exists(section_path):
            raw = Path(section_path).read_text()
            if raw.startswith(f"# {ws.title}\n\n"):
                content_text = raw[len(f"# {ws.title}\n\n"):]
            else:
                content_text = raw
            sections.append(_make_section(ws.title, content_text))
            print(f"  {i+1}. {ws.title} (cached)")
        else:
            content_text = ws.content.strip()
            sections.append(_make_section(ws.title, content_text))
            with open(section_path, "w") as f:
                f.write(f"# {ws.title}\n\n{content_text}")
            chars = len(content_text)
            tokens_est = chars // 4
            budget_pct = tokens_est / CONTEXT_BUDGET * 100
            print(f"  {i+1}. {ws.title}")
            print(
                f"     {chars:,} chars, ~{tokens_est:,} tokens"
                f" ({budget_pct:.0f}% of budget) → {section_path}"
            )

    step_elapsed = time.time() - step_t0
    print(f"\n{len(sections)} sections saved to {sections_dir}/ ({fmt_time(step_elapsed)} total)")

else:
    # ----- PDF path (local file or downloaded PDF URL) -----
    pdf_file = input_source.path

    print("Stage 1: TOC analysis & section resolution")
    print("=" * 60)

    content = resolve_content_pages(pdf_file)
    print(f"PDF: {content.total_pages} total pages")

    if content.skipped_front:
        print("\nSkipped (front matter):")
        for s in content.skipped_front:
            print(f"  {s}")
    if content.skipped_back:
        print("\nSkipped (back matter):")
        for s in content.skipped_back:
            print(f"  {s}")

    toc_sections = resolve_content_sections(
        pdf_file, max_level=MAX_TOC_LEVEL, max_tokens=CONTEXT_BUDGET
    )

    print(f"\nContent sections ({len(toc_sections)}):\n")
    for i, s in enumerate(toc_sections):
        pages = s.end_page - s.start_page + 1
        indent = "  " * (s.level - 1)
        print(f"  {i+1}. {indent}{s.title} (p.{s.start_page}-{s.end_page}, {pages} pages)")

    # --- Stage 2: Markdown extraction per section ---

    print()
    print("=" * 60)
    print("Stage 2: Markdown extraction per section")
    print("=" * 60)

    step_t0 = time.time()

    for i, toc_sec in enumerate(toc_sections):
        safe_title = toc_sec.title.replace("/", "-").replace(" ", "_")[:50]
        section_path = os.path.join(sections_dir, f"{i:02d}_{safe_title}.md")

        if os.path.exists(section_path):
            raw = Path(section_path).read_text()
            if raw.startswith(f"# {toc_sec.title}\n\n"):
                content_text = raw[len(f"# {toc_sec.title}\n\n"):]
            else:
                content_text = raw
            sections.append(_make_section(toc_sec.title, content_text))
            chars = len(content_text)
            tokens_est = chars // 4
            budget_pct = tokens_est / CONTEXT_BUDGET * 100
            print(f"  {i+1}. {toc_sec.title} (cached)")
            print(
                f"     {chars:,} chars, ~{tokens_est:,} tokens"
                f" ({budget_pct:.0f}% of budget) → {section_path}"
            )
        else:
            t0 = time.time()
            pages = list(range(toc_sec.start_page, toc_sec.end_page + 1))
            md = pdf_to_markdown(pdf_file, backend=PDF_PARSER_BACKEND, pages=pages)

            content_text = md.strip()
            chars = len(content_text)
            tokens_est = chars // 4

            sections.append(_make_section(toc_sec.title, content_text))

            with open(section_path, "w") as f:
                f.write(f"# {toc_sec.title}\n\n{content_text}")

            elapsed = time.time() - t0
            budget_pct = tokens_est / CONTEXT_BUDGET * 100
            print(f"  {i+1}. {toc_sec.title}")
            print(
                f"     {chars:,} chars, ~{tokens_est:,} tokens"
                f" ({budget_pct:.0f}% of budget),"
                f" {fmt_time(elapsed)} → {section_path}"
            )

    step_elapsed = time.time() - step_t0
    print(f"\n{len(sections)} sections saved to {sections_dir}/ ({fmt_time(step_elapsed)} total)")


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
    narration = adapt_narration_section(
        section, llm=config.llm,
        source_lang=narr.source_lang, target_lang=narr.target_lang,
    )
    elapsed = time.time() - t0
    narr_path = os.path.join(narrations_dir, f"{idx:02d}_narration.txt")
    with open(narr_path, "w") as f:
        f.write(narration)
    return idx, section.title, narr_path, len(narration), elapsed


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
            idx, title, path, nchars, elapsed = future.result()
            narrations[idx] = Path(path).read_text()
            print(
                f"  [{idx+1}/{len(sections)}] {title}"
                f" → {path} ({nchars} chars, {fmt_time(elapsed)})"
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
