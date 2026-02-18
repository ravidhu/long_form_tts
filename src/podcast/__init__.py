from shared.providers import SAMPLE_RATE

from .config import DialogueConfig, PodcastConfig
from .generate import (
    DialogueSegment,
    PodcastOutline,
    generate_dialogue_segment,
    generate_intro_outro,
    generate_outline,
)
from .render import (
    get_sample_rate,
    load_tts_model,
    render_dialogue,
)

__all__ = [
    "DialogueConfig",
    "PodcastConfig",
    "PodcastOutline",
    "DialogueSegment",
    "generate_outline",
    "generate_dialogue_segment",
    "generate_intro_outro",
    "SAMPLE_RATE",
    "get_sample_rate",
    "load_tts_model",
    "render_dialogue",
]
