"""Command line entry point: discover files, read their slates, rename them."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import media, rename
from .rename import Item
from .slate import parse
from .transcribe import Transcriber

DEFAULT_SECONDS = 15.0
LOG_NAME = "shot-renamer-log.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shot-renamer",
        description=(
            "Rename takes from the slate spoken at the head of each file. "
            "Extracts the first seconds of audio with ffmpeg, transcribes it, "
            "and renames to 'SceneXX ShotYY TakeZZ'."
        ),
    )
    parser.add_argument("paths", nargs="+", metavar="PATH", help="files or directories")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually rename (default: show what would happen)",
    )
    parser.add_argument("-r", "--recursive", action="store_true", help="recurse into directories")
    parser.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_SECONDS,
        help=f"seconds of audio to transcribe (default: {DEFAULT_SECONDS:g})",
    )
    parser.add_argument("--model", default="small.en", help="Whisper model (default: small.en)")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "cuda"), default="auto", help="default: auto"
    )
    parser.add_argument(
        "--compute-type", default="auto", help="ctranslate2 compute type (default: auto)"
    )
    parser.add_argument(
        "--show-transcript",
        action="store_true",
        help="print what Whisper heard for every file",
    )
    parser.add_argument("--log", type=Path, metavar="FILE", help="CSV audit log path")
    parser.add_argument("--json", action="store_true", dest="as_json", help="machine-readable output")
    parser.add_argument("-q", "--quiet", action="store_true", help="summary only")
    return parser


def build_transcriber(args: argparse.Namespace) -> Transcriber:
    return Transcriber(args.model, args.device, args.compute_type)


def discover(paths: list[str], recursive: bool) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()

    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            entries = path.rglob("*") if recursive else path.iterdir()
            for entry in sorted(entries):
                relative = entry.relative_to(path)
                if not entry.is_file():
                    continue
                if any(part.startswith(".") for part in relative.parts):
                    continue
                if entry.name == LOG_NAME:
                    continue
                if entry not in seen:
                    seen.add(entry)
                    found.append(entry)
        elif path.is_file():
            if path not in seen:
                seen.add(path)
                found.append(path)
        else:
            print(f"skip {raw}: not a file or directory", file=sys.stderr)

    return found


def transcribe_file(path: Path, seconds: float, transcriber: Transcriber) -> Item:
    try:
        audio = media.extract(path, seconds)
        result = transcriber.transcribe(audio)
        slate = parse(result.text)
        if slate is None:
            note = "silent audio" if not result.text else ""
            return Item(path, rename.STATUS_NO_SLATE, transcript=result.text, note=note)
        return Item(path, rename.STATUS_WOULD_RENAME, slate=slate, transcript=result.text)
    except Exception as exc:  # noqa: BLE001 - one bad file must not end the batch
        return Item(path, rename.STATUS_ERROR, note=str(exc))


def run(args: argparse.Namespace) -> int:
    files = discover(args.paths, args.recursive)
    if not files:
        print("no files to process", file=sys.stderr)
        return 2

    items: list[Item] = []
    pending: list[Path] = []
    explicit = {Path(raw) for raw in args.paths if Path(raw).is_file()}

    for path in files:
        try:
            if media.has_audio(path):
                pending.append(path)
            else:
                items.append(Item(path, rename.STATUS_NO_AUDIO, note="no audio stream"))
        except Exception as exc:  # noqa: BLE001
            # A directory scan is full of sidecars; only blame the user for
            # files they named directly.
            status = rename.STATUS_ERROR if path in explicit else rename.STATUS_NOT_MEDIA
            items.append(Item(path, status, note=str(exc)))

    if pending:
        transcriber = build_transcriber(args)
        try:
            transcriber.warmup()
        except Exception as exc:  # noqa: BLE001 - model download / CUDA failure
            print(f"cannot load Whisper model {args.model!r}: {exc}", file=sys.stderr)
            return 2
        if transcriber.warning:
            print(f"warning: {transcriber.warning}", file=sys.stderr)
            shown_warning = transcriber.warning
        else:
            shown_warning = None
        if not args.quiet:
            print(
                f"whisper {args.model} on {transcriber.device}/{transcriber.compute_type}",
                file=sys.stderr,
            )
        for path in pending:
            items.append(transcribe_file(path, args.seconds, transcriber))
        if transcriber.warning and transcriber.warning != shown_warning:
            print(f"warning: {transcriber.warning}", file=sys.stderr)

    items.sort(key=lambda item: str(item.source))
    rename.resolve(items)

    if args.apply:
        rename.apply(items)

    if args.apply or args.log:
        log_path = args.log or Path.cwd() / LOG_NAME
        rename.write_log(items, log_path)
        if not args.quiet:
            print(f"log written to {log_path}", file=sys.stderr)

    if args.as_json:
        print(json.dumps([_as_dict(item) for item in items], indent=2))
    elif not args.quiet:
        _report(items, args.show_transcript, args.apply)

    return 1 if any(item.failed for item in items) else 0


def _as_dict(item: Item) -> dict[str, str]:
    return {
        "source": str(item.source),
        "target": str(item.target) if item.target else "",
        "status": item.status,
        "slate": str(item.slate) if item.slate else "",
        "transcript": item.transcript,
        "note": item.note,
    }


def _report(items: list[Item], show_transcript: bool, applied: bool) -> None:
    width = max(len(item.source.name) for item in items)
    for item in items:
        line = f"{item.source.name:<{width}}  {item.status}"
        if item.target and item.target.name != item.source.name:
            line += f"  ->  {item.target.name}"
        if item.note:
            line += f"  ({item.note})"
        print(line)
        if item.transcript and (show_transcript or item.failed):
            print(f"{'':<{width}}  heard: {item.transcript}")

    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    summary = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    print(f"\n{summary}")

    if not applied and counts.get(rename.STATUS_WOULD_RENAME):
        print("dry run: nothing renamed. re-run with --apply to do it.")


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
