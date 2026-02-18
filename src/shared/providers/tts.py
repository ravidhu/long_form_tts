"""TTS backend configurations.

Shared across audiobook and podcast pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass

# Default voice pairs per language (female, male).
# See https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
KOKORO_VOICE_PRESETS: dict[str, tuple[str, ...]] = {
    "en": ("af_heart", "am_michael"),   # American — flagship female (A) + warm male (C+)
    "fr": ("ff_siwis",),                # French — SIWIS corpus female (B-). No male voice.
    "es": ("ef_dora", "em_alex"),       # Spanish — female + male
    "hi": ("hf_alpha", "hm_omega"),     # Hindi — female + male
    "it": ("if_sara", "im_nicola"),     # Italian — female + male
    "ja": ("jf_alpha", "jm_kumo"),      # Japanese — female + male (Kumo no Ito)
    "pt": ("pf_dora", "pm_alex"),       # Brazilian Portuguese — female + male
    "zh": ("zf_xiaobei", "zm_yunjian"), # Mandarin Chinese — female + male
}


@dataclass
class KokoroTTS:
    """Kokoro — lightweight multi-language TTS with built-in voices.

    Supports 8 languages: en, fr, es, hi, it, ja, pt, zh.

    Set ``lang`` to auto-select voices from KOKORO_VOICE_PRESETS,
    or set ``voices`` explicitly for full control.

    Voice naming convention: ``{accent}{gender}_{name}``
      accent: a=American, b=British, e=Spanish, f=French,
              h=Hindi, i=Italian, j=Japanese, p=Portuguese, z=Chinese
      gender: f=female, m=male

    Audiobook uses voices[0]; podcast uses voices[0] and voices[1].

    Models downloaded on first use:
      MLX:     mlx-community/Kokoro-82M-bf16  (~160 MB)
      PyTorch: hexgrad/Kokoro-82M             (~360 MB)
    """

    lang: str | None = None          # auto-select voices from preset
    voices: tuple[str, ...] | None = None  # explicit voice names
    speed: float = 0.95              # global playback speed (native Kokoro param)
    speeds: tuple[float, ...] | None = None  # per-voice speeds; overrides ``speed``

    def __post_init__(self):
        if self.voices is None:
            lang = self.lang or "en"
            if lang not in KOKORO_VOICE_PRESETS:
                raise ValueError(
                    f"No voice preset for lang='{lang}'. "
                    f"Available: {list(KOKORO_VOICE_PRESETS.keys())}. "
                    f"Set voices=(...) explicitly."
                )
            self.voices = KOKORO_VOICE_PRESETS[lang]
        elif self.lang is None:
            # Infer lang from voice prefix for validation convenience
            self.lang = next(
                (lg for lg, vs in KOKORO_VOICE_PRESETS.items()
                 if self.voices[0][0] == vs[0][0]),
                None,
            )


@dataclass
class ChatterboxTTS:
    """Chatterbox — multilingual TTS with voice cloning via reference audio.

    Supports 23+ languages. Provide ``audio_prompts`` with reference WAV paths
    for voice cloning (one path for audiobook, two for podcast two-speaker).

    No native speed control — the model uses a fixed token-to-mel mapping
    with no duration predictor. ``exaggeration`` and ``cfg`` have indirect
    effects on pacing but are not precise speed controls.

    Models downloaded on first use:
      MLX:     mlx-community/chatterbox-fp16  (~2.6 GB)
      PyTorch: ResembleAI/chatterbox          (~9.6 GB)
    """

    audio_prompts: tuple[str, ...] | None = None  # reference audio paths for voice cloning
    exaggeration: float = 0.5  # emotional expressiveness (0.0–1.0)
    cfg: float = 0.5           # classifier-free guidance weight (0.0–1.0)
    lang: str | None = None    # language code (e.g. "en", "fr")


# Union type for type hints
TTSBackend = KokoroTTS | ChatterboxTTS

# All TTS backends output 24kHz audio
SAMPLE_RATE = 24000
