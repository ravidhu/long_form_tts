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
    cp scripts/configs/podcast.example.yaml scripts/configs/podcast.yaml
    Edit podcast.yaml (dialogue format, speakers, LLM, TTS, pipeline settings).
    Or pass --config path/to/custom.yaml.
"""

import argparse
import json
import logging
import os
import sys
import time

logging.getLogger("phonemizer").setLevel(logging.ERROR)
from pathlib import Path

import soundfile as sf

# Add src/ to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from configs.common import (  # noqa: E402
    PODCAST_CONFIG,
    PODCAST_DEFAULT,
    fmt_time,
)
from configs.cli_arg_parser import (  # noqa: E402
    add_common_args,
    apply_common_overrides,
    print_llm_info,
    resolve_pipeline,
)
from configs.loader import load_podcast_config  # noqa: E402

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
from shared.content_extractor import extract_content  # noqa: E402
from shared.providers import (  # noqa: E402
    KOKORO_VOICE_PRESETS,
    KokoroTTS,
)

# =============================================================================
# CLI setup
# =============================================================================

parser = argparse.ArgumentParser(description="Podcast pipeline — PDF/URL to two-speaker audio")
add_common_args(parser, output_prefix="podcast", default_config_display=str(PODCAST_CONFIG))
# Podcast-specific args
parser.add_argument(
    "--only",
    help="Render only specific segments: intro, outro, or 1-based section numbers. "
         "Comma-separated, ranges supported. Example: --only intro,1-3,outro",
)
parser.add_argument("--voice1", default=None, help="Speaker 1 TTS voice (e.g. bf_emma)")
parser.add_argument("--voice2", default=None, help="Speaker 2 TTS voice (e.g. bm_george)")
parser.add_argument("--format", default=None, choices=["two_hosts", "host_guest"],
                    help="Dialogue format")
parser.add_argument("--voice1name", default=None, help="Speaker 1 name")
parser.add_argument("--voice2name", default=None, help="Speaker 2 name")
parser.add_argument("--duration", type=int, default=None, help="Target duration in minutes")
parser.add_argument("--segment-words", type=int, default=None, help="Words per segment (~8min at 150wpm)")
args = parser.parse_args()

# =============================================================================
# Config resolution and overrides
# =============================================================================

pipeline, config, loaded = resolve_pipeline(
    args, parser,
    default_config=PODCAST_CONFIG,
    default_fallback=PODCAST_DEFAULT,
    load_config_fn=load_podcast_config,
)
apply_common_overrides(args, config, lang_config=config.dialogue)

# Podcast-specific overrides
if (args.voice1 or args.voice2) and hasattr(config.tts, "voices"):
    v1 = args.voice1 or (config.tts.voices[0] if config.tts.voices else "bf_emma")
    v2 = args.voice2 or (config.tts.voices[1] if len(config.tts.voices) > 1 else "bm_george")
    config.tts.voices = (v1, v2)
if args.speed is not None and hasattr(config.tts, "speeds"):
    config.tts.speeds = None  # clear per-voice speeds when global speed is set

if args.format:
    config.dialogue.format = args.format
if args.voice1name:
    config.dialogue.speaker1_name = args.voice1name
if args.voice2name:
    config.dialogue.speaker2_name = args.voice2name
if args.duration is not None:
    config.dialogue.target_duration_min = args.duration
if args.segment_words is not None:
    config.dialogue.segment_target_words = args.segment_words

output_dir = pipeline.output_dir
sections_dir = pipeline.sections_dir

# =============================================================================
# Print config info
# =============================================================================

print("=" * 60)
dlg = config.dialogue
print(f"Output: {output_dir}")
print(f"Format: {dlg.format} ({dlg.speaker1_name} & {dlg.speaker2_name})")
if dlg.target_duration_min:
    print(f"Target duration: {dlg.target_duration_min} min")
else:
    print("Target duration: auto (accumulate from all sections)")
print(f"Language: {dlg.source_lang} → {dlg.target_lang}")
print_llm_info(config)
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


# =============================================================================
# Podcast-specific helpers
# =============================================================================


def _parse_only(value: str, total: int) -> set[int]:
    """Parse --only value into 0-based indices into all_dialogue/labels.

    Mapping: intro -> 0, section N (1-based) -> N, outro -> total-1.
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
# Stage 1-2: Content extraction
# =============================================================================

result = extract_content(
    input_source=pipeline.input_source,
    sections_dir=sections_dir,
    max_toc_level=pipeline.max_toc_level,
    context_budget=pipeline.context_budget,
    pdf_parser=pipeline.pdf_parser,
)
sections_markdown = [(s.title, s.content) for s in result.sections]


# =============================================================================
# Stage 3: Podcast outline generation
# =============================================================================

print()
print("=" * 60)
print("Stage 3: Podcast outline generation")
print("=" * 60)

outline_path = os.path.join(output_dir, "podcast_outline.md")

if os.path.exists(outline_path):
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

        with open(seg_path, "w") as f:
            f.write(result.dialogue)

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
