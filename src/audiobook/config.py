"""Audiobook pipeline configuration."""

from __future__ import annotations

from dataclasses import dataclass

from shared.providers import KokoroTTS, LLMBackend, OllamaLLM, TTSBackend


@dataclass
class NarrationConfig:
    """Controls audiobook narration generation."""

    source_lang: str = "en"  # language of the PDF
    target_lang: str = "en"  # language for the audiobook
    max_workers: int = 1  # parallel LLM requests (tune to hardware)


@dataclass
class AudiobookConfig:
    """Top-level audiobook pipeline configuration.

    Composes narration, LLM, and TTS configs.
    """

    narration: NarrationConfig | None = None
    llm: LLMBackend | None = None
    tts: TTSBackend | None = None

    def __post_init__(self):
        if self.narration is None:
            self.narration = NarrationConfig()
        if self.llm is None:
            self.llm = OllamaLLM(temperature=0.3)
        if self.tts is None:
            # Auto-select TTS backend from target_lang
            self.tts = KokoroTTS(lang=self.narration.target_lang)
        elif isinstance(self.tts, KokoroTTS) and self.tts.lang is None:
            self.tts.lang = self.narration.target_lang
            self.tts.__post_init__()  # re-resolve voices
