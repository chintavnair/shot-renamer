"""Whisper wrapper: turn the extracted slate audio into words."""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel

from .media import Audio
from .resources import model_dir

# A slate is a fixed sentence; showing the model one biases it toward the
# vocabulary and rhythm we are looking for.
SLATE_PROMPT = "Scene 12A, Shot 3, Take 2. Marker."

# Beyond this mean no-speech probability the clip is treated as silent. Without
# a guard, prompt-biased decoding can invent a slate out of room tone.
SILENCE_LIMIT = 0.75

# Below this RMS the audio is dead air (about -80 dBFS). Whisper still emits
# confident text there, echoing the prompt, so the check happens before ASR.
SILENCE_RMS = 1e-4


@dataclass(frozen=True)
class Transcription:
    text: str
    no_speech: float


def _samples(audio: Audio) -> np.ndarray:
    with wave.open(io.BytesIO(audio.wav), "rb") as handle:
        frames = handle.readframes(handle.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32_768.0


def _rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples))))


def _cuda_available() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001 - any failure just means "use CPU"
        return False


class Transcriber:
    """Loads one Whisper model and reuses it across a whole batch."""

    def __init__(
        self,
        model: str = "small.en",
        device: str = "auto",
        compute_type: str = "auto",
        prompt: str = SLATE_PROMPT,
    ) -> None:
        self._name = model_dir(model) or model
        self._requested_device = device
        self._requested_compute = compute_type
        self._prompt = prompt
        self._model: WhisperModel | None = None
        self.device = device
        self.compute_type = compute_type
        self.warning: str | None = None

    def warmup(self) -> None:
        """Load the model up front so a download or CUDA failure fails fast."""
        self._ensure_model()

    def _ensure_model(self) -> WhisperModel:
        if self._model is not None:
            return self._model

        device = self._requested_device
        if device == "auto":
            device = "cuda" if _cuda_available() else "cpu"
        compute = self._requested_compute
        if compute == "auto":
            compute = "float16" if device == "cuda" else "int8"

        try:
            self._model = WhisperModel(self._name, device=device, compute_type=compute)
        except Exception as exc:  # noqa: BLE001 - CUDA needs system libs we cannot check for
            if device != "cuda":
                raise
            self.warning = f"CUDA unusable ({exc}); falling back to CPU"
            device, compute = "cpu", "int8"
            self._model = WhisperModel(self._name, device=device, compute_type=compute)

        self.device, self.compute_type = device, compute
        return self._model

    def transcribe(self, audio: Audio) -> Transcription:
        samples = _samples(audio)
        if _rms(samples) < SILENCE_RMS:
            return Transcription("", 1.0)

        self._ensure_model()
        try:
            return self._run(samples)
        except Exception as exc:  # noqa: BLE001 - CUDA libs can fail lazily
            if self.device != "cuda":
                raise
            self.warning = f"CUDA transcription failed ({exc}); using CPU from here"
            self._use_cpu()
            return self._run(samples)

    def _use_cpu(self) -> None:
        self._model = WhisperModel(self._name, device="cpu", compute_type="int8")
        self.device, self.compute_type = "cpu", "int8"

    def _run(self, samples: np.ndarray) -> Transcription:
        segments, _info = self._model.transcribe(
            samples,
            language="en",
            beam_size=5,
            initial_prompt=self._prompt,
            condition_on_previous_text=False,
            vad_filter=False,
        )

        texts: list[str] = []
        no_speech: list[float] = []
        for segment in segments:  # generator: consume once
            texts.append(segment.text.strip())
            no_speech.append(segment.no_speech_prob)

        mean_no_speech = sum(no_speech) / len(no_speech) if no_speech else 1.0
        if mean_no_speech >= SILENCE_LIMIT:
            return Transcription("", mean_no_speech)
        return Transcription(" ".join(t for t in texts if t).strip(), mean_no_speech)
