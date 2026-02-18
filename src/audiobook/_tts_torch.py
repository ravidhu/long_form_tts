"""PyTorch adapter for TTS rendering (CUDA / ROCm / CPU).

Uses the ``kokoro`` PyPI package for Kokoro and ``chatterbox-tts`` for Chatterbox.
Each generate_* function returns list[np.ndarray] of float32 audio chunks.
"""

from __future__ import annotations

import numpy as np

from shared.providers import ChatterboxTTS, KokoroTTS, TTSBackend


def _torch_device() -> str:
    """Pick the best available PyTorch device."""
    import torch

    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------


def load_model(tts: TTSBackend):
    """Load a PyTorch TTS model based on config type.

    Returns
    -------
    - KokoroTTS      → ``kokoro.KPipeline``
    - ChatterboxTTS  → ``ChatterboxTTS`` model instance
    """
    if isinstance(tts, KokoroTTS):
        return _load_kokoro(tts)
    elif isinstance(tts, ChatterboxTTS):
        return _load_chatterbox()
    else:
        raise TypeError(f"Unknown TTS config type: {type(tts)}")


def _load_kokoro(tts: KokoroTTS):
    from kokoro import KPipeline

    lang_code = tts.voices[0][0] if tts.voices else "a"
    return KPipeline(lang_code=lang_code, device=_torch_device())


def _load_chatterbox():
    from chatterbox.tts import ChatterboxTTS as _ChatterboxTTS

    device = _torch_device()
    return _ChatterboxTTS.from_pretrained(device=device)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_kokoro(
    model, text: str, voice: str, speed: float, lang_code: str
) -> list[np.ndarray]:
    """Generate audio chunks with Kokoro via PyTorch ``kokoro`` package."""
    chunks: list[np.ndarray] = []
    for _graphemes, _phonemes, audio_tensor in model(
        text, voice=voice, speed=speed
    ):
        chunks.append(audio_tensor.numpy().astype(np.float32))
    return chunks


def generate_chatterbox(
    model, text: str, *, audio_prompt_path: str | None = None
) -> list[np.ndarray]:
    """Generate audio with Chatterbox via ``chatterbox-tts`` package."""
    kwargs = {"text": text}
    if audio_prompt_path is not None:
        kwargs["audio_prompt_path"] = audio_prompt_path
    wav = model.generate(**kwargs)
    audio_np = wav.squeeze().cpu().numpy().astype(np.float32).ravel()
    if audio_np.size > 0:
        return [audio_np]
    return []
