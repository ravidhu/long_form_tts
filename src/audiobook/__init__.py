from shared.providers import SAMPLE_RATE

from .adapt import adapt_narration_section
from .config import AudiobookConfig, NarrationConfig
from .prompts import NARRATION_SYSTEM_PROMPT
from .render import load_tts_model, render_section

__all__ = [
    "adapt_narration_section",
    "AudiobookConfig",
    "NarrationConfig",
    "NARRATION_SYSTEM_PROMPT",
    "render_section",
    "load_tts_model",
    "SAMPLE_RATE",
]
