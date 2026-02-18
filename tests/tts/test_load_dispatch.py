"""Tests for TTS backend dispatch — verify correct module is loaded."""

from unittest.mock import MagicMock, patch

import pytest

from shared.providers import KokoroTTS


@pytest.fixture(autouse=True)
def _clear_runtime_cache():
    from shared.providers.get_tts_runtime import get_tts_runtime

    get_tts_runtime.cache_clear()
    yield
    get_tts_runtime.cache_clear()


class TestRenderSectionBackendDispatch:
    """render_section._get_backend() returns the correct module."""

    def test_mlx_runtime_loads_mlx_backend(self):
        with patch("audiobook.render.get_tts_runtime", return_value="mlx"):
            from audiobook.render import _get_backend

            backend = _get_backend()
            assert backend.__name__.endswith("_mlx")

    def test_torch_runtime_loads_torch_backend(self):
        with patch("audiobook.render.get_tts_runtime", return_value="torch"):
            from audiobook.render import _get_backend

            backend = _get_backend()
            assert backend.__name__.endswith("_torch")


class TestRenderDialogueBackendDispatch:
    """render_dialogue._get_backend() returns the correct module."""

    def test_mlx_runtime_loads_mlx_backend(self):
        with patch("podcast.render.get_tts_runtime", return_value="mlx"):
            from podcast.render import _get_backend

            backend = _get_backend()
            assert backend.__name__.endswith("_mlx")

    def test_torch_runtime_loads_torch_backend(self):
        with patch("podcast.render.get_tts_runtime", return_value="torch"):
            from podcast.render import _get_backend

            backend = _get_backend()
            assert backend.__name__.endswith("_torch")


class TestLoadTtsModelDispatches:
    """load_tts_model() calls the correct backend's load_model()."""

    def test_render_section_load_dispatches(self):
        mock_backend = MagicMock()
        mock_backend.load_model.return_value = "fake_model"

        with patch("audiobook.render._get_backend", return_value=mock_backend):
            from audiobook.render import load_tts_model

            tts = KokoroTTS()
            result = load_tts_model(tts)
            mock_backend.load_model.assert_called_once_with(tts)
            assert result == "fake_model"

    def test_render_dialogue_load_dispatches(self):
        mock_backend = MagicMock()
        mock_backend.load_model.return_value = "fake_model"

        with patch("podcast.render._get_backend", return_value=mock_backend):
            from podcast.render import load_tts_model

            tts = KokoroTTS()
            result = load_tts_model(tts)
            mock_backend.load_model.assert_called_once_with(tts)
            assert result == "fake_model"
