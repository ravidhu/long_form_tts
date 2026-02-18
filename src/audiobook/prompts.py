"""System prompt for audiobook narration adaptation (all language pairs)."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text().strip()


NARRATION_SYSTEM_PROMPT = _load_prompt("narration_system.md")
