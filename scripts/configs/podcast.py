"""Podcast pipeline configuration."""

from podcast import DialogueConfig, PodcastConfig
from shared.providers import MLXLLM, ChatterboxTTS, KokoroTTS, OllamaLLM  # noqa: F401

from .common import MAX_TOC_LEVEL, MODELS, PDF_PARSER_BACKEND  # noqa: F401

# Select which model to use
MODEL_NAME = "qwen3:14b"

# --- Podcast configuration (composable) ---
config = PodcastConfig(
    dialogue=DialogueConfig(
        format="two_hosts",  # "two_hosts" | "host_guest"
        speaker1_name="Alex",
        speaker2_name="Sam",
        source_lang="en",            # language of the PDF
        target_lang="en",            # language for the podcast dialogue
        target_duration_min=None,  # optional — set e.g. 60 to hint the outline LLM
        words_per_minute=150,
        segment_target_words=1200,  # ~8 min per segment
    ),
    # LLM — swap the class to switch backend
    llm=OllamaLLM(
        model=MODEL_NAME, num_ctx=MODELS[MODEL_NAME]["context"], temperature=0.7
    ),
    # llm=MLXLLM(model="Qwen/Qwen3-14B-MLX-4bit"),
    # TTS — auto-selected from target_lang. Uncomment to override:
    tts=KokoroTTS(voices=("bf_emma", "bm_george"), speeds=(1, 1.2)),  # custom per-voice speeds
    # tts=KokoroTTS(voices=("bf_emma", "bm_george")),  # custom voices
    # tts=ChatterboxTTS(audio_prompts=("voices/host.wav", "voices/guest.wav")),  # voice cloning
)

# LLM context window — for section budget calculation
num_ctx = getattr(config.llm, "num_ctx", 40960)
CONTEXT_BUDGET = (num_ctx - 500) // 2  # 500 token system prompt overhead
