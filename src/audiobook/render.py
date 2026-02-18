"""Audiobook TTS rendering with multi-backend support.

Supports Kokoro and Chatterbox TTS engines with automatic runtime
selection between MLX (Apple Silicon) and PyTorch (CUDA/ROCm/CPU).
"""

from __future__ import annotations

import re

import numpy as np

from shared.providers import (
    SAMPLE_RATE,
    ChatterboxTTS,
    KokoroTTS,
    TTSBackend,
    get_tts_runtime,
)

# Silence segments (24kHz sample rate)
PAUSE_SHORT = np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)  # 0.5s
PAUSE_MEDIUM = np.zeros(int(1.2 * SAMPLE_RATE), dtype=np.float32)  # 1.2s
PAUSE_LONG = np.zeros(int(2.0 * SAMPLE_RATE), dtype=np.float32)  # 2.0s

PAUSE_MAP = {
    "[PAUSE_SHORT]": PAUSE_SHORT,
    "[PAUSE_MEDIUM]": PAUSE_MEDIUM,
    "[PAUSE_LONG]": PAUSE_LONG,
}

_PAUSE_PATTERN = r"(\[PAUSE_SHORT\]|\[PAUSE_MEDIUM\]|\[PAUSE_LONG\])"


def _get_backend():
    """Return the active TTS backend module (_mlx or _torch)."""
    if get_tts_runtime() == "mlx":
        from audiobook import _tts_mlx as backend
    else:
        from audiobook import _tts_torch as backend
    return backend


def load_tts_model(tts: TTSBackend):
    """Load a TTS model based on config type. Call once, pass to render_section().

    Parameters
    ----------
    tts : KokoroTTS | ChatterboxTTS
    """
    return _get_backend().load_model(tts)



def render_section(
    narration: str, tts: TTSBackend, model=None
) -> np.ndarray:
    """Render narration text with pause markers into a numpy audio array.

    Args:
        narration: Text with [PAUSE_SHORT], [PAUSE_MEDIUM], [PAUSE_LONG] markers.
        tts: TTS backend config (KokoroTTS or ChatterboxTTS).
        model: Pre-loaded TTS model from load_tts_model(). Required.

    Returns:
        Concatenated audio as a numpy float32 array at 24kHz.
    """
    if model is None:
        raise ValueError("model is required — call load_tts_model() first")

    if isinstance(tts, KokoroTTS):
        return _render_kokoro(narration, model, tts)
    elif isinstance(tts, ChatterboxTTS):
        return _render_chatterbox(narration, model, tts)
    else:
        raise TypeError(f"Unknown TTS config type: {type(tts)}")


# ---------------------------------------------------------------------------
# Kokoro
# ---------------------------------------------------------------------------


def _render_kokoro(narration: str, model, tts: KokoroTTS) -> np.ndarray:
    """Render with Kokoro — voice from config, lang_code from voice prefix."""
    backend = _get_backend()
    voice = tts.voices[0]
    lang_code = voice[0]  # derive from voice prefix (e.g. "af_heart" → "a")
    parts = re.split(_PAUSE_PATTERN, narration)

    audio_segments: list[np.ndarray] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if part in PAUSE_MAP:
            audio_segments.append(PAUSE_MAP[part])
            continue

        for chunk in backend.generate_kokoro(
            model, text=part, voice=voice, speed=tts.speed, lang_code=lang_code
        ):
            audio_segments.append(chunk)

    if not audio_segments:
        return np.array([], dtype=np.float32)

    return np.concatenate(audio_segments)


# ---------------------------------------------------------------------------
# Chatterbox — single narrator, optional voice cloning via audio prompt
# ---------------------------------------------------------------------------


def _render_chatterbox(narration: str, model, tts: ChatterboxTTS) -> np.ndarray:
    """Render with Chatterbox — single narrator, optional voice cloning."""
    backend = _get_backend()
    parts = re.split(_PAUSE_PATTERN, narration)

    # Use first audio prompt for single-narrator audiobook
    ref_audio = tts.audio_prompts[0] if tts.audio_prompts else None

    audio_segments: list[np.ndarray] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if part in PAUSE_MAP:
            audio_segments.append(PAUSE_MAP[part])
            continue

        if get_tts_runtime() == "mlx":
            for chunk in backend.generate_chatterbox(
                model,
                text=part,
                ref_audio=ref_audio,
                lang_code=tts.lang,
                exaggeration=tts.exaggeration,
                cfg_weight=tts.cfg,
            ):
                audio_segments.append(chunk)
        else:
            for chunk in backend.generate_chatterbox(
                model, text=part, audio_prompt_path=ref_audio
            ):
                audio_segments.append(chunk)

    if not audio_segments:
        return np.array([], dtype=np.float32)
    return np.concatenate(audio_segments)
