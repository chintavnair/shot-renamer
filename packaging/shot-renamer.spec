# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the no-install build.

Everything lands in a single folder: ffmpeg/ffprobe at the root (found through
shotrenamer.resources), the model under models/, and the Python runtime plus
native libraries under _internal/.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parent
vendor = root / "vendor"

datas = []
binaries = []
hiddenimports = []

for package in ("ctranslate2", "onnxruntime", "faster_whisper", "tokenizers", "av"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports

for tool in ("ffmpeg", "ffprobe"):
    binaries.append((str(vendor / "bin" / tool), "."))

datas.append((str(vendor / "models"), "models"))

# Whatever the platform's build shipped: licence text and provenance.
for note in sorted((vendor / "bin").glob("*.txt")):
    datas.append((str(note), "licenses"))

analysis = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="shot-renamer",
    console=True,
)

COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    # Stripping invalidates code signatures on macOS.
    strip=sys.platform != "darwin",
    upx=False,
    name="shot-renamer",
)
