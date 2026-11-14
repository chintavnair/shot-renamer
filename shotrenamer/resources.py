"""Locate ffmpeg, ffprobe and the Whisper model.

A packaged build carries all three next to the executable; a source checkout
falls back to whatever is on PATH and to the HuggingFace cache.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _roots() -> list[Path]:
    """Directories that may hold bundled resources, most specific first."""
    roots: list[Path] = []
    override = os.environ.get("SHOT_RENAMER_HOME")
    if override:
        roots.append(Path(override))
    # PyInstaller 6 puts bundled data under _internal, exposed as _MEIPASS.
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(Path(bundle))
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).parent)
    return roots


def binary(name: str) -> str:
    """Absolute path to a bundled helper binary, or the bare name for PATH."""
    for root in _roots():
        for candidate in (root / name, root / "bin" / name):
            if candidate.is_file():
                return str(candidate)
    return name


def model_dir(name: str) -> str | None:
    """Directory of a model shipped inside this build, if there is one."""
    for root in _roots():
        candidate = root / "models" / name
        if (candidate / "model.bin").is_file():
            return str(candidate)
    return None
