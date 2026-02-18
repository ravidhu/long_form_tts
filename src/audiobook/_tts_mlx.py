"""MLX adapter for TTS rendering (Apple Silicon).

Wraps mlx_audio model loading and generation behind a uniform interface.
Each generate_* function returns list[np.ndarray] of float32 audio chunks.
"""

from __future__ import annotations

import numpy as np

from shared.providers import ChatterboxTTS, KokoroTTS, TTSBackend

_MODEL_IDS: dict[type, str] = {
    KokoroTTS: "mlx-community/Kokoro-82M-bf16",
    ChatterboxTTS: "mlx-community/chatterbox-fp16",
}


def load_model(tts: TTSBackend):
    """Load an MLX TTS model based on config type."""
    from mlx_audio.tts.utils import load_model as _load

    model_id = _MODEL_IDS.get(type(tts))
    if model_id is None:
        raise TypeError(f"Unknown TTS config type: {type(tts)}")
    return _load(model_id)


def generate_kokoro(
    model, text: str, voice: str, speed: float, lang_code: str
) -> list[np.ndarray]:
    """Generate audio chunks with Kokoro via MLX."""
    chunks: list[np.ndarray] = []
    for result in model.generate(
        text=text, voice=voice, speed=speed, lang_code=lang_code
    ):
        chunks.append(np.array(result.audio, dtype=np.float32))
    return chunks


def generate_chatterbox(
    model,
    text: str,
    *,
    ref_audio: str | None = None,
    lang_code: str | None = None,
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
) -> list[np.ndarray]:
    """Generate audio chunks with Chatterbox via MLX."""
    kwargs: dict = {"text": text, "exaggeration": exaggeration, "cfg_weight": cfg_weight}
    if ref_audio is not None:
        kwargs["ref_audio"] = ref_audio
    if lang_code is not None:
        kwargs["lang_code"] = lang_code

    chunks: list[np.ndarray] = []
    for result in model.generate(**kwargs):
        chunks.append(np.array(result.audio, dtype=np.float32))
    return chunks
