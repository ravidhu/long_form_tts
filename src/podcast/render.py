"""Multi-speaker TTS rendering for podcast dialogue.

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


def get_sample_rate(tts: TTSBackend) -> int:
    return SAMPLE_RATE


def _make_pause_map(sr: int) -> dict[str, np.ndarray]:
    return {
        "[PAUSE_SHORT]": np.zeros(int(0.5 * sr), dtype=np.float32),
        "[PAUSE_MEDIUM]": np.zeros(int(1.2 * sr), dtype=np.float32),
        "[PAUSE_LONG]": np.zeros(int(2.0 * sr), dtype=np.float32),
    }


def _make_speaker_gap(sr: int) -> np.ndarray:
    return np.zeros(int(0.3 * sr), dtype=np.float32)


def _get_backend():
    """Return the active TTS backend module (_mlx or _torch)."""
    if get_tts_runtime() == "mlx":
        from audiobook import _tts_mlx as backend
    else:
        from audiobook import _tts_torch as backend
    return backend


def load_tts_model(tts: TTSBackend):
    """Load a TTS model. Call once, pass to render_dialogue().

    Parameters
    ----------
    tts : KokoroTTS | ChatterboxTTS
    """
    return _get_backend().load_model(tts)


def render_dialogue(
    dialogue: str,
    tts: TTSBackend,
    model=None,
) -> np.ndarray:
    """Render podcast dialogue to audio.

    Parameters
    ----------
    dialogue : text with [S1]/[S2] speaker tags and [PAUSE_*] markers
    tts : KokoroTTS | ChatterboxTTS config
    model : pre-loaded TTS model from load_tts_model()

    Returns
    -------
    np.ndarray of float32 audio samples at backend sample rate
    (use get_sample_rate(tts) for the correct rate)
    """
    if model is None:
        raise ValueError("model is required — call load_tts_model() first")

    sr = get_sample_rate(tts)
    pause_map = _make_pause_map(sr)
    speaker_gap = _make_speaker_gap(sr)

    if isinstance(tts, KokoroTTS):
        return _render_kokoro(dialogue, model, tts, pause_map, speaker_gap)
    elif isinstance(tts, ChatterboxTTS):
        return _render_chatterbox(dialogue, model, tts, pause_map, speaker_gap)
    else:
        raise TypeError(f"Unknown TTS config type: {type(tts)}")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PAUSE_KEYS = {"[PAUSE_SHORT]", "[PAUSE_MEDIUM]", "[PAUSE_LONG]"}


def _parse_speaker_turns(dialogue: str) -> list[tuple[str, str]]:
    """Parse dialogue into list of (speaker_tag, text) tuples.

    Returns list of ("S1", "text...") or ("S2", "text...") tuples.
    Pause markers are returned as ("PAUSE", "[PAUSE_*]").
    """
    # Tokenize into speaker turns and pause markers
    token_pattern = r"(\[S[12]\]|\[PAUSE_SHORT\]|\[PAUSE_MEDIUM\]|\[PAUSE_LONG\])"
    tokens = re.split(token_pattern, dialogue)

    turns: list[tuple[str, str]] = []
    current_speaker = "S1"

    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token in ("[S1]", "[S2]"):
            current_speaker = token[1:-1]  # "S1" or "S2"
        elif token in _PAUSE_KEYS:
            turns.append(("PAUSE", token))
        else:
            # Text content — attribute to current speaker
            if token:
                turns.append((current_speaker, token))

    return turns


# ---------------------------------------------------------------------------
# Kokoro — alternates between two voice embeddings
# ---------------------------------------------------------------------------


def _render_kokoro(
    dialogue: str, model, tts: KokoroTTS, pause_map: dict, speaker_gap: np.ndarray
) -> np.ndarray:
    """Render by splitting on speaker tags and alternating voices."""
    backend = _get_backend()
    voices = tts.voices
    if len(voices) < 2:
        raise ValueError(f"KokoroTTS for podcast needs 2 voices, got: {voices}")
    voice_map = {"S1": voices[0], "S2": voices[1]}
    speeds = tts.speeds or (tts.speed, tts.speed)
    speed_map = {"S1": speeds[0], "S2": speeds[1]}
    # Derive lang_code from the first voice's prefix (e.g. "af_heart" → "a")
    lang_code = voices[0][0]

    turns = _parse_speaker_turns(dialogue)
    audio_segments: list[np.ndarray] = []

    for speaker, text in turns:
        if speaker == "PAUSE":
            audio_segments.append(pause_map[text])
            continue

        voice = voice_map[speaker]
        for chunk in backend.generate_kokoro(
            model,
            text=text,
            voice=voice,
            speed=speed_map[speaker],
            lang_code=lang_code,
        ):
            audio_segments.append(chunk)

        # Small gap between speaker turns
        audio_segments.append(speaker_gap)

    if not audio_segments:
        return np.array([], dtype=np.float32)
    return np.concatenate(audio_segments)


# ---------------------------------------------------------------------------
# Chatterbox — two-speaker via voice cloning with reference audio
# ---------------------------------------------------------------------------


def _render_chatterbox(
    dialogue: str, model, tts: ChatterboxTTS, pause_map: dict, speaker_gap: np.ndarray
) -> np.ndarray:
    """Render using Chatterbox with two reference audio files for voice cloning."""
    backend = _get_backend()
    turns = _parse_speaker_turns(dialogue)
    audio_segments: list[np.ndarray] = []

    # Map speakers to reference audio prompts
    ref_map = {}
    if tts.audio_prompts and len(tts.audio_prompts) >= 2:
        ref_map = {"S1": tts.audio_prompts[0], "S2": tts.audio_prompts[1]}
    elif tts.audio_prompts and len(tts.audio_prompts) == 1:
        ref_map = {"S1": tts.audio_prompts[0], "S2": tts.audio_prompts[0]}

    is_mlx = get_tts_runtime() == "mlx"

    for speaker, text in turns:
        if speaker == "PAUSE":
            audio_segments.append(pause_map[text])
            continue

        ref_audio = ref_map.get(speaker)

        if is_mlx:
            for chunk in backend.generate_chatterbox(
                model,
                text=text,
                ref_audio=ref_audio,
                lang_code=tts.lang,
                exaggeration=tts.exaggeration,
                cfg_weight=tts.cfg,
            ):
                audio_segments.append(chunk)
        else:
            for chunk in backend.generate_chatterbox(
                model, text=text, audio_prompt_path=ref_audio
            ):
                audio_segments.append(chunk)

        audio_segments.append(speaker_gap)

    if not audio_segments:
        return np.array([], dtype=np.float32)
    return np.concatenate(audio_segments)
