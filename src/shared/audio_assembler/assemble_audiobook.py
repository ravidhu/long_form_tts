import numpy as np
import soundfile as sf

from shared.providers import SAMPLE_RATE


def assemble_audiobook(
    audio_segments: list[np.ndarray],
    output_path: str,
    sample_rate: int = SAMPLE_RATE,
    inter_section_pause: float = 2.0,
) -> None:
    """Concatenate section audio arrays with pauses between them and write to wav.

    Args:
        audio_segments: List of numpy float32 arrays, one per section.
        output_path: Path to write the final wav file.
        sample_rate: Audio sample rate (default 24kHz for Kokoro).
        inter_section_pause: Seconds of silence between sections (default 2.0).
    """
    if not audio_segments:
        raise ValueError("No audio segments to assemble")

    pause = np.zeros(int(inter_section_pause * sample_rate), dtype=np.float32)

    parts = []
    for i, segment in enumerate(audio_segments):
        parts.append(segment)
        if i < len(audio_segments) - 1:
            parts.append(pause)

    final_audio = np.concatenate(parts)
    sf.write(output_path, final_audio, sample_rate)

    duration_min = len(final_audio) / sample_rate / 60
    print(f"Audiobook saved to: {output_path}")
    print(f"Duration: {duration_min:.1f} minutes")
