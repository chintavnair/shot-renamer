import csv
import json
import shutil
import subprocess

import pytest

from shotrenamer import cli
from shotrenamer.transcribe import Transcription

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

SLATE = "Scene 12, Shot 3, Take 2."


def tone(path, seconds=1.0):
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
            "-t", str(seconds), str(path),
        ],
        check=True,
    )
    return path


class FakeTranscriber:
    device = "cpu"
    compute_type = "int8"
    warning = None

    def __init__(self, text):
        self.text = text

    def warmup(self):
        pass

    def transcribe(self, audio):
        return Transcription(self.text, 0.0)


@pytest.fixture
def stub(monkeypatch):
    def _stub(text=SLATE):
        monkeypatch.setattr(cli, "build_transcriber", lambda args: FakeTranscriber(text))

    return _stub


def test_dry_run_changes_nothing(tmp_path, stub, capsys):
    stub()
    take = tone(tmp_path / "A045.mov")
    log = tmp_path / "log.csv"

    code = cli.main([str(tmp_path), "--json", "--log", str(log)])

    assert code == 0
    assert take.exists()
    assert (tmp_path / "Scene12 Shot03 Take02.mov").exists() is False
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["status"] == "would-rename"
    assert payload[0]["target"].endswith("Scene12 Shot03 Take02.mov")


def test_apply_renames_and_logs(tmp_path, stub):
    stub()
    take = tone(tmp_path / "A045.mov")
    log = tmp_path / "log.csv"

    code = cli.main([str(tmp_path), "--apply", "--log", str(log)])

    assert code == 0
    assert not take.exists()
    assert (tmp_path / "Scene12 Shot03 Take02.mov").exists()

    with log.open() as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["status"] == "renamed"
    assert rows[0]["source"].endswith("A045.mov")
    assert rows[0]["transcript"] == SLATE


def test_duplicate_slates_get_suffixed(tmp_path, stub):
    stub()
    first = tone(tmp_path / "A-cam.mov")
    second = tone(tmp_path / "B-cam.mov")

    code = cli.main([str(tmp_path), "--apply", "--log", str(tmp_path / "log.csv")])

    assert code == 0
    assert not first.exists() and not second.exists()
    assert (tmp_path / "Scene12 Shot03 Take02.mov").exists()
    assert (tmp_path / "Scene12 Shot03 Take02_2.mov").exists()


def test_no_slate_leaves_file_alone_and_fails(tmp_path, stub, capsys):
    stub("just some room tone chatter")
    take = tone(tmp_path / "mystery.mov")

    code = cli.main([str(tmp_path), "--json", "--log", str(tmp_path / "log.csv")])

    assert code == 1
    assert take.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["status"] == "no-slate"
    assert payload[0]["transcript"] == "just some room tone chatter"


def test_already_named_is_idempotent(tmp_path, stub):
    stub("Scene 3A, Shot 3, Take 1.")
    take = tone(tmp_path / "Scene03A Shot03 Take01.mov")

    code = cli.main([str(tmp_path), "--apply", "--log", str(tmp_path / "log.csv")])

    assert code == 0
    assert take.exists()


def test_file_without_audio_is_skipped(tmp_path, stub, capsys):
    stub()
    mute = tmp_path / "mute.mp4"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=160x120:rate=10", "-t", "1", "-c:v", "mpeg4", str(mute)],
        check=True,
    )

    code = cli.main([str(tmp_path), "--json", "--log", str(tmp_path / "log.csv")])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["status"] == "no-audio"


def test_non_media_file_in_directory_is_skipped(tmp_path, stub, capsys):
    stub()
    (tmp_path / "notes.txt").write_text("hello")

    code = cli.main([str(tmp_path), "--json", "--log", str(tmp_path / "log.csv")])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["status"] == "not-media"


def test_explicit_unreadable_file_fails(tmp_path, stub, capsys):
    stub()
    broken = tmp_path / "broken.mov"
    broken.write_bytes(b"not a movie")

    code = cli.main([str(broken), "--json", "--log", str(tmp_path / "log.csv")])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["status"] == "error"
    assert broken.exists()


def test_parser_defaults():
    args = cli.build_parser().parse_args(["some/dir"])
    assert args.apply is False
    assert args.seconds == 15.0
    assert args.model == "small.en"
    assert args.device == "auto"
