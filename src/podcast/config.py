"""Podcast pipeline configuration."""

from __future__ import annotations

from dataclasses import dataclass

from shared.providers import KokoroTTS, LLMBackend, OllamaLLM, TTSBackend


@dataclass
class DialogueConfig:
    """Controls podcast dialogue generation."""

    format: str = "two_hosts"  # "two_hosts" | "host_guest"
    speaker1_name: str = "Alex"
    speaker2_name: str = "Sam"
    source_lang: str = "en"  # language of the PDF
    target_lang: str = "en"  # language for the podcast dialogue
    target_duration_min: int | None = None  # optional hint for outline LLM
    words_per_minute: int = 150  # estimation only (duration display), does not affect audio speed
    segment_target_words: int = 1200  # ~8 min per segment at 150 wpm


@dataclass
class PodcastConfig:
    """Top-level podcast pipeline configuration.

    Composes dialogue, LLM, and TTS configs.
    """

    dialogue: DialogueConfig | None = None
    llm: LLMBackend | None = None
    tts: TTSBackend | None = None

    def __post_init__(self):
        if self.dialogue is None:
            self.dialogue = DialogueConfig()
        if self.llm is None:
            self.llm = OllamaLLM()
        if self.tts is None:
            # Auto-select TTS backend from target_lang
            self.tts = KokoroTTS(lang=self.dialogue.target_lang)
        elif isinstance(self.tts, KokoroTTS) and self.tts.lang is None:
            self.tts.lang = self.dialogue.target_lang
            self.tts.__post_init__()  # re-resolve voices
