"""TTS runtime detection.

Determines whether to use MLX (Apple Silicon) or PyTorch (CUDA/ROCm/CPU)
for TTS rendering. Override with TTS_RUNTIME env var.
"""

from __future__ import annotations

import functools
import os
from typing import Literal

TTSRuntime = Literal["mlx", "torch"]


@functools.cache
def get_tts_runtime() -> TTSRuntime:
    """Return the active TTS runtime.

    Resolution order:
    1. ``TTS_RUNTIME`` environment variable (``"mlx"`` or ``"torch"``)
    2. Auto-detect: ``"mlx"`` if ``mlx_audio`` is importable, else ``"torch"``
    """
    env = os.environ.get("TTS_RUNTIME", "").strip().lower()
    if env in ("mlx", "torch"):
        return env  # type: ignore[return-value]
    if env:
        raise ValueError(
            f"Invalid TTS_RUNTIME={env!r}. Must be 'mlx' or 'torch'."
        )

    try:
        import mlx_audio  # noqa: F401

        return "mlx"
    except ImportError:
        return "torch"
