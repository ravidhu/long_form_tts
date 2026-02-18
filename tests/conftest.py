"""Shared fixtures and path setup for the test suite."""

import sys
from pathlib import Path

import pytest

# Mirror the sys.path setup used by the pipeline scripts
_APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_APP / "src"))
sys.path.insert(0, str(_APP / "scripts"))


# ---------------------------------------------------------------------------
# Clear infer_toc LRU cache between tests so results don't leak
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_infer_toc_cache():
    yield
    from shared.pdf_parser.infer_toc import infer_toc
    infer_toc.cache_clear()
