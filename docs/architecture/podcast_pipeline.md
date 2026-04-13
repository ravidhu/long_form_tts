# Podcast Pipeline (7 stages)

Each stage is **resumable** — if a run is interrupted, re-running with the same `--output` directory skips completed stages automatically (cached files are detected on disk).

```mermaid
flowchart LR
    S1[1. Input\nResolution] --> S2[2. Markdown\nExtraction]
    S2 --> S3[3. Outline\nGeneration]
    S3 --> S4[4. Dialogue\nGeneration]
    S4 --> S5[5. Intro /\nOutro]
    S5 --> S6[6. Multi-Speaker\nTTS]
    S6 --> S7[7. Audio\nAssembly]

    style S1 fill:#e8f4fd
    style S2 fill:#e8f4fd
    style S3 fill:#fff3cd
    style S4 fill:#fff3cd
    style S5 fill:#fff3cd
    style S6 fill:#d4edda
    style S7 fill:#f8d7da
```

> Stages are color-coded: blue = extraction, yellow = LLM, green = TTS, red = assembly. Each stage caches its output — re-running skips completed stages.

```
uv run python scripts/podcast.py -i book.pdf -o output/my_podcast
```

### Partial rendering with `--only`

The `--only` flag lets you re-render specific segments without re-running the full pipeline. See [CLI Reference — `--only`](../reference/cli_reference.md#the---only-flag) for full syntax and examples.

---

### Stages 1-2: Content Extraction

Input resolution (PDF, URL, web page), TOC analysis, and markdown extraction. These stages are shared with the audiobook pipeline — see [Content Extraction](content_extraction.md) for the full walkthrough.

The podcast uses `max_toc_level: 1` (part-level) because dialogue is generated sequentially with a rolling summary — fewer, larger sections give each conversation segment more material to discuss.

---

### Language propagation

Setting `source_lang` and `target_lang` in `DialogueConfig` is all you need — the pipeline propagates them automatically:

1. **LLM prompts**: A `language_instruction(source_lang, target_lang)` is appended to every LLM call (outline, dialogue, intro/outro, rolling summary). When `source_lang == target_lang == "en"`, no instruction is added. Otherwise the LLM is told to write in the target language, translating if needed.
2. **TTS voice auto-selection**: If you omit the `tts=` parameter, `PodcastConfig` creates `KokoroTTS(lang=target_lang)` automatically, picking the correct voice preset for that language.

> **Caveat**: If you set `tts=` explicitly with specific voices, make sure they match the target language. For example, `target_lang="fr"` with `KokoroTTS(voices=("bf_emma", "bm_george"))` would generate French dialogue but read it with British English voices.

See [Translation](../backends/translation.md) for cross-language workflows and examples.

---

### Stage 3: Podcast Outline Generation

**What it does**: Produces a structured episode plan from all sections in a single LLM call.

**How it works**:
1. All section titles and content previews (~2000 chars each) are sent to the LLM with the [outline system prompt](../../src/podcast/prompts/outline_system.md)
2. The LLM produces a structured outline with:
   - Episode title
   - Per-segment topics, hooks, and talking points
   - Duration estimates per segment
3. If `target_duration_min` is set, the outline respects the time budget
4. The outline is saved as `podcast_outline.md` and stays constant throughout dialogue generation

**Output**: `podcast_outline.md`

**Cache**: If the outline file exists, it's loaded from disk.

**Key config**: [`target_duration_min`](../reference/api_reference.md#config-classes-1), [`llm`](../reference/api_reference.md#llm-backends)

---

### Stage 4: Dialogue Generation

**What it does**: Generates two-speaker conversational dialogue for each section, sequentially.

```mermaid
flowchart LR
    subgraph Context["Constant context"]
        O[Outline]
    end

    O --> Seg1[Section 1]
    Seg1 -->|summary + topics| Seg2[Section 2]
    Seg2 -->|summary + topics| Seg3[Section 3]
    Seg3 -->|summary + topics| SegN[Section N]
```

**How it works**:
1. Sections are processed **one at a time** in order (not parallelizable — each depends on the previous)
2. For each section, the LLM receives a [dialogue prompt](../../src/podcast/prompts/) ([two hosts](../../src/podcast/prompts/dialogue_two_hosts.md) or [host+guest](../../src/podcast/prompts/dialogue_host_guest.md)) along with:
   - The global outline (constant context)
   - The section's markdown content
   - A rolling summary of everything discussed so far (~500 words, Chain-of-Density style)
   - A list of all topics already covered (prevents repetition)
3. The LLM produces dialogue with `[S1]`/`[S2]` speaker tags
4. After each segment, the LLM also produces an updated rolling summary and updated topic list
5. Both the dialogue and the rolling state (`rolling_summary` + `covered_topics`) are saved to disk

**Output**: `dialogue/01_Chapter_1.txt`, `dialogue/01_state.json`, etc.

**Cache**: If both the dialogue `.txt` and `_state.json` exist for a segment, it's loaded from disk. The rolling summary is restored so subsequent segments can resume correctly.

**Why `MAX_TOC_LEVEL=1`**: The podcast defaults to part-level granularity because dialogue is generated sequentially with a rolling summary — fewer, larger sections give each conversation segment more material to discuss, and auto-subdivision still splits oversized parts when they exceed the context budget.

**Key config**: [`segment_target_words`, `words_per_minute`, `format`, `speaker1_name`, `speaker2_name`](../reference/api_reference.md#config-classes-1)

---

### Stage 5: Intro & Outro Generation

**What it does**: Generates opening and closing dialogue with full awareness of all topics covered.

**How it works**:
1. Generated **after** all content segments, so the LLM knows what was discussed
2. The LLM receives the outline and the complete list of covered topics
3. The [intro prompt](../../src/podcast/prompts/intro.md) hooks the listener and previews the episode
4. The [outro prompt](../../src/podcast/prompts/outro.md) summarizes key takeaways and wraps up

**Output**: `dialogue/00_intro.txt`, `dialogue/99_outro.txt`

**Cache**: If both files exist, they're loaded from disk.

---

### Stage 6: Multi-Speaker TTS Rendering

**What it does**: Converts `[S1]`/`[S2]`-tagged dialogue into two-speaker audio.

**How it works**:
1. The TTS model is loaded once (only if there are uncached segments)
2. Each dialogue segment (intro + content segments + outro) is rendered to audio
3. The rendering approach depends on the TTS backend:

| Backend | How it handles two speakers |
|---|---|
| **Kokoro** | Dialogue is split by speaker tags, each speaker's lines are rendered with a different voice from the `voices` pair, then interleaved |
| **Chatterbox** | Dialogue is split by speaker tags, each speaker is rendered with a different reference audio file for voice cloning |

4. Processing is **sequential** — a design choice for simplicity given single-GPU hardware. Segments are independent and could be parallelized with multiple devices

**Output**: `audio/00_intro.wav`, `audio/01_Chapter_1.wav`, ..., `audio/99_outro.wav` (24kHz sample rate)

**Cache**: If an audio `.wav` file already exists, it's loaded from disk.

**Key config**: [`tts`](../reference/api_reference.md#tts-backends) (backend choice, voices, speed, audio_prompts)

---

### Stage 7: Audio Assembly

**What it does**: Concatenates all segment audio files into a single podcast episode.

**How it works**:
1. All per-segment audio arrays are concatenated in order (intro first, outro last)
2. 1.5 seconds of silence is inserted between each segment (shorter than audiobook)
3. The final audio is written as a single `.wav` file

**Output**: `podcast.wav`

**Key config**: [`inter_section_pause`](../reference/api_reference.md#assemble_audiobookaudio_segments-output_path-sample_rate24000-inter_section_pause20---none) (hardcoded at 1.5s)

---

## Caching & Resume

Every stage writes its output to disk before moving on. When you re-run with the same `--output` directory:

| Stage | Cache key | To re-run this stage |
|---|---|---|
| 2. Markdown | `sections/*.md` | Delete the section's `.md` file |
| 3. Outline | `podcast_outline.md` | Delete the file |
| 4. Dialogue | `dialogue/*.txt` + `*_state.json` | Delete both files for the segment |
| 5. Intro/Outro | `dialogue/00_intro.txt` + `99_outro.txt` | Delete both files |
| 6. Audio | `audio/*.wav` | Delete the `.wav` file(s) |
| 7. Final | `podcast.wav` | Delete the final file |

To re-run the entire pipeline from scratch, delete the output directory and run again.

## Per-Run Logging

Each invocation creates a timestamped log file (`run_YYYYMMDD_HHMMSS.log`) in the output directory. The log mirrors all terminal output and is line-buffered for crash resilience. Resuming a run creates a new log file, so the output directory accumulates a full history across invocations.
