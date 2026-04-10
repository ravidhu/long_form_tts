"""System prompts for audiobook narration adaptation."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text().strip()


# Legacy full-section prompt (kept for reference / fallback)
NARRATION_SYSTEM_PROMPT = _load_prompt("narration_system.md")

# Block-specific prompts for the hybrid pipeline
TABLE_TO_PROSE_PROMPT = _load_prompt("table_to_prose.md")
CODE_TO_DESCRIPTION_PROMPT = _load_prompt("code_to_description.md")
LIST_TO_PROSE_PROMPT = _load_prompt("list_to_prose.md")
METADATA_CLASSIFY_PROMPT = _load_prompt("metadata_classify.md")
TRANSLATE_BLOCK_PROMPT = _load_prompt("translate_block.md")
