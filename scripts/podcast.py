#!/usr/bin/env python3
"""Podcast pipeline — PDF/URL to two-speaker conversational audio.

PDF/URL → TOC analysis → content extraction → LLM outline → segment-by-segment
dialogue → multi-speaker TTS → audio assembly.

Generates 45-90 min two-speaker conversational audio from large PDFs or webpages.

Usage:
    uv run python scripts/podcast.py -i docs/book.pdf
    uv run python scripts/podcast.py -i https://example.com/article
    uv run python scripts/podcast.py -i docs/book.pdf -o output/my_run
    uv run python scripts/podcast.py -o output/my_run   # resume (--input not needed)

Configuration:
    Edit scripts/configs/podcast.py (dialogue format, speakers, LLM, TTS)
    and scripts/configs/common.py (PDF_PARSER_BACKEND, MODELS).
"""

import argparse
import json
import logging
import os
import sys
import time

logging.getLogger("phonemizer").setLevel(logging.ERROR)
from datetime import datetime
from pathlib import Path

import soundfile as sf

# Add src/ to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from configs.common import TeeLogger, fmt_time, resolve_input  # noqa: E402
from configs.podcast import (  # noqa: E402
    CONTEXT_BUDGET,
    MAX_TOC_LEVEL,
    PDF_PARSER_BACKEND,
    config,
)

from podcast import (  # noqa: E402
    PodcastOutline,
    generate_dialogue_segment,
    generate_intro_outro,
    generate_outline,
    get_sample_rate,
    load_tts_model,
    render_dialogue,
)
from shared.audio_assembler import assemble_audiobook  # noqa: E402
from shared.pdf_parser import (  # noqa: E402
    pdf_to_markdown,
    resolve_content_pages,
    resolve_content_sections,
)
from shared.providers import (  # noqa: E402
    KOKORO_VOICE_PRESETS,
    KokoroTTS,
    OllamaLLM,
    ollama_preflight,
)
from shared.web_parser import fetch_url_content, split_by_headings  # noqa: E402

