"""Podcast dialogue generation pipeline.

Outline-first + segment-by-segment dialogue with rolling context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.providers import language_instruction, llm_generate

from .config import PodcastConfig
from .prompts import (
    DIALOGUE_SYSTEM_PROMPTS,
    INTRO_PROMPT,
    OUTLINE_SYSTEM_PROMPT,
    OUTRO_PROMPT,
    SUMMARY_PROMPT,
)


@dataclass
class PodcastOutline:
    """Parsed outline produced by the LLM."""

    raw_text: str
    title: str = ""
    segments: list[dict] = field(default_factory=list)  # kept as raw text per segment


@dataclass
class DialogueSegment:
    """Result of generating one dialogue segment."""

    dialogue: str
    updated_summary: str
    covered_topics: list[str]


# ---------------------------------------------------------------------------
# Outline
# ---------------------------------------------------------------------------


def generate_outline(
    sections_markdown: list[tuple[str, str]],
    config: PodcastConfig,
) -> PodcastOutline:
    """Generate a global podcast outline from section titles and content.

    Parameters
    ----------
    sections_markdown : list of (title, content) tuples
    config : PodcastConfig

    Returns
    -------
    PodcastOutline with raw LLM output and parsed title
    """
    # Build a summary of each section for the outline prompt
    section_summaries = []
    for i, (title, content) in enumerate(sections_markdown, 1):
        # Truncate very long sections to ~2000 chars for the outline
        preview = content[:2000] + "..." if len(content) > 2000 else content
        section_summaries.append(
            f"SECTION {i}: {title}\n{preview}\n"
        )

    duration_hint = (
        f"Target duration: {config.dialogue.target_duration_min} minutes\n"
        if config.dialogue.target_duration_min
        else "Duration: cover all sections thoroughly — no fixed time limit.\n"
    )
    prompt = (
        duration_hint
        + f"Number of source sections: {len(sections_markdown)}\n\n"
        + "\n".join(section_summaries)
    )

    system = OUTLINE_SYSTEM_PROMPT + language_instruction(config.dialogue.source_lang, config.dialogue.target_lang)
    raw = llm_generate(system, prompt, config.llm)

    # Parse title from the outline
    title = ""
    for line in raw.splitlines():
        if line.strip().lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            break

    return PodcastOutline(raw_text=raw, title=title)


# ---------------------------------------------------------------------------
# Dialogue segments
# ---------------------------------------------------------------------------


def generate_dialogue_segment(
    section_content: str,
    section_title: str,
    outline: PodcastOutline,
    segment_index: int,
    rolling_summary: str,
    covered_topics: list[str],
    config: PodcastConfig,
) -> DialogueSegment:
    """Generate dialogue for one segment with rolling context.

    Parameters
    ----------
    section_content : markdown content for this section
    section_title : title of this section
    outline : the global outline (stays constant)
    segment_index : 0-based index of this segment
    rolling_summary : summary of all previous segments
    covered_topics : list of topics already discussed
    config : PodcastConfig

    Returns
    -------
    DialogueSegment with dialogue text, updated summary, and updated topic list
    """
    dlg = config.dialogue
    target_words = dlg.segment_target_words
    target_minutes = target_words // dlg.words_per_minute

    # Format the system prompt with speaker names and targets
    system_template = DIALOGUE_SYSTEM_PROMPTS[dlg.format]
    system = system_template.format(
        speaker1=dlg.speaker1_name,
        speaker2=dlg.speaker2_name,
        target_words=target_words,
        target_minutes=target_minutes,
    ) + language_instruction(dlg.source_lang, dlg.target_lang)

    # Build the user prompt with context
    parts = [
        f"PODCAST OUTLINE (for reference):\n{outline.raw_text}\n",
        f"CURRENT SEGMENT: {segment_index + 1} — {section_title}\n",
    ]
    if rolling_summary:
        parts.append(f"CONVERSATION SO FAR (summary):\n{rolling_summary}\n")
    if covered_topics:
        parts.append(
            "TOPICS ALREADY COVERED (do NOT repeat):\n"
            + "\n".join(f"- {t}" for t in covered_topics)
            + "\n"
        )
    parts.append(f"SOURCE MATERIAL FOR THIS SEGMENT:\n{section_content}")

    prompt = "\n".join(parts)
    dialogue = llm_generate(system, prompt, config.llm)

    # Generate updated rolling summary
    updated_summary, new_topics = _update_summary(
        rolling_summary, dialogue, covered_topics, config
    )

    return DialogueSegment(
        dialogue=dialogue,
        updated_summary=updated_summary,
        covered_topics=new_topics,
    )


def _update_summary(
    previous_summary: str,
    new_dialogue: str,
    previous_topics: list[str],
    config: PodcastConfig,
) -> tuple[str, list[str]]:
    """Update rolling summary and topic list after a dialogue segment."""
    prompt = SUMMARY_PROMPT.format(
        previous_summary=previous_summary or "(No previous summary — this is the first segment.)",
        new_dialogue=new_dialogue,
    )

    summary_system = (
        "You are a concise summarizer maintaining context for a podcast."
        + language_instruction(config.dialogue.source_lang, config.dialogue.target_lang)
    )
    raw = llm_generate(summary_system, prompt, config.llm)

    # Parse topics from the summary output
    topics = list(previous_topics)
    if "TOPICS COVERED:" in raw:
        topic_section = raw.split("TOPICS COVERED:", 1)[1]
        for line in topic_section.splitlines():
            line = line.strip().lstrip("-•*").strip()
            if line and line not in topics:
                topics.append(line)

    # Summary is everything before TOPICS COVERED
    summary = raw.split("TOPICS COVERED:")[0].strip() if "TOPICS COVERED:" in raw else raw.strip()

    return summary, topics


# ---------------------------------------------------------------------------
# Intro / Outro
# ---------------------------------------------------------------------------


def generate_intro_outro(
    outline: PodcastOutline,
    all_topics: list[str],
    config: PodcastConfig,
) -> tuple[str, str]:
    """Generate podcast intro and outro dialogue.

    Returns
    -------
    (intro_dialogue, outro_dialogue) tuple
    """
    dlg = config.dialogue
    title = outline.title or "Untitled Episode"
    topics_str = ", ".join(all_topics[:10])  # cap at 10 for prompt length

    intro_prompt = INTRO_PROMPT.format(
        speaker1=dlg.speaker1_name,
        speaker2=dlg.speaker2_name,
        title=title,
        topics=topics_str,
    )
    lang_inst = language_instruction(dlg.source_lang, dlg.target_lang)
    intro_system = (
        f"You are writing podcast dialogue. Use [S1] for {dlg.speaker1_name} "
        f"and [S2] for {dlg.speaker2_name}."
        + lang_inst
    )
    intro = llm_generate(intro_system, intro_prompt, config.llm)

    outro_prompt = OUTRO_PROMPT.format(
        speaker1=dlg.speaker1_name,
        speaker2=dlg.speaker2_name,
        title=title,
        topics=topics_str,
    )
    outro = llm_generate(intro_system, outro_prompt, config.llm)

    return intro, outro
