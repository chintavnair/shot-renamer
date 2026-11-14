"""Download the assets a no-install build needs into vendor/.

Fetches a static ffmpeg/ffprobe for the current platform and the Whisper model,
so the packaged build never depends on system packages or the network.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "vendor"

MODELS = {
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base.en": "Systran/faster-whisper-base.en",
    "small.en": "Systran/faster-whisper-small.en",
    "medium.en": "Systran/faster-whisper-medium.en",
}

LINUX_URL = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-{arch}-static.tar.xz"
MAC_URL = "https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/{tool}.zip"
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.txt"


def _download(url: str, destination: Path) -> None:
    print(f"downloading {url}")
    # Some mirrors reject Python's default user agent with a 403.
    request = urllib.request.Request(url, headers={"User-Agent": "shot-renamer-packaging/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def fetch_ffmpeg(bin_dir: Path) -> None:
    if all((bin_dir / tool).is_file() for tool in ("ffmpeg", "ffprobe")):
        print("ffmpeg already present")
        return

    system, machine = platform.system(), platform.machine()
    bin_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)

        if system == "Linux":
            arch = {"x86_64": "amd64", "aarch64": "arm64"}[machine]
            archive = tmp / "ffmpeg.tar.xz"
            _download(LINUX_URL.format(arch=arch), archive)
            with tarfile.open(archive) as tar:
                tar.extractall(tmp / "unpacked")
            source = next((tmp / "unpacked").glob("ffmpeg-*-static"))
            for tool in ("ffmpeg", "ffprobe"):
                shutil.copy2(source / tool, bin_dir / tool)
            # GPL build: ship its licence alongside the binary.
            shutil.copy2(source / "GPLv3.txt", bin_dir / "GPLv3.txt")
            (bin_dir / "SOURCE.txt").write_text(
                "Static build from https://johnvansickle.com/ffmpeg/\n"
            )

        elif system == "Darwin":
            arch = {"arm64": "arm64", "x86_64": "amd64"}[machine]
            for tool in ("ffmpeg", "ffprobe"):
                archive = tmp / f"{tool}.zip"
                _download(MAC_URL.format(arch=arch, tool=tool), archive)
                with zipfile.ZipFile(archive) as zipped:
                    zipped.extract(tool, bin_dir)
                (bin_dir / tool).chmod(0o755)
            (bin_dir / "SOURCE.txt").write_text(
                "Static build from https://ffmpeg.martin-riedl.de/\n"
            )
            # Those builds are GPL; ship the licence text alongside.
            _download(LICENSE_URL, bin_dir / "GPLv3.txt")

        else:
            raise SystemExit(f"unsupported build platform: {system}")


def fetch_model(name: str) -> None:
    if name not in MODELS:
        raise SystemExit(f"unknown model {name!r}; choose from {', '.join(MODELS)}")

    destination = VENDOR / "models" / name
    if (destination / "model.bin").is_file():
        print(f"model {name} already present")
        return

    from huggingface_hub import snapshot_download

    print(f"downloading model {MODELS[name]}")
    snapshot_download(repo_id=MODELS[name], local_dir=destination)

    cache = destination / ".cache"
    if cache.exists():
        shutil.rmtree(cache)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="small.en")
    parser.add_argument("--skip-ffmpeg", action="store_true")
    parser.add_argument("--skip-model", action="store_true")
    args = parser.parse_args()

    if not args.skip_ffmpeg:
        fetch_ffmpeg(VENDOR / "bin")
    if not args.skip_model:
        fetch_model(args.model)


if __name__ == "__main__":
    main()
