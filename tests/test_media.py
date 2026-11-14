import io
import shutil
import subprocess
import wave

import pytest

from shotrenamer import media

ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def make_audio(path, seconds=3.0):
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
            "-t", str(seconds), "-ac", "1", str(path),
        ],
        check=True,
    )


def make_video(path, seconds=20.0, with_audio=True):
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
           "-i", "testsrc=size=160x120:rate=10"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
    cmd += ["-t", str(seconds), "-c:v", "mpeg4", "-y"]
    if with_audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(str(path))
    subprocess.run(cmd, check=True)


@ffmpeg
def test_has_audio_true_for_wav(tmp_path):
    path = tmp_path / "take.wav"
    make_audio(path)
    assert media.has_audio(path)


@ffmpeg
def test_has_audio_false_for_silent_video(tmp_path):
    path = tmp_path / "mute.mp4"
    make_video(path, seconds=2, with_audio=False)
    assert not media.has_audio(path)


@ffmpeg
def test_has_audio_true_for_video_with_sound(tmp_path):
    path = tmp_path / "take.mp4"
    make_video(path, seconds=2)
    assert media.has_audio(path)


def test_has_audio_rejects_missing_file(tmp_path):
    with pytest.raises(media.MediaError):
        media.has_audio(tmp_path / "nope.mov")


@ffmpeg
def test_extract_returns_16k_mono_wav(tmp_path):
    path = tmp_path / "short.wav"
    make_audio(path, seconds=3)

    audio = media.extract(path)

    with wave.open(io.BytesIO(audio.wav), "rb") as handle:
        assert handle.getframerate() == media.SAMPLE_RATE
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
    assert audio.duration == pytest.approx(3.0, abs=0.1)


@ffmpeg
def test_extract_truncates_long_video(tmp_path):
    path = tmp_path / "long.mp4"
    make_video(path, seconds=20)

    audio = media.extract(path, seconds=15)

    assert audio.duration == pytest.approx(15.0, abs=0.2)


@ffmpeg
def test_extract_respects_custom_window(tmp_path):
    path = tmp_path / "long.mp4"
    make_video(path, seconds=20)

    audio = media.extract(path, seconds=2)

    assert audio.duration == pytest.approx(2.0, abs=0.2)


@ffmpeg
def test_extract_reports_missing_audio(tmp_path):
    path = tmp_path / "mute.mp4"
    make_video(path, seconds=2, with_audio=False)

    with pytest.raises(media.MediaError):
        media.extract(path)
