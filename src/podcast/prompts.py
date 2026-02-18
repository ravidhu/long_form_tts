"""Prompt templates for podcast dialogue generation."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text().strip()


OUTLINE_SYSTEM_PROMPT = _load_prompt("outline_system.md")
DIALOGUE_SYSTEM_PROMPT_TWO_HOSTS = _load_prompt("dialogue_two_hosts.md")
DIALOGUE_SYSTEM_PROMPT_HOST_GUEST = _load_prompt("dialogue_host_guest.md")
INTRO_PROMPT = _load_prompt("intro.md")
OUTRO_PROMPT = _load_prompt("outro.md")
SUMMARY_PROMPT = _load_prompt("summary.md")

DIALOGUE_SYSTEM_PROMPTS = {
    "two_hosts": DIALOGUE_SYSTEM_PROMPT_TWO_HOSTS,
    "host_guest": DIALOGUE_SYSTEM_PROMPT_HOST_GUEST,
}
