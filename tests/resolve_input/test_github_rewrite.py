"""Tests for resolve_input() — GitHub blob URL rewriting."""

from unittest.mock import MagicMock, patch

import requests as _real_requests  # noqa: F401
from configs.common import resolve_input


class TestGitHubRewrite:
    """GitHub blob URLs (github.com/.../blob/...) are rewritten to
    raw.githubusercontent.com before downloading."""

    def test_blob_url_rewritten_to_raw(self, tmp_path):
        dest = str(tmp_path / "downloads")
        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [b"data"]
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp) as mock_get:
            resolve_input(
                "https://github.com/user/repo/blob/main/doc.pdf",
                dest_dir=dest,
            )
            get_call = mock_get.call_args
            assert "raw.githubusercontent.com" in get_call[0][0]
