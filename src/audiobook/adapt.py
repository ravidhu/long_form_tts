"""Hybrid narration adapter: rule-based preprocessing + targeted LLM calls.

Paragraphs and headings are processed deterministically (no LLM).
Tables, code blocks, lists, and metadata go through small, focused LLM
calls. This eliminates the summarization problem of sending entire
sections to an LLM.
"""

from __future__ import annotations

import logging

from shared.markdown_parser import Section
from shared.providers import LLMBackend, language_instruction, llm_generate

from .blocks import Block, split_into_blocks
from .preprocess import heading_to_transition, preprocess_paragraph, stitch_broken_lines
from .prompts import (
    CODE_TO_DESCRIPTION_PROMPT,
    LIST_TO_PROSE_PROMPT,
    METADATA_CLASSIFY_PROMPT,
    TABLE_TO_PROSE_PROMPT,
    TRANSLATE_BLOCK_PROMPT,
)

log = logging.getLogger(__name__)


def adapt_narration_section(
    section: Section,
    llm: LLMBackend,
    source_lang: str = "en",
    target_lang: str = "en",
) -> tuple[str, int]:
    """Convert a section to narration-ready prose using a hybrid approach.

    Most content is processed with deterministic rules (markdown stripping,
    number-to-spoken, abbreviation expansion). Only tables, code blocks,
    lists, and metadata blocks go through the LLM.

    Returns:
        (narration_text, llm_call_count)
    """
    needs_translation = source_lang != target_lang
    lang_suffix = language_instruction(source_lang, target_lang)

    blocks = split_into_blocks(stitch_broken_lines(section.content))
    narrated_parts: list[str] = []
    llm_calls = 0

    for block in blocks:
        result, calls = _process_block(block, llm, lang_suffix, needs_translation)
        llm_calls += calls
        if result:
            narrated_parts.append(result)

    return _assemble(narrated_parts), llm_calls


# ---------------------------------------------------------------------------
# Block dispatch
# ---------------------------------------------------------------------------


def _process_block(
    block: Block,
    llm: LLMBackend,
    lang_suffix: str,
    needs_translation: bool,
) -> tuple[str | None, int]:
    """Process a single block. Returns (narration_text, llm_call_count)."""
    if block.kind == "heading":
        text = heading_to_transition(block.content, block.level)
        if needs_translation:
            text = _translate(text, llm, lang_suffix)
            return text, 1
        return text, 0

    if block.kind == "paragraph":
        text = preprocess_paragraph(block.content)
        if needs_translation:
            text = _translate(text, llm, lang_suffix)
            return text, 1
        return text, 0

    if block.kind == "table":
        return _llm_convert(TABLE_TO_PROSE_PROMPT, block.content, llm, lang_suffix), 1

    if block.kind == "code":
        return _llm_convert(CODE_TO_DESCRIPTION_PROMPT, block.content, llm, lang_suffix), 1

    if block.kind == "list":
        return _llm_convert(LIST_TO_PROSE_PROMPT, block.content, llm, lang_suffix), 1

    if block.kind == "metadata":
        result = _classify_metadata(block.content, llm, lang_suffix)
        return result, 1

    # Unknown block kind — treat as paragraph
    text = preprocess_paragraph(block.content)
    if needs_translation:
        text = _translate(text, llm, lang_suffix)
        return text, 1
    return text, 0


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------


def _llm_convert(system_prompt: str, content: str, llm: LLMBackend, lang_suffix: str) -> str:
    """Send a block to the LLM with a focused system prompt."""
    system = system_prompt + lang_suffix
    return llm_generate(system, content, llm)


def _translate(text: str, llm: LLMBackend, lang_suffix: str) -> str:
    """Translate a pre-processed block via LLM (cross-language mode only)."""
    system = TRANSLATE_BLOCK_PROMPT + lang_suffix
    return llm_generate(system, text, llm)


def _classify_metadata(content: str, llm: LLMBackend, lang_suffix: str) -> str | None:
    """Ask the LLM whether to skip or briefly mention a metadata block."""
    system = METADATA_CLASSIFY_PROMPT + lang_suffix
    response = llm_generate(system, content, llm).strip()

    if response.upper().startswith("SKIP"):
        return None

    if response.upper().startswith("MENTION:"):
        return response[len("MENTION:"):].strip()

    # Unexpected format — use the whole response as a mention
    log.warning("Unexpected metadata classification response: %s", response[:100])
    return response


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _assemble(parts: list[str]) -> str:
    """Concatenate narrated parts with pause markers between them.

    Heading transitions already include their own pause markers, so we
    only add [PAUSE_SHORT] between non-heading parts.
    """
    if not parts:
        return ""

    output: list[str] = []
    for i, part in enumerate(parts):
        output.append(part)

        # Don't add extra pause after the last part
        if i >= len(parts) - 1:
            continue

        # Heading transitions already end with a period — add a short
        # pause before the next content block
        if not part.strip().endswith("]"):
            # Not a pause marker line — add paragraph pause
            output.append("[PAUSE_SHORT]")

    return "\n\n".join(output)
