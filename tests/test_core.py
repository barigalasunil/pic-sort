import datetime
from pathlib import Path

import pytest

from picsort import core


def test_destination_for_layout():
    dt = datetime.datetime(2026, 8, 26, 14, 30, 0)
    dest = Path("D:/dest")
    assert core.destination_for(dest, dt) == Path("D:/dest/2026/August/26")


def test_parse_exif_datetime_variants():
    assert core._parse_exif_datetime("2024:08:26 14:30:00") == datetime.datetime(2024, 8, 26, 14, 30, 0)
    assert core._parse_exif_datetime("2024/08/26 14:30") == datetime.datetime(2024, 8, 26, 14, 30, 0)
    assert core._parse_exif_datetime("2024-08-26") == datetime.datetime(2024, 8, 26, 0, 0, 0)
    assert core._parse_exif_datetime("not a date") is None


def test_file_identity_full_under_threshold(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"hello world" * 10)
    ident = core.file_identity(p)
    assert ident[0] == "full"


def test_unique_copy_path_returns_none_for_duplicate(tmp_path):
    src = tmp_path / "x.jpg"
    src.write_bytes(b"content")
    ident = core.file_identity(src)
    day = tmp_path / "day"
    target = core.unique_copy_path(day, "x.jpg", ident)
    assert target is not None
    assert day.exists()
    import shutil
    shutil.copy2(src, target)
    assert target.exists()
    core.cache_put(day, target.name, ident)
    assert core.unique_copy_path(day, "x.jpg", ident) is None


def test_mode_configs_immutable_shape():
    for key in ("media", "documents"):
        cfg = core.MODE_CONFIGS[key]
        assert "extensions" in cfg and "date_tags" in cfg and "types" in cfg


def test_scan_sources_filters_extensions(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"a")
    (tmp_path / "b.txt").write_bytes(b"b")
    found = list(core.scan_sources([tmp_path], {".jpg"}))
    assert len(found) == 1
    assert found[0].suffix.lower() == ".jpg"


def test_bump_type_counts_increments_matching_type():
    cfg = core.MODE_CONFIGS["media"]
    counts = {"photo": 0, "video": 0}
    core._bump_type_counts(counts, ".jpg", cfg)
    core._bump_type_counts(counts, ".MP4", cfg)
    assert counts == {"photo": 1, "video": 1}
