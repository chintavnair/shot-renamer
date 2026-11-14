"""ffmpeg helpers: does a file carry audio, and give me its first seconds."""

from __future__ import annotations

import io
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from .resources import binary

SAMPLE_RATE = 16_000


class MediaError(RuntimeError):
    """A file could not be probed or decoded."""


@dataclass(frozen=True)
class Audio:
    """Mono 16 kHz PCM, as WAV bytes, ready for an ASR engine."""

    wav: bytes
    duration: float


def has_audio(path: Path) -> bool:
    proc = subprocess.run(
        [
            binary("ffprobe"), "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise MediaError(proc.stderr.strip() or f"ffprobe failed on {path.name}")
    return bool(proc.stdout.strip())


def extract(path: Path, seconds: float = 15.0) -> Audio:
    """Decode the first ``seconds`` of audio, downmixed to mono 16 kHz."""
    proc = subprocess.run(
        [
            binary("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error",
            "-i", str(path),
            "-t", f"{seconds:g}",
            "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", "-f", "wav", "pipe:1",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        message = proc.stderr.decode("utf-8", "replace").strip()
        raise MediaError(message or f"ffmpeg failed on {path.name}")
    if not proc.stdout:
        raise MediaError(f"no audio decoded from {path.name}")
    return Audio(proc.stdout, _wav_duration(proc.stdout))


def _wav_duration(wav: bytes) -> float:
    """Seconds of audio in a WAV buffer.

    ffmpeg writes a placeholder data-chunk size when streaming to a pipe, so
    the header lies about the frame count; measure the actual payload instead.
    """
    with wave.open(io.BytesIO(wav), "rb") as handle:
        rate = handle.getframerate()
        block = handle.getnchannels() * handle.getsampwidth()

    offset = wav.find(b"data")
    payload = len(wav) - (offset + 8) if offset >= 0 else 0
    return payload / (rate * block) if block else 0.0
