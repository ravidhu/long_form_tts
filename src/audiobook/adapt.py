from __future__ import annotations

from shared.markdown_parser import Section
from shared.providers import LLMBackend, language_instruction, llm_generate

from .prompts import NARRATION_SYSTEM_PROMPT


def adapt_narration_section(
    section: Section,
    llm: LLMBackend,
    source_lang: str = "en",
    target_lang: str = "en",
) -> str:
    """Send a section to LLM for narration conversion.

    When source_lang != target_lang, the LLM translates and adapts
    in a single pass. Works with any LLM backend (Ollama, MLX).
    """
    system = NARRATION_SYSTEM_PROMPT + language_instruction(source_lang, target_lang)

    # Add table/list hints for the LLM
    hints = []
    if section.has_table:
        hints.append(
            "This section contains markdown tables — "
            "convert them into comparative narration."
        )
    if section.has_list:
        hints.append(
            "This section contains bullet/numbered lists — "
            "convert them into flowing prose."
        )

    user_msg = f"Section: {section.title}\n"
    if hints:
        user_msg += f"Notes: {' '.join(hints)}\n"
    user_msg += f"\nContent:\n{section.content}"

    return llm_generate(system, user_msg, llm)
