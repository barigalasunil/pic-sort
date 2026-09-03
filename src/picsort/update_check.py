#!/usr/bin/env python3
"""PicSort - silent PyPI update check with 24h cache. Never blocks startup."""

import json
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

from picsort import __version__, core

PYPI_JSON_URL = "https://pypi.org/pypi/picsort-cli/json"
CACHE_TTL = 24 * 3600  # seconds


def _cache_path() -> Path:
    return core.data_dir() / "update_check.json"


def _read_cache(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_cache(path: Path, data: dict, checked: float) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(data)
        payload["checked_at"] = checked
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        pass


def _cache_fresh(cache) -> bool:
    if not isinstance(cache, dict):
        return False
    ts = cache.get("checked_at")
    if not isinstance(ts, (int, float)):
        return False
    return (time.time() - ts) < CACHE_TTL


def _compare_versions(newer: str, older: str) -> bool:
    """True if `newer` is strictly a higher M.m.p version than `older`."""
    def parts(v):
        return [int(x) for x in v.strip().lstrip("v").split(".") if x.isdigit()]
    a, b = parts(newer), parts(older)
    for x, y in zip(a, b):
        if x != y:
            return x > y
    return len(a) > len(b)


def _fetch_latest(fetch=None) -> str | None:
    if fetch is not None:
        return fetch().get("info", {}).get("version")
    if requests is None:
        return None
    try:
        resp = requests.get(PYPI_JSON_URL, timeout=(2, 3))
        resp.raise_for_status()
        return resp.json().get("info", {}).get("version")
    except (OSError, ValueError, requests.RequestException):
        return None


def check_for_update(print_if_newer=True, fetch=None) -> str | None:
    """Return the newer remote version string if an update is available.

    Caches a successful check for 24h. Fails silently (returns None) on any
    error, network issue, parse error, or when already up to date.
    """
    path = _cache_path()
    cache = _read_cache(path)
    if cache and _cache_fresh(cache):
        return None
    try:
        latest = _fetch_latest(fetch=fetch)
    except Exception:
        return None
    if not latest or not _compare_versions(latest, __version__):
        return None
    if print_if_newer:
        from picsort import ui
        ui.console_print(
            f"Update available: v{latest} (you have v{__version__}) \u2014 run: pipx upgrade picsort-cli",
            "yellow",
        )
    _write_cache(path, {"latest": latest}, time.time())
    return latest
