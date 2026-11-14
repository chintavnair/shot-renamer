from pathlib import Path

import pytest

from shotrenamer import rename
from shotrenamer.rename import Item
from shotrenamer.slate import Slate


def make_item(path: Path, slate: Slate | None, status: str = rename.STATUS_WOULD_RENAME) -> Item:
    return Item(path, status, slate=slate)


def test_target_stem_formats():
    assert rename.target_stem(Slate(12, None, 3, 2)) == "Scene12 Shot03 Take02"
    assert rename.target_stem(Slate(12, "A", 3, 2)) == "Scene12A Shot03 Take02"
    assert rename.target_stem(Slate(7, None, 12, 10)) == "Scene07 Shot12 Take10"
    assert rename.target_stem(Slate(100, None, 3, 2)) == "Scene100 Shot03 Take02"


def test_is_canonical():
    assert rename.is_canonical("Scene03A Shot03 Take01.mov")
    assert rename.is_canonical("Scene03 Shot03 Take01.mov")
    assert rename.is_canonical("Scene100 Shot012 Take10.mov")
    assert not rename.is_canonical("Scene 3a Shot 3 Take 1.mov")
    assert not rename.is_canonical("Scene3 Shot3 Take1.mov")
    assert not rename.is_canonical("A045_01261916_C065.mov")


def test_resolve_single(tmp_path):
    source = tmp_path / "A045_01261916_C065.mov"
    source.write_bytes(b"x")
    item = make_item(source, Slate(12, None, 3, 2))

    rename.resolve([item])

    assert item.target == tmp_path / "Scene12 Shot03 Take02.mov"
    assert item.status == rename.STATUS_WOULD_RENAME
    assert item.note == ""


def test_resolve_duplicates_suffix_in_name_order(tmp_path):
    first = tmp_path / "A-cam.mov"
    second = tmp_path / "B-cam.mov"
    first.write_bytes(b"x")
    second.write_bytes(b"x")
    items = [make_item(second, Slate(4, None, 2, 1)), make_item(first, Slate(4, None, 2, 1))]

    rename.resolve(items)

    by_name = {item.source.name: item for item in items}
    assert by_name["A-cam.mov"].target.name == "Scene04 Shot02 Take01.mov"
    assert by_name["B-cam.mov"].target.name == "Scene04 Shot02 Take01_2.mov"
    assert by_name["B-cam.mov"].note.startswith("duplicate slate")


def test_resolve_skips_suffix_already_on_disk(tmp_path):
    source = tmp_path / "new.mov"
    source.write_bytes(b"x")
    (tmp_path / "Scene04 Shot02 Take01.mov").write_bytes(b"existing")
    (tmp_path / "Scene04 Shot02 Take01_2.mov").write_bytes(b"existing")
    item = make_item(source, Slate(4, None, 2, 1))

    rename.resolve([item])

    assert item.target.name == "Scene04 Shot02 Take01_3.mov"


def test_resolve_marks_already_named(tmp_path):
    source = tmp_path / "Scene03A Shot03 Take01.mov"
    source.write_bytes(b"x")
    item = make_item(source, Slate(3, "A", 3, 1))

    rename.resolve([item])

    assert item.status == rename.STATUS_ALREADY_NAMED
    assert item.target == source


def test_apply_renames_and_keeps_content(tmp_path):
    source = tmp_path / "take.mov"
    source.write_bytes(b"payload")
    item = make_item(source, Slate(12, None, 3, 2))
    rename.resolve([item])

    rename.apply([item])

    assert item.status == rename.STATUS_RENAMED
    assert not source.exists()
    assert item.target.read_bytes() == b"payload"


def test_apply_refuses_to_overwrite(tmp_path):
    source = tmp_path / "take.mov"
    source.write_bytes(b"new")
    occupied = tmp_path / "Scene12 Shot03 Take02.mov"
    occupied.write_bytes(b"old")
    item = Item(source, rename.STATUS_WOULD_RENAME, target=occupied, slate=Slate(12, None, 3, 2))

    rename.apply([item])

    assert item.status == rename.STATUS_ERROR
    assert occupied.read_bytes() == b"old"
    assert source.read_bytes() == b"new"


def test_resolve_ignores_items_without_slate(tmp_path):
    source = tmp_path / "x.mov"
    source.write_bytes(b"x")
    item = Item(source, rename.STATUS_NO_SLATE)
    rename.resolve([item])
    assert item.target is None
    assert item.status == rename.STATUS_NO_SLATE
