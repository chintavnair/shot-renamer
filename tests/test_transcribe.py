import numpy as np

from shotrenamer.transcribe import SILENCE_RMS, _rms


def test_digital_silence_is_below_threshold():
    assert _rms(np.zeros(16_000, dtype=np.float32)) == 0.0
    assert _rms(np.zeros(0, dtype=np.float32)) == 0.0


def test_quiet_but_real_audio_is_above_threshold():
    tone = 0.1 * np.sin(np.linspace(0, 2 * np.pi * 440, 16_000)).astype(np.float32)
    assert _rms(tone) > SILENCE_RMS


def test_near_silent_noise_sits_below_threshold():
    noise = (np.random.default_rng(0).normal(0, 1e-5, 16_000)).astype(np.float32)
    assert _rms(noise) < SILENCE_RMS
