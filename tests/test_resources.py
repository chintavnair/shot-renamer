from pathlib import Path

import pytest

from shotrenamer import resources


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("SHOT_RENAMER_HOME", raising=False)


def test_binary_falls_back_to_path_name():
    assert resources.binary("definitely-not-bundled") == "definitely-not-bundled"


def test_binary_finds_override_dir(tmp_path, monkeypatch):
    tool = tmp_path / "ffmpeg"
    tool.write_bytes(b"#!/bin/sh\n")
    monkeypatch.setenv("SHOT_RENAMER_HOME", str(tmp_path))

    assert resources.binary("ffmpeg") == str(tool)


def test_binary_finds_bin_subdirectory(tmp_path, monkeypatch):
    (tmp_path / "bin").mkdir()
    tool = tmp_path / "bin" / "ffprobe"
    tool.write_bytes(b"#!/bin/sh\n")
    monkeypatch.setenv("SHOT_RENAMER_HOME", str(tmp_path))

    assert resources.binary("ffprobe") == str(tool)


def test_model_dir_requires_model_bin(tmp_path, monkeypatch):
    model = tmp_path / "models" / "small.en"
    model.mkdir(parents=True)
    monkeypatch.setenv("SHOT_RENAMER_HOME", str(tmp_path))
    assert resources.model_dir("small.en") is None

    (model / "model.bin").write_bytes(b"x")
    assert resources.model_dir("small.en") == str(model)


def test_model_dir_absent_for_unknown_model(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOT_RENAMER_HOME", str(tmp_path))
    assert resources.model_dir("base.en") is None


def test_env_override_wins_over_other_roots(tmp_path, monkeypatch):
    override = tmp_path / "override"
    override.mkdir()
    (override / "ffmpeg").write_bytes(b"#!/bin/sh\n")
    monkeypatch.setenv("SHOT_RENAMER_HOME", str(override))

    assert resources.binary("ffmpeg").startswith(str(override))
