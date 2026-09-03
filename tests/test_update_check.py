import json
import time

from picsort import core, update_check


def test_version_compare():
    assert update_check._compare_versions("0.2.0", "0.1.0") is True
    assert update_check._compare_versions("0.1.0", "0.2.0") is False
    assert update_check._compare_versions("1.0.0", "1.0.0") is False
    assert update_check._compare_versions("0.10.0", "0.9.0") is True


def test_cache_fresh():
    empty = {}
    assert update_check._cache_fresh(empty) is False
    old = {"checked_at": time.time() - 30 * 3600}
    assert update_check._cache_fresh(old) is False
    new = {"checked_at": time.time() - 3600}
    assert update_check._cache_fresh(new) is True


def test_check_returns_newer_and_does_not_raise(monkeypatch, tmp_path):
    monkeypatch.setattr(update_check, "_cache_path", lambda: tmp_path / "nocache.json")
    latest = "9.9.9"
    fetched = {"info": {"version": latest}}

    monkeypatch.setattr("picsort.update_check.__version__", "0.1.0")

    res = update_check.check_for_update(fetch=lambda: fetched)
    assert res == latest


def test_check_none_when_up_to_date(monkeypatch, tmp_path):
    monkeypatch.setattr(update_check, "_cache_path", lambda: tmp_path / "nocache.json")
    fetched = {"info": {"version": "0.1.0"}}
    monkeypatch.setattr("picsort.update_check.__version__", "0.1.0")
    assert update_check.check_for_update(fetch=lambda: fetched) is None


def test_check_silent_on_error(monkeypatch, tmp_path):
    monkeypatch.setattr(update_check, "_cache_path", lambda: tmp_path / "nocache.json")
    def boom():
        raise OSError("no network")
    res = update_check.check_for_update(fetch=boom)
    assert res is None


def test_cache_written_and_read(tmp_path):
    path = tmp_path / "update_check.json"
    update_check._write_cache(path, {"info": {"version": "1.0.0"}}, checked=time.time())
    cached = update_check._read_cache(path)
    assert cached is not None
    assert cached["info"]["version"] == "1.0.0"