parser = argparse.ArgumentParser(description="Podcast pipeline — PDF/URL to two-speaker audio")
parser.add_argument(
    "--input", "-i", default=None,
    help="Input PDF file or URL (required unless resuming a partial run)",
)
parser.add_argument(
    "--output", "-o",
    default=f"output/podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    help="Output directory (pass an existing dir to resume a partial run)",
)
parser.add_argument(
    "--source-lang", default=None,
    help=f"Source language code (default: {config.dialogue.source_lang} from config)",
)
parser.add_argument(
    "--target-lang", default=None,
    help=f"Target language code (default: {config.dialogue.target_lang} from config)",
)
parser.add_argument(
    "--only",
    help="Render only specific segments: intro, outro, or 1-based section numbers. "
         "Comma-separated, ranges supported. Example: --only intro,1-3,outro",
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
    config.dialogue.source_lang = args.source_lang
if args.target_lang:
    config.dialogue.target_lang = args.target_lang
    if hasattr(config.tts, "lang"):
        config.tts.lang = args.target_lang

if input_source and input_source.kind == "pdf" and not os.path.isfile(input_source.path):
    parser.error(f"Input file not found: {input_source.path}")

os.makedirs(output_dir, exist_ok=True)
log_path = os.path.join(output_dir, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
sys.stdout = TeeLogger(log_path)

sections_dir = os.path.join(output_dir, "sections")
os.makedirs(sections_dir, exist_ok=True)


def _parse_only(value: str, total: int) -> set[int]:
    """Parse --only value into 0-based indices into all_dialogue/labels.

    Mapping: intro → 0, section N (1-based) → N, outro → total-1.
    """
    indices = set()
    for part in value.split(","):
        part = part.strip().lower()
        if part == "intro":
            indices.add(0)
        elif part == "outro":
            indices.add(total - 1)
        elif "-" in part:
            a, b = part.split("-", 1)
            indices.update(range(int(a), int(b) + 1))
        else:
            indices.add(int(part))
    return {i for i in indices if 0 <= i < total}


# =============================================================================
# Stage 1–2: Content extraction (PDF branch vs URL branch)
# =============================================================================

print("=" * 60)

# --- Print common config info ---
dlg = config.dialogue
print(f"Output: {output_dir}")
print(f"Format: {dlg.format} ({dlg.speaker1_name} & {dlg.speaker2_name})")
if dlg.target_duration_min:
    print(f"Target duration: {dlg.target_duration_min} min")
else:
    print("Target duration: auto (accumulate from all sections)")
print(f"Language: {dlg.source_lang} → {dlg.target_lang}")
print(f"LLM: {type(config.llm).__name__} / {config.llm.model}")
if isinstance(config.llm, OllamaLLM):
    print(f"  Ollama URL: {config.llm.url}")
    ollama_preflight(config.llm)
    print("  Ollama connection verified, model available")
print(f"TTS: {type(config.tts).__name__}")
if isinstance(config.tts, KokoroTTS):
    print(f"  Lang: {config.tts.lang}, Voices: {config.tts.voices}")
    # Validate voice prefixes vs target language
    _LANG_PREFIXES = {
        lang: {v[0] for v in voices}
        for lang, voices in KOKORO_VOICE_PRESETS.items()
    }
    _LANG_PREFIXES["en"] = {"a", "b"}  # American + British
    expected = _LANG_PREFIXES.get(dlg.target_lang)
    if expected:
        bad = [v for v in config.tts.voices if v[0] not in expected]
        if bad:
            parser.error(
                f"Voice/language mismatch: {bad} incompatible with "
                f"target_lang='{dlg.target_lang}' (expected prefix: {expected}). "
                f"Kokoro would phonemize {dlg.target_lang} text with wrong rules."
            )

sections_markdown: list[tuple[str, str]] = []  # list of (title, content) tuples

if input_source is None:
    # ----- Resume mode: reload sections from cached files -----
    print("\nResuming from cached sections")
    print("=" * 60)

    for section_path in sorted(Path(sections_dir).glob("*.md")):
        raw = section_path.read_text()
        if raw.startswith("# "):
            first_nl = raw.index("\n")
            title = raw[2:first_nl]
            content_text = raw[first_nl:].strip()
        else:
            title = section_path.stem
            content_text = raw.strip()
        sections_markdown.append((title, content_text))
        print(f"  {len(sections_markdown)}. {title} (cached)")

    if not sections_markdown:
        print("ERROR: No section files found in", sections_dir)
        sys.exit(1)

    print(f"\n{len(sections_markdown)} sections loaded from {sections_dir}/")

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
            sections_markdown.append((ws.title, content_text))
            print(f"  {i+1}. {ws.title} (cached)")
        else:
            content_text = ws.content.strip()
            sections_markdown.append((ws.title, content_text))
            with open(section_path, "w") as f:
                f.write(f"# {ws.title}\n\n{content_text}")
            chars = len(content_text)
            print(f"  {i+1}. {ws.title} ({chars:,} chars) → {section_path}")

    step_elapsed = time.time() - step_t0
    print(
        f"\n{len(sections_markdown)} sections saved to"
        f" {sections_dir}/ ({fmt_time(step_elapsed)} total)"
    )

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
            sections_markdown.append((toc_sec.title, content_text))
            chars = len(content_text)
            print(f"  {i+1}. {toc_sec.title} (cached, {chars:,} chars)")
        else:
            t0 = time.time()
            pages = list(range(toc_sec.start_page, toc_sec.end_page + 1))
            md = pdf_to_markdown(pdf_file, backend=PDF_PARSER_BACKEND, pages=pages)
            content_text = md.strip()
            sections_markdown.append((toc_sec.title, content_text))

            with open(section_path, "w") as f:
                f.write(f"# {toc_sec.title}\n\n{content_text}")

            elapsed = time.time() - t0
            chars = len(content_text)
            print(f"  {i+1}. {toc_sec.title} ({chars:,} chars, {fmt_time(elapsed)})")

    step_elapsed = time.time() - step_t0
    print(
        f"\n{len(sections_markdown)} sections saved to"
        f" {sections_dir}/ ({fmt_time(step_elapsed)} total)"
    )


# =============================================================================
# Stage 3: Podcast outline generation
# =============================================================================

print()
print("=" * 60)
print("Stage 3: Podcast outline generation")
print("=" * 60)

os.makedirs(output_dir, exist_ok=True)

outline_path = os.path.join(output_dir, "podcast_outline.md")

if os.path.exists(outline_path):
    # Cache hit — reconstruct PodcastOutline from saved file
    raw = Path(outline_path).read_text()
    title = ""
    for line in raw.splitlines():
        if line.strip().lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            break
    outline = PodcastOutline(raw_text=raw, title=title)
    print(f"Outline loaded from cache: {outline_path}")
    print(f"Episode title: {outline.title}")
else:
    print(f"Generating podcast outline from {len(sections_markdown)} sections...")
    if config.dialogue.target_duration_min:
        print(f"Target duration: {config.dialogue.target_duration_min} min\n")
    else:
        print("Duration: auto (cover all sections)\n")

    t0 = time.time()
    outline = generate_outline(sections_markdown, config)
    elapsed = time.time() - t0

    with open(outline_path, "w") as f:
        f.write(outline.raw_text)

    print(f"Outline saved to {outline_path} ({fmt_time(elapsed)})")
    print(f"Episode title: {outline.title}")

print("\n--- Outline preview ---")
print(outline.raw_text[:2000])
if len(outline.raw_text) > 2000:
    print("\n... (truncated — see full outline in saved file)")


# =============================================================================
# Stage 4: Sequential dialogue generation (segment by segment)
# =============================================================================

print()
print("=" * 60)
print("Stage 4: Dialogue generation")
print("=" * 60)

dialogue_dir = os.path.join(output_dir, "dialogue")
os.makedirs(dialogue_dir, exist_ok=True)

rolling_summary = ""
covered_topics = []
dialogue_segments = []  # list of dialogue text strings

dlg = config.dialogue
print(f"Generating dialogue for {len(sections_markdown)} sections (sequential)...")
print(f"Target: ~{dlg.segment_target_words} words/segment "
      f"(~{dlg.segment_target_words // dlg.words_per_minute} min each)\n")

step_t0 = time.time()

for i, (title, content_text) in enumerate(sections_markdown):
    safe_title = title.replace("/", "-").replace(" ", "_")[:50]
    seg_path = os.path.join(dialogue_dir, f"{i+1:02d}_{safe_title}.txt")
    state_path = os.path.join(dialogue_dir, f"{i+1:02d}_state.json")

    if os.path.exists(seg_path) and os.path.exists(state_path):
        # Cache hit — load dialogue and rolling state
        dialogue = Path(seg_path).read_text()
        state = json.loads(Path(state_path).read_text())
        dialogue_segments.append(dialogue)
        rolling_summary = state["rolling_summary"]
        covered_topics = state["covered_topics"]

        word_count = len(dialogue.split())
        est_minutes = word_count / dlg.words_per_minute
        print(
            f"  [{i+1}/{len(sections_markdown)}] {title}"
            f" (cached, {word_count} words, ~{est_minutes:.1f} min)"
        )
    else:
        t0 = time.time()
        print(f"  [{i+1}/{len(sections_markdown)}] {title}...", end=" ", flush=True)

        result = generate_dialogue_segment(
            section_content=content_text,
            section_title=title,
            outline=outline,
            segment_index=i,
            rolling_summary=rolling_summary,
            covered_topics=covered_topics,
            config=config,
        )

        dialogue_segments.append(result.dialogue)
        rolling_summary = result.updated_summary
        covered_topics = result.covered_topics

        # Save segment dialogue
        with open(seg_path, "w") as f:
            f.write(result.dialogue)

        # Persist rolling state for resume
        with open(state_path, "w") as f:
            json.dump({"rolling_summary": rolling_summary, "covered_topics": covered_topics}, f)

        elapsed = time.time() - t0
        word_count = len(result.dialogue.split())
        est_minutes = word_count / dlg.words_per_minute
        print(f"{word_count} words (~{est_minutes:.1f} min), {fmt_time(elapsed)}")

step_elapsed = time.time() - step_t0
total_words = sum(len(d.split()) for d in dialogue_segments)
total_est_min = total_words / dlg.words_per_minute
print(f"\nDialogue generation complete ({fmt_time(step_elapsed)} total)")
print(f"Total: {total_words:,} words, estimated {total_est_min:.0f} min podcast")
print(f"Topics covered: {len(covered_topics)}")


# =============================================================================
# Stage 5: Intro & outro generation
# =============================================================================

print()
print("=" * 60)
print("Stage 5: Intro & outro generation")
print("=" * 60)

intro_path = os.path.join(dialogue_dir, "00_intro.txt")
outro_path = os.path.join(dialogue_dir, "99_outro.txt")

if os.path.exists(intro_path) and os.path.exists(outro_path):
    # Cache hit
    intro = Path(intro_path).read_text()
    outro = Path(outro_path).read_text()
    print("Intro and outro loaded from cache.")
else:
    print("Generating intro and outro...")
    t0 = time.time()

    intro, outro = generate_intro_outro(outline, covered_topics, config)
    elapsed = time.time() - t0

    with open(intro_path, "w") as f:
        f.write(intro)
    with open(outro_path, "w") as f:
        f.write(outro)
    print(f"Intro & outro generated ({fmt_time(elapsed)})")

# Insert intro at front, outro at end
all_dialogue = [intro] + dialogue_segments + [outro]

dlg = config.dialogue
intro_words = len(intro.split())
outro_words = len(outro.split())
total_words = sum(len(d.split()) for d in all_dialogue)
total_est_min = total_words / dlg.words_per_minute

print(f"Intro: {intro_words} words → {intro_path}")
print(f"Outro: {outro_words} words → {outro_path}")
print(f"Total with intro/outro: {total_words:,} words, ~{total_est_min:.0f} min")


# =============================================================================
# Stage 6: Multi-speaker TTS rendering (sequential)
# =============================================================================

print()
print("=" * 60)
print("Stage 6: TTS rendering")
print("=" * 60)

sample_rate = get_sample_rate(config.tts)

audio_dir = os.path.join(output_dir, "audio")
os.makedirs(audio_dir, exist_ok=True)

labels = ["intro"] + [s[0] for s in sections_markdown] + ["outro"]

# Resolve --only filter
render_set = _parse_only(args.only, len(all_dialogue)) if args.only else None
if render_set is not None:
    selected = [labels[i] for i in sorted(render_set)]
    print(f"--only: rendering {len(render_set)} of {len(labels)} segments: {', '.join(selected)}")

# Check which segments need rendering
to_render = []
for i, label in enumerate(labels):
    if render_set is not None and i not in render_set:
        continue
    safe_label = label.replace("/", "-").replace(" ", "_")[:50]
    audio_path = os.path.join(audio_dir, f"{i:02d}_{safe_label}.wav")
    if not os.path.exists(audio_path):
        to_render.append(i)

# Only load the TTS model if there's work to do
tts_model = None
if to_render:
    print(f"Loading TTS model ({type(config.tts).__name__})...")
    t0 = time.time()
    tts_model = load_tts_model(tts=config.tts)
    print(f"Model loaded ({fmt_time(time.time() - t0)}).")
    print(f"  {len(labels) - len(to_render)} cached/skipped, {len(to_render)} to render\n")
else:
    print("All audio cached — nothing to render\n")

# TTS is GPU/Metal-bound — sequential rendering
audio_segments = []
step_t0 = time.time()

for i, (dialogue, label) in enumerate(zip(all_dialogue, labels, strict=False)):
    safe_label = label.replace("/", "-").replace(" ", "_")[:50]
    audio_path = os.path.join(audio_dir, f"{i:02d}_{safe_label}.wav")

    # --only filtering: skip segments not in render_set
    if render_set is not None and i not in render_set:
        if os.path.exists(audio_path):
            audio, _ = sf.read(audio_path, dtype="float32")
            audio_segments.append(audio)
            audio_dur = len(audio) / sample_rate
            print(f"  {i+1}/{len(all_dialogue)}: {label} (skipped, cached {fmt_time(audio_dur)})")
        else:
            print(f"  {i+1}/{len(all_dialogue)}: {label} (skipped)")
        continue

    if os.path.exists(audio_path):
        audio, _ = sf.read(audio_path, dtype="float32")
        audio_segments.append(audio)
        audio_dur = len(audio) / sample_rate
        print(f"  {i+1}/{len(all_dialogue)}: {label} (cached, {fmt_time(audio_dur)} audio)")
    else:
        print(f"  {i+1}/{len(all_dialogue)}: {label}...", end=" ", flush=True)
        t0 = time.time()

        audio = render_dialogue(dialogue, tts=config.tts, model=tts_model)
        audio_segments.append(audio)
        elapsed = time.time() - t0

        sf.write(audio_path, audio, sample_rate)
        audio_dur = len(audio) / sample_rate
        print(f"{fmt_time(audio_dur)} audio, {fmt_time(elapsed)} elapsed")

step_elapsed = time.time() - step_t0
total_audio = sum(len(a) for a in audio_segments) / sample_rate
print(
    f"\nRendered {len(audio_segments)} segments"
    f" ({fmt_time(total_audio)} audio, {fmt_time(step_elapsed)} total)"
)


# =============================================================================
# Stage 7: Audio assembly
# =============================================================================

print()
print("=" * 60)
print("Stage 7: Audio assembly")
print("=" * 60)

output_name = "podcast_partial.wav" if render_set is not None else "podcast.wav"
final_output = os.path.join(output_dir, output_name)

if not audio_segments:
    print("No audio segments to assemble — skipping.")
else:
    t0 = time.time()
    assemble_audiobook(
        audio_segments=audio_segments,
        output_path=final_output,
        sample_rate=sample_rate,
        inter_section_pause=1.5,  # shorter pause than audiobook
    )
    elapsed = time.time() - t0
    print(f"Assembly completed in {fmt_time(elapsed)}")
    print(f"\nPodcast saved to {final_output}")
