"""Turn parsed slates into filenames, resolve collisions, apply renames."""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .slate import Slate

STATUS_RENAMED = "renamed"
STATUS_WOULD_RENAME = "would-rename"
STATUS_ALREADY_NAMED = "already-named"
STATUS_NO_SLATE = "no-slate"
STATUS_NO_AUDIO = "no-audio"
STATUS_NOT_MEDIA = "not-media"
STATUS_ERROR = "error"

# A name this tool would have produced itself: "Scene12A Shot03 Take02.mov".
_CANONICAL = re.compile(r"^Scene\d{2,}[A-Z]? Shot\d{2,} Take\d{2}$")


@dataclass
class Item:
    source: Path
    status: str
    target: Path | None = None
    slate: Slate | None = None
    transcript: str = ""
    note: str = ""

    @property
    def failed(self) -> bool:
        return self.status in (STATUS_NO_SLATE, STATUS_ERROR)


def target_stem(slate: Slate) -> str:
    return (
        f"Scene{slate.scene:02d}{slate.letter or ''} "
        f"Shot{slate.shot:02d} Take{slate.take:02d}"
    )


def is_canonical(name: str) -> bool:
    return bool(_CANONICAL.match(Path(name).stem))


def _names(directory: Path) -> set[str]:
    try:
        return {entry.name.casefold() for entry in directory.iterdir()}
    except OSError:
        return set()


def resolve(items: list[Item]) -> None:
    """Assign a collision-free target to every item that has a slate.

    Duplicate slates (A-cam and B-cam on one take) get ``_2``, ``_3``, ...
    assigned in source-name order, skipping anything already on disk.
    """
    used: dict[Path, set[str]] = {}

    for item in sorted(items, key=lambda it: str(it.source)):
        if item.slate is None:
            continue

        directory = item.source.parent
        base = target_stem(item.slate)
        extension = item.source.suffix

        if directory not in used:
            used[directory] = _names(directory)

        if item.source.name == f"{base}{extension}":
            item.target = item.source
            item.status = STATUS_ALREADY_NAMED
            used[directory].add(item.source.name.casefold())
            continue

        candidate = f"{base}{extension}"
        counter = 2
        while candidate.casefold() in used[directory]:
            candidate = f"{base}_{counter}{extension}"
            counter += 1

        used[directory].add(candidate.casefold())
        item.target = directory / candidate
        if candidate != f"{base}{extension}":
            item.note = f"duplicate slate, suffixed _{counter - 1}"
        item.status = STATUS_WOULD_RENAME


def apply(items: list[Item]) -> None:
    """Rename on disk. Refuses to overwrite anything that appeared meanwhile."""
    for item in items:
        if item.status != STATUS_WOULD_RENAME or item.target is None:
            continue
        if item.target.exists():
            item.status = STATUS_ERROR
            item.note = f"target already exists: {item.target.name}"
            continue
        item.source.rename(item.target)
        item.status = STATUS_RENAMED


def write_log(items: list[Item], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "target", "status", "slate", "transcript", "note"])
        for item in items:
            writer.writerow(
                [
                    str(item.source),
                    str(item.target) if item.target else "",
                    item.status,
                    str(item.slate) if item.slate else "",
                    item.transcript,
                    item.note,
                ]
            )
