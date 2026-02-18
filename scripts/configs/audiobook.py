"""Audiobook pipeline configuration."""

from audiobook import AudiobookConfig, NarrationConfig
from shared.providers import MLXLLM, ChatterboxTTS, KokoroTTS, OllamaLLM  # noqa: F401

from .common import MODELS, PDF_PARSER_BACKEND  # noqa: F401

# --- Audiobook-specific settings ---
MAX_TOC_LEVEL = 2       # 2 = Chapters (overrides common.py default of 1)
SOURCE_LANGUAGE = "en"  # language of the PDF ("en" or "fr")
TARGET_LANGUAGE = "en"  # language for the audiobook ("en" or "fr")

# Select which model to use
MODEL_NAME = "qwen3:14b"

# --- Audiobook configuration (composable) ---
config = AudiobookConfig(
    narration=NarrationConfig(
        source_lang=SOURCE_LANGUAGE,
        target_lang=TARGET_LANGUAGE,
        max_workers=1,  # parallel Ollama requests — tune to your hardware
    ),

    # LLM — swap the class to switch backend
    # llm=OllamaLLM(model=MODEL_NAME, num_ctx=MODELS[MODEL_NAME]["context"], temperature=0.3),
    llm=MLXLLM(model="Qwen/Qwen3-14B-MLX-4bit"),

    # TTS — auto-selected from target_lang. Uncomment to override:
    # tts=KokoroTTS(speed=0.95),  # custom speed
    # tts=KokoroTTS(voices=("ff_siwis",), speed=0.95),  # custom voice
    # tts=ChatterboxTTS()  # Chatterbox default voice
)

# LLM context window — for section budget calculation
num_ctx = getattr(config.llm, "num_ctx", 40960)
SYSTEM_PROMPT_TOKENS = 350    # narration system prompt (~345 tokens)
CONTEXT_BUDGET = (num_ctx - SYSTEM_PROMPT_TOKENS) // 2  # input ≈ output
