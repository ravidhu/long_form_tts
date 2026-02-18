"""Shared configuration — models, defaults, and helpers used by both pipelines."""

import sys
from pathlib import Path

# Add src/ to Python path (needed before importing config.* dataclasses)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from shared.extract import InputSource, resolve_input  # noqa: E402, F401

# --- LLM models reference ---
MODELS = {
    # Ollama — local models
    "qwen3:32b":        {"context": 40960,  "notes": "Best dense model, strong French, Apache 2.0"},
    "qwen3:14b":        {"context": 40960,  "notes": "Sweet spot speed/quality, Apache 2.0"},
    "qwen3:8b":         {"context": 40960,  "notes": "Matches qwen2.5:14b quality, smallest"},
    "qwen3:30b-a3b":    {"context": 262144, "notes": "MoE 3B active, 256K context, Apache 2.0"},
    "mistral-small3.2:24b-instruct-2506-q8_0": {
        "context": 131072, "notes": "Best French, reduced repetition, Apache 2.0",
    },
    "mistral-nemo":     {"context": 131072, "notes": "12B, 128K context, good French"},
    # MLX — local on Apple Silicon (use with MLXLLM)
    "Qwen/Qwen3-8B-MLX-4bit":      {"context": 40960,  "notes": "MLX 4-bit, 4.35 GB"},
    "Qwen/Qwen3-14B-MLX-4bit":     {"context": 40960,  "notes": "MLX 4-bit, 7.85 GB"},
    "Qwen/Qwen3-32B-MLX-4bit":     {"context": 40960,  "notes": "MLX 4-bit, 17.4 GB"},
    "Qwen/Qwen3-30B-A3B-MLX-4bit": {"context": 262144, "notes": "MLX 4-bit MoE, 16.2 GB"},
    "mlx-community/Mistral-Nemo-Instruct-2407-4bit": {
        "context": 131072, "notes": "MLX 4-bit, 6.89 GB",
    },
    "mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit": {
        "context": 131072, "notes": "MLX 4-bit, 13.3 GB, best French",
    },
}

# --- Shared defaults ---
PDF_PARSER_BACKEND = "pymupdf"     # "pymupdf" | "docling"
MAX_TOC_LEVEL = 1       # 1 = Parts/Chapters, 2 = sub-chapters



def fmt_time(seconds):
    """Format seconds as HH:MM:SS."""
    h, remainder = divmod(int(seconds), 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class TeeLogger:
    """Duplicate stdout to a log file."""
    def __init__(self, log_path):
        self.terminal = sys.stdout
        self.log = open(log_path, "a", buffering=1)  # noqa: SIM115
    def write(self, msg):
        self.terminal.write(msg)
        self.log.write(msg)
    def flush(self):
        self.terminal.flush()
        self.log.flush()
