"""Tests for providers.get_tts_runtime — TTS runtime detection."""

from unittest.mock import patch

import pytest

from shared.providers.get_tts_runtime import get_tts_runtime


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the cached runtime result between tests."""
    get_tts_runtime.cache_clear()
    yield
    get_tts_runtime.cache_clear()


class TestEnvOverride:
    """TTS_RUNTIME env var takes priority over auto-detection."""

    def test_env_mlx(self):
        with patch.dict("os.environ", {"TTS_RUNTIME": "mlx"}):
            assert get_tts_runtime() == "mlx"

    def test_env_torch(self):
        with patch.dict("os.environ", {"TTS_RUNTIME": "torch"}):
            assert get_tts_runtime() == "torch"

    def test_env_case_insensitive(self):
        with patch.dict("os.environ", {"TTS_RUNTIME": "MLX"}):
            assert get_tts_runtime() == "mlx"

    def test_env_with_whitespace(self):
        with patch.dict("os.environ", {"TTS_RUNTIME": "  torch  "}):
            assert get_tts_runtime() == "torch"

    def test_env_invalid_raises(self):
        with patch.dict("os.environ", {"TTS_RUNTIME": "jax"}), pytest.raises(
            ValueError, match="Invalid TTS_RUNTIME"
        ):
            get_tts_runtime()


class TestAutoDetect:
    """When no env var, auto-detect based on mlx_audio importability."""

    def test_mlx_available(self):
        with patch.dict("os.environ", {}, clear=True):
            # mlx_audio is importable on this machine (Apple Silicon dev env)
            # so auto-detect should return "mlx"
            result = get_tts_runtime()
            assert result in ("mlx", "torch")

    def test_mlx_not_importable_returns_torch(self):
        import sys

        with (
            patch.dict("os.environ", {}, clear=True),
            patch.dict(sys.modules, {"mlx_audio": None}),
        ):
            # Force ImportError by removing from sys.modules cache
            # and patching __import__
            original_import = (
                __builtins__.__import__
                if hasattr(__builtins__, "__import__")
                else __import__
            )

            def mock_import(name, *args, **kwargs):
                if name == "mlx_audio":
                    raise ImportError("mocked")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                assert get_tts_runtime() == "torch"
