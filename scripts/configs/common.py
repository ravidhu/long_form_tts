"""Shared helpers used by both pipeline scripts."""

import sys
from pathlib import Path

# Add src/ to Python path (needed before importing config.* dataclasses)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from shared.extract import InputSource, resolve_input  # noqa: E402, F401

from .loader import MODELS  # noqa: E402, F401

# Default config file locations (next to this file)
CONFIGS_DIR = Path(__file__).parent
AUDIOBOOK_CONFIG = CONFIGS_DIR / "audiobook.yaml"
PODCAST_CONFIG = CONFIGS_DIR / "podcast.yaml"
AUDIOBOOK_EXAMPLE = CONFIGS_DIR / "audiobook.example.yaml"
PODCAST_EXAMPLE = CONFIGS_DIR / "podcast.example.yaml"


def fmt_time(seconds):
    """Format seconds as HH:MM:SS or as sub-second when < 1s."""
    if seconds < 1:
        return f"{seconds:.2f}s"
    h, remainder = divmod(int(seconds), 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class TeeLogger:
    """Duplicate a stream (stdout or stderr) to a log file."""
    def __init__(self, log_path, stream=None):
        self.terminal = stream or sys.stdout
        self.log = open(log_path, "a", buffering=1)  # noqa: SIM115
    def write(self, msg):
        self.terminal.write(msg)
        self.log.write(msg)
    def flush(self):
        self.terminal.flush()
        self.log.flush()
