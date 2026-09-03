# PicSort → picsort-cli PyPI Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the single-file `picsort.py` (1027 lines) into a proper `src/`-layout Python package (`picsort`) published to PyPI as `picsort-cli`, installable via `pipx` and invoked as `picsort`, replacing the PyInstaller EXE distribution.

**Architecture:** Split the one file into five focused modules (`__init__.py`, `core.py`, `ui.py`, `update_check.py`, `cli.py`) under `src/picsort/`. `core.py` holds all non-UI logic and never imports `ui`; `ui.py` owns the Rich console and all renderables; `update_check.py` adds a silent PyPI version check; `cli.py` wires them together behind a `main()` entry point with a `-V/--version` flag. Packaging via `setuptools` with `src/` layout, dynamic version sourced from `__init__.py`, and a `picsort` script entry point. The PyPI distribution name is `picsort-cli`; the command/import name is `picsort`.

**Tech Stack:** Python ≥3.9, `rich`, `requests`, `setuptools` (build backend), `pytest` (tests), GitHub Actions (CI + Trusted Publishing to PyPI).

## Global Constraints

- **Naming rule:** the distribution/package name is **`picsort-cli`** (used ONLY in install/upgrade/uninstall/release commands and `pyproject.toml name`). The command, import, module folder, and CLI-facing name is **`picsort`** everywhere else.
- **Version single-source-of-truth:** `picsort/__init__.py` defines `__version__`; `pyproject.toml` sources it dynamically via `[tool.setuptools.dynamic] version = {attr = "picsort.__version__"}`. Never hardcode the version anywhere else.
- **`-V`/`--version` must short-circuit** before the update check, exiftool check, mode menu, or any prompt. A `--version` call prints `picsort <__version__>` and exits 0 instantly (no network).
- **Exiftool storage:** auto-download to `%LOCALAPPDATA%\picsort\tools\exiftool.exe`, falling back to `Path.home() / ".picsort" / "tools"` when `LOCALAPPDATA` is unset. Same base dir hosts `fallback_used.log` and `update_check.json`.
- **Update check:** PyPI JSON API for `picsort-cli`, timeout 2–3 s, cached once per 24 h, silent on any failure. Never blocks startup.
- **Keep unchanged behavior:** mode selection (Media/Documents), Rich split-panel UI, media/docs extension + date-tag priority sets, hash dedup, multi-source comma input + single destination, copy-only with `shutil.copy2`, `Dest/YYYY/MonthName/DD/` structure, non-TTY fallback path.
- **ASCII-only rendered output**: `box.ASCII` everywhere; icons pure ASCII (cp1252 console).
- **Follow existing style:** `_` prefix for private helpers, UPPER_SNAKE constants, type hints on signatures, minimal comments (match existing code, don't add new ones unless the ported code has them).
- **Dev dependency:** `pytest` (already installed: 9.1.1). `rich` and `requests` already installed globally.
- **Use `py` launcher** (Python 3.14.6) for commands, matching existing repo usage.
- **Path base:** all commands run against `D:\pic-sort` (repo root). Tests use a `conftest.py` that puts `src/` on `sys.path` so `import picsort` works without installing.

---

### Task 1: Package scaffold — `src/` layout, `__init__.py`, `pyproject.toml`, `.gitignore`, test harness

**Files:**
- Create: `D:\pic-sort\src\picsort\__init__.py`
- Create: `D:\pic-sort\pyproject.toml`
- Modify: `D:\pic-sort\.gitignore`
- Create: `D:\pic-sort\tests\conftest.py`
- Create: `D:\pic-sort\tests\test_version.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `picsort.__version__ == "0.1.0"` (importable via the `src` conftest path).
  - `pyproject.toml` distribution `name = "picsort-cli"`, dynamic version, `[project.scripts] picsort = "picsort.cli:main"` (cli does not exist yet — the entry point is declared now but only exercised from Task 9).
  - A working `pytest` harness: running `py -m pytest` from repo root imports `picsort` through `src/`.

- [ ] **Step 1: Create `src/picsort/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "picsort-cli"
description = "Sort your entire photo, video & document library by date, automatically."
readme = "README.md"
requires-python = ">=3.9"
license = { text = "MIT" }
dynamic = ["version"]
dependencies = [
    "rich",
    "requests",
]

[project.scripts]
picsort = "picsort.cli:main"

[tool.setuptools.dynamic]
version = { attr = "picsort.__version__" }

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

> Note: `license = { text = "MIT" }` is the modern PEP 639 form; a warning may appear on older setuptools but is tolerated. The `[tool.pytest.ini_options]` section makes `py -m pytest` pick up `tests/` automatically.

- [ ] **Step 3: Update `.gitignore`**

Read the current `.gitignore`, then replace its full contents with:

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/

# Packaging / build output
dist/
build/
*.egg-info/

# Editor
.idea/
.vscode/

# Runtime artifacts (per-user app data is outside the repo, but keep these safe)
*.log
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
```

- [ ] **Step 5: Write the failing version-consistency test**

Create `D:\pic-sort\tests\test_version.py`:

```python
import tomllib

from pathlib import Path

import picsort


def test_picsort_imports():
    assert isinstance(picsort.__version__, str)


def test_pyproject_version_matches_init():
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    # version is sourced dynamically from picsort.__version__, so the attr
    # path must point at it.
    assert "version" in data["project"]["dynamic"]
    assert data["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "picsort.__version__"
    assert data["project"]["name"] == "picsort-cli"
    assert data["project"]["scripts"]["picsort"] == "picsort.cli:main"
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `py -m pytest tests/test_version.py -v`
Expected: 2 passed. (`tomllib` is stdlib in 3.11+; Python here is 3.14.)

- [ ] **Step 7: Commit**

```bash
git add src/picsort/__init__.py pyproject.toml .gitignore tests/
git commit -m "feat: scaffold src-layout package picsort-cli with pyproject and pytest harness"
```

---

### Task 2: `core.py` — scanning, hashing, date-reading, exiftool, copy logic

**Files:**
- Create: `D:\pic-sort\src\picsort\core.py`
- Create: `D:\pic-sort\tests\test_core.py`

**Interfaces:**
- Consumes: stdlib only (`datetime`, `hashlib`, `os`, `re`, `shutil`, `subprocess`, `sys`, `tempfile`, `time`, `zipfile`, `pathlib.Path`); optional `requests` guarded by try/except.
- Produces (names/types later tasks rely on):
  - Constants: `PARTIAL_HASH_THRESHOLD`, `PARTIAL_HASH_CHUNK`, `EXIFTOOL_PAGE_URL`, `IMAGE_EXTS`, `VIDEO_EXTS`, `DOCUMENT_EXTS`, `MEDIA_DATE_TAGS`, `DOCS_DATE_TAGS`, `MODE_CONFIGS`, `GREEN`, `YELLOW`, `RED`, `CYAN`, `DIM`.
  - `data_dir() -> Path` — per-user app-data dir (`%LOCALAPPDATA%\picsort` or `~/.picsort`).
  - `tools_exiftool() -> Path` — `data_dir()/tools/exiftool.exe`.
  - `fallback_log_path() -> Path` — `data_dir()/fallback_used.log`.
  - `ensure_exiftool() -> Path` — returns working exe path; downloads on first run; prints manual fallback and `sys.exit(1)` on failure.
  - `read_capture_date(file_path: Path, tags) -> datetime.datetime | None`.
  - `_parse_exif_datetime(value: str) -> datetime.datetime | None`.
  - `file_identity(path: Path) -> tuple`.
  - `destination_for(dest_root: Path, dt: datetime.datetime) -> Path`.
  - `unique_copy_path(dest_day_dir: Path, filename: str, src_identity) -> Path | None`.
  - `scan_sources(sources, extensions) -> generator`.
  - `log_fallback(path, dt) -> None`.
  - `_bump_type_counts(type_counts: dict, ext: str, cfg: dict) -> None`.
  - `MODE_CONFIGS` values must be byte-identical to the current `picsort.py` ones.

**Source:** all logic is moved verbatim from the current `picsort.py` (read it in full), EXCEPT the exiftool path resolution, which is retargeted from exe-relative to per-user app-data.

- [ ] **Step 1: Write failing tests for the pure-logic functions**

Create `D:\pic-sort\tests\test_core.py`:

```python
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
    # first call: free -> target
    target = core.unique_copy_path(day, "x.jpg", ident)
    assert target is not None
    assert target.exists()
    core.cache_put(day, target.name, ident)
    # second call: identical -> None (dup)
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
```

- [ ] **Step 2: Run tests to verify they fail (no core module yet)**

Run: `py -m pytest tests/test_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'picsort.core'` (and `_parse_exif_datetime` being private is fine since the test imports the module and calls by attribute).

- [ ] **Step 3: Write `src/picsort/core.py`**

Create the full module (see below). It is the non-UI half of the current `picsort.py`, adapted:

```python
#!/usr/bin/env python3
"""PicSort - core scanning, hashing, date-reading, and copy logic.

This module holds all non-UI behavior and deliberately imports nothing from
the UI layer. It does not create a module-level Console.
"""

import datetime
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

try:
    import requests  # only needed for first-run ExifTool download
except ImportError:
    requests = None

PARTIAL_HASH_THRESHOLD = 100 * 1024 * 1024   # 100 MB
PARTIAL_HASH_CHUNK = 1024 * 1024             # 1 MB each end

EXIFTOOL_PAGE_URL = "https://exiftool.org/"

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff",
    ".webp", ".heic", ".heif", ".avif", ".raw", ".cr2", ".nef",
    ".arw", ".dng", ".insv", ".insp",
}

VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v",
    ".3gp", ".webm", ".mts", ".m2ts",
}

DOCUMENT_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}

MEDIA_DATE_TAGS = [
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    "CreationDate",
]

DOCS_DATE_TAGS = [
    "CreateDate",
    "CreateTime",
    "CreationDate",
    "DateCreated",
]

GREEN = "bright_green"
YELLOW = "yellow"
RED = "bright_red"
CYAN = "bright_cyan"
DIM = "bright_black"

LOGO_ART = r"""
  ____ ___ ____     ____   ___  ____ _____
 |  _ \_ _/ ___|   / ___| / _ \|  _ \_   _|
 | |_) | | |   ____\___ \| | | | |_) || |
 |  __/| | |__|_____|__) | |_| |  _ < | |
 |_|  |___\____|   |____/ \___/|_| \_\|_|
"""

CAMERA_ICON = r"""
     _____________
    /             \
   |  __    ___   |
   | |  |  |   |  |
   | |__|  |___|  |
   |    ______    |
   |   |  ()  |   |
   |   |______|   |
    \_____________/
"""

FOLDER_ICON = r"""
 .--------------------.
 |  .----------------. |
 |  |                | |
 |  |                | |
 |  |                | |
 |  |________________| |
  \__________________/
"""

TAGLINE = "Sort your photos, videos & documents by date, automatically."

MODE_CONFIGS = {
    "media": {
        "label": "Media (Photos & Videos)",
        "extensions": IMAGE_EXTS | VIDEO_EXTS,
        "date_tags": MEDIA_DATE_TAGS,
        "icon": CAMERA_ICON,
        "accent": "bright_green",
        "dim": "bright_black",
        "types": {
            "photo": {"exts": IMAGE_EXTS,  "color": "bright_green", "label": "Photos"},
            "video": {"exts": VIDEO_EXTS,  "color": "bright_blue",  "label": "Videos"},
        },
    },
    "documents": {
        "label": "Documents (PDF, Word, Excel, PowerPoint)",
        "extensions": DOCUMENT_EXTS,
        "date_tags": DOCS_DATE_TAGS,
        "icon": FOLDER_ICON,
        "accent": "bright_cyan",
        "dim": "bright_black",
        "types": {
            "pdf":     {"exts": {".pdf"},               "color": "orange1",     "label": "PDF"},
            "word":    {"exts": {".doc", ".docx"},      "color": "bright_blue", "label": "Word"},
            "excel":   {"exts": {".xls", ".xlsx"},      "color": "bright_green","label": "Excel"},
            "ppt":     {"exts": {".ppt", ".pptx"},      "color": "bright_magenta","label": "PowerPoint"},
        },
    },
}

_TYPE_BY_EXT: dict = {}
for _cfg in MODE_CONFIGS.values():
    for _kind, _info in _cfg["types"].items():
        for _ext in _info["exts"]:
            _TYPE_BY_EXT.setdefault(_ext, (_kind, _info["label"], _info["color"]))


# ---------------------------------------------------------------------------
# Per-user app data directory (retargeted from exe-relative to per-user)
# ---------------------------------------------------------------------------

def data_dir() -> Path:
    """Per-user app-data dir hosting tools/, logs, and caches.

    Prefers %LOCALAPPDATA%\\picsort on Windows; falls back to
    ~/.picsort when the env var is missing. Never tied to an exe location.
    """
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".picsort"
    return base / "picsort"


def tools_exiftool() -> Path:
    """Absolute path to the per-user tools\\exiftool.exe."""
    return data_dir() / "tools" / "exiftool.exe"


def fallback_log_path() -> Path:
    return data_dir() / "fallback_used.log"


# ---------------------------------------------------------------------------
# First-run ExifTool auto-download (logic unchanged, destination retargeted)
# ---------------------------------------------------------------------------

def ensure_exiftool() -> Path:
    exe = tools_exiftool()
    if exe.exists():
        return exe

    from picsort.ui import console_print
    console_print(f"First-time setup: downloading ExifTool...", GREEN)
    if requests is None:
        _manual_fallback("requests module not available (re-install with: pip install requests)")
        sys.exit(1)

    tmp = Path(tempfile.mkdtemp(prefix="picsort_"))
    try:
        url = _discover_exiftool_url()
        zip_path = tmp / "exiftool.zip"
        console_print(f"  Downloading from {url} ...", GREEN)
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        extract_dir = tmp / "exiftool"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)

        candidates = list(extract_dir.rglob("exiftool*.exe"))
        if not candidates:
            _manual_fallback("downloaded zip did not contain an exe")
            sys.exit(1)
        src = candidates[0]

        src_root = src.parent
        tools_dir = data_dir() / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        for item in src_root.iterdir():
            dst = tools_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)

        e = tools_dir / "exiftool.exe"
        shutil.move(tools_dir / src.name, e)
        console_print(f"  Installed ExifTool -> {e}", GREEN)
        return e
    except (OSError, requests.RequestException, ValueError) as exc:
        _manual_fallback(str(exc))
        sys.exit(1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _discover_exiftool_url() -> str:
    from picsort.ui import console_print
    console_print(f"  Fetching {EXIFTOOL_PAGE_URL} to find current version ...", GREEN)
    resp = requests.get(EXIFTOOL_PAGE_URL, timeout=60)
    resp.raise_for_status()
    html = resp.text
    match = re.search(r'href="([^"]*exiftool-\d+(?:\.\d+)+_64\.zip[^"]*)"', html, re.IGNORECASE)
    if not match:
        raise ValueError("could not find the Windows 64-bit ExifTool download link on the page")
    return match.group(1)


def _manual_fallback(reason: str) -> None:
    from picsort.ui import console_print
    console_print(f"\n  [!] ExifTool download failed: {reason}", RED)
    console_print("  Manual setup required. Please:", YELLOW)
    console_print("    1. Download the 'Windows Executable' zip from:  https://exiftool.org/", YELLOW)
    console_print("       (use the 64-bit one, e.g. exiftool-<version>_64.zip)", YELLOW)
    console_print("    2. Extract the whole ZIP (keep the 'exiftool_files' folder!)", YELLOW)
    console_print("    3. Copy the exe AND its 'exiftool_files' folder into a 'tools' dir", YELLOW)
    console_print("       in your per-user app-data folder, renaming exiftool(-k).exe -> exiftool.exe:", YELLOW)
    console_print(f"       -> {tools_exiftool()}", YELLOW)
    console_print("       -> exiftool_files\\  (must sit right beside exiftool.exe)", YELLOW)
    console_print("  Then re-run picsort.", YELLOW)


# ---------------------------------------------------------------------------
# ExifTool metadata reading
# ---------------------------------------------------------------------------

def read_capture_date(file_path: Path, tags) -> datetime.datetime | None:
    exe = tools_exiftool()
    tag_args = []
    for t in tags:
        tag_args += ["-" + t]
    try:
        proc = subprocess.run(
            [str(exe), "-s", "-s", "-s"] + tag_args + ["-q", "-q", str(file_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    lines = proc.stdout.splitlines()
    for tag, val in zip(tags, lines):
        val = val.strip()
        if not val:
            continue
        dt = _parse_exif_datetime(val)
        if dt is not None:
            return dt
    return None


def _parse_exif_datetime(value: str) -> datetime.datetime | None:
    text = value.strip()
    text = re.sub(r"^(\d{4}):(\d{2}):(\d{2})", r"\1-\2-\3", text)
    text = re.sub(r"^(\d{4})/(\d{2})/(\d{2})", r"\1-\2-\3", text)
    text = re.sub(r"[Tt]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\.\d+", "", text)
    text = text.split("+", 1)[0].split("Z", 1)[0].strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Hashing / dedup
# ---------------------------------------------------------------------------

def file_identity(path: Path) -> tuple:
    size = path.stat().st_size
    if size <= PARTIAL_HASH_THRESHOLD:
        return ("full", hashlib.sha256(path.read_bytes()).hexdigest())

    with path.open("rb") as f:
        head_hash = hashlib.sha256()
        head = f.read(PARTIAL_HASH_CHUNK)
        head_hash.update(head)
        f.seek(max(0, size - PARTIAL_HASH_CHUNK))
        tail = f.read(PARTIAL_HASH_CHUNK)
    tail_hash = hashlib.sha256(tail).hexdigest()
    return ("partial", size, hashlib.sha256(head).hexdigest(), tail_hash)


# ---------------------------------------------------------------------------
# Destination folder + copy logic
# ---------------------------------------------------------------------------

def destination_for(dest_root: Path, dt: datetime.datetime) -> Path:
    month_name = dt.strftime("%B")
    return dest_root / str(dt.year) / month_name / f"{dt.day:02d}"


def unique_copy_path(dest_day_dir: Path, filename: str, src_identity) -> Path | None:
    dest_day_dir.mkdir(parents=True, exist_ok=True)
    for candidate in _candidate_names(dest_day_dir, filename):
        verdict = _probe(dest_day_dir, candidate, src_identity)
        if verdict == "same":
            return None
        if verdict == "free":
            cache_put(dest_day_dir, candidate, src_identity)
            return candidate
    return None


def _candidate_names(dest_day_dir: Path, filename: str):
    p = Path(filename)
    stem, ext = p.stem, p.suffix
    yield dest_day_dir / filename
    for counter in range(1, 10000):
        yield dest_day_dir / f"{stem}_{counter}{ext}"


_IDENTITY_CACHE: dict = {}


def _probe(day_dir: Path, filename: Path, identity) -> str:
    if not filename.exists():
        return "free"
    key = str(filename)
    if key in _IDENTITY_CACHE:
        return "same" if _IDENTITY_CACHE[key] == identity else "diff"
    try:
        existing_id = file_identity(filename)
    except OSError:
        return "diff"
    _IDENTITY_CACHE[key] = existing_id
    return "same" if existing_id == identity else "diff"


def cache_put(day_dir: Path, filename: Path, identity) -> None:
    _IDENTITY_CACHE[str(filename)] = identity


# ---------------------------------------------------------------------------
# Source scanning
# ---------------------------------------------------------------------------

def scan_sources(sources, extensions):
    for src in sources:
        for root, _dirs, files in os.walk(src):
            for name in files:
                if Path(name).suffix.lower() in extensions:
                    yield Path(root) / name


# ---------------------------------------------------------------------------
# Fallback logging
# ---------------------------------------------------------------------------

def log_fallback(path, dt) -> None:
    try:
        with open(fallback_log_path(), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat()} | {path} | used mtime {dt}\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Type counting
# ---------------------------------------------------------------------------

def _bump_type_counts(type_counts: dict, ext: str, cfg: dict) -> None:
    for kind, info in cfg["types"].items():
        if ext.lower() in info["exts"]:
            type_counts[kind] = type_counts.get(kind, 0) + 1
            return
```

> Implementation note: `LOGO_ART`, `CAMERA_ICON`, `FOLDER_ICON`, `TAGLINE` live here in `core.py` (matching the current single-file location) but are consumed by `ui.py` and `cli.py` as `core.LOGO_ART`, etc. This keeps the constants co-located with `MODE_CONFIGS` as in the original file.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m pytest tests/test_core.py -v`
Expected: all 7 tests pass.

- [ ] **Step 5: Syntax/pyflakes sanity check**

Run: `py -m py_compile src\picsort\core.py` then `py -c "import sys; sys.path.insert(0,'src'); import picsort.core; print('core OK')"`
Expected: `core OK`.

- [ ] **Step 6: Commit**

```bash
git add src/picsort/core.py tests/test_core.py
git commit -m "feat: add picsort.core module with scanning, hashing, date-reading, exiftool, copy logic"
```

---

### Task 3: `ui.py` — Rich console primitives and renderables

**Files:**
- Create: `D:\pic-sort\src\picsort\ui.py`
- Create: `D:\pic-sort\tests\test_ui.py`

**Interfaces:**
- Consumes: `rich` primitives; `core` constants (`GREEN`, `YELLOW`, `RED`, `CYAN`, `DIM`, `_TYPE_BY_EXT`); `core.MODE_CONFIGS` shape.
- Produces:
  - `CONSOLE` (module-level `rich.console.Console`).
  - `console_print(text="", style="", **kwargs) -> None`.
  - `_center_block(text: str) -> str`.
  - `_human_bytes(n: int) -> str`.
  - `_fmt_elapsed(seconds: float) -> str`.
  - `_drive_free(path) -> tuple | None`.
  - `_type_lookup(ext: str) -> tuple | None`.
  - `_activity_list(activity_lines: list, accent: str) -> Group`.
  - `_current_file_line(file_path, day_rel, status, is_fallback, color, mode_cfg) -> Text`.
  - `_per_type_table(type_counts: dict, mode_cfg) -> Table`.
  - `_stats_table(cfg, counts, total_files, processed, elapsed, drive_src, drive_dest) -> Table`.
  - `_progress_renderable(processed: int, total: int, style: str) -> Progress`.
  - `_right_panel(cfg, counts, type_counts, activity_lines, total, processed, start, drive_src, drive_dest) -> Panel`.
  - `_left_panel(cfg, body: Text) -> Panel`.
  - `_build_layout(cfg, left, right) -> Layout`.
  - `_legend(mode_cfg) -> Text`.
  - `_legend_text(cfg) -> Text`.
  - `_summary_panel(cfg, panel: dict, type_counts, elapsed) -> Panel`.
  - `print_summary(panel, cfg, type_counts, elapsed) -> None`.
  - Also define a `_render_text(renderable) -> str` helper (used for non-TTY / final-layout printing).

**Source:** move the Rich helpers from `picsort.py` verbatim; `console_print` and `CONSOLE` move here. The `_render_text` helper (from the previous layout-polish plan) is added as a convenience for final rendering.

- [ ] **Step 1: Write failing import/behavior test**

Create `D:\pic-sort\tests\test_ui.py`:

```python
from rich.panel import Panel
from rich.table import Table

from picsort import core, ui


def test_console_print_writes():
    ui.CONSOLE.print("hello")  # must not raise


def test_center_block_pads():
    out = ui._center_block("abc")
    assert out.strip() == "abc"
    assert out != "abc"  # has leading padding


def test_human_bytes():
    assert ui._human_bytes(0) == "0 B"
    assert ui._human_bytes(1024) == "1.0 KB"


def test_summary_panel_is_panel():
    cfg = core.MODE_CONFIGS["media"]
    panel = {"sources": 1, "scanned": 2, "copied": 2, "duplicates": 0, "fallback": 0, "errors": 0}
    p = ui._summary_panel(cfg, panel, {"photo": 2, "video": 0}, 5.0)
    assert isinstance(p, Panel)


def test_per_type_table_is_table():
    cfg = core.MODE_CONFIGS["documents"]
    t = ui._per_type_table({"pdf": 1, "word": 0, "excel": 0, "ppt": 0}, cfg)
    assert isinstance(t, Table)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m pytest tests/test_ui.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'picsort.ui'`.

- [ ] **Step 3: Write `src/picsort/ui.py`**

Create the full module (moved verbatim from `picsort.py`, plus `_render_text`):

```python
#!/usr/bin/env python3
"""PicSort - Rich console primitives and renderables (no data logic)."""

import shutil
import time
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import BarColumn, Progress
from rich.table import Table
from rich.text import Text

from picsort import core

GREEN = core.GREEN
YELLOW = core.YELLOW
RED = core.RED
CYAN = core.CYAN
DIM = core.DIM

CONSOLE = Console()

_ACTIVITY_MAX = 8


def console_print(text="", style="", **kwargs):
    """Print a plain (non-live) line, optionally styled with a rich color."""
    if isinstance(text, Text):
        CONSOLE.print(text, **kwargs)
    elif style:
        CONSOLE.print(Text(str(text), style=style), **kwargs)
    else:
        CONSOLE.print(str(text), **kwargs)


def _render_text(renderable) -> str:
    """Render a rich renderable to plain text via a throwaway Console."""
    from rich.console import Console as _Console
    tmp = _Console(width=max(80, CONSOLE.width), force_terminal=False)
    tmp.print(renderable, end="")
    return tmp.export_text()


def _human_bytes(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return str(n)


def _fmt_elapsed(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m:02d}m {s:02d}s"


def _drive_free(path: Path):
    """Return (free, total) bytes for the disk holding `path`, or None."""
    try:
        root = path if path.is_dir() else path.parent
        u = shutil.disk_usage(root)
        return u.free, u.total
    except OSError:
        return None


def _type_lookup(ext: str):
    info = core._TYPE_BY_EXT.get(ext.lower())
    if info:
        return info
    return None


def _activity_list(activity_lines: list, accent: str) -> Group:
    lines = activity_lines[-_ACTIVITY_MAX:] if len(activity_lines) > _ACTIVITY_MAX else activity_lines
    return Group(*lines) if lines else Group(Text("Scanning ...", style="dim"))


def _current_file_line(file_path: Path, day_rel: str, status: str,
                       is_fallback: bool, color: str, mode_cfg) -> Text:
    name = file_path.name
    base = Text()
    if is_fallback:
        base.append(name, style=f"{YELLOW}")
        base.append(f"  (fallback date)", style=YELLOW)
    else:
        base.append(name, style=color)
    base.append(f"  ->  {day_rel}", style="dim")
    if status == "dup":
        base.append("  (dup)", style=YELLOW)
    return base


def _per_type_table(type_counts: dict, mode_cfg) -> Table:
    table = Table(show_header=False, box=box.SIMPLE, pad_edge=False, expand=True)
    table.add_column("type")
    table.add_column("count", justify="right")
    for kind, info in mode_cfg["types"].items():
        n = type_counts.get(kind, 0)
        tbl_label = Text(f" {info['label']}", style=info["color"])
        table.add_row(tbl_label, Text(str(n), style=info["color"]))
    return table


def _stats_table(cfg, counts: dict, total_files: int, processed: int,
                 elapsed: float, drive_src, drive_dest) -> Table:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(justify="left")
    grid.add_column(justify="right")

    pct = (processed / total_files) if total_files else 0.0
    grid.add_row(
        Text("Processed", style="bold"),
        Text(f"{processed} / {total_files}   ({pct*100:.1f}%)", style="bold"),
    )
    grid.add_row(Text("Copied", style=GREEN), Text(str(counts["copied"]), style=GREEN))
    grid.add_row(Text("Duplicates", style=YELLOW), Text(str(counts["duplicates"]), style=YELLOW))
    grid.add_row(Text("Fallback date", style="yellow"), Text(str(counts["fallback"]), style="yellow"))
    grid.add_row(Text("Errors", style=RED), Text(str(counts["errors"]), style=RED))
    grid.add_row(Text("Elapsed", style=CYAN), Text(_fmt_elapsed(elapsed), style=CYAN))

    if drive_src:
        free_src = _human_bytes(drive_src[0])
        grid.add_row(Text("Source free", style="dim"), Text(free_src, style="dim"))
    if drive_dest:
        free_dest = _human_bytes(drive_dest[0])
        grid.add_row(Text("Dest free", style="dim"), Text(free_dest, style="dim"))

    return grid


def _progress_renderable(processed: int, total: int, style: str) -> Progress:
    progress = Progress(
        BarColumn(bar_width=None, style=style),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=CONSOLE,
        expand=True,
    )
    task = progress.add_task("", total=total)
    progress.update(task, completed=processed)
    return progress


def _right_panel(cfg, counts, type_counts, activity_lines, total, processed,
                 start, drive_src, drive_dest) -> Panel:
    elapsed = time.time() - start
    body = Group(
        _stats_table(cfg, counts, total, processed, elapsed, drive_src, drive_dest),
        Text("Per type:", style="bold"),
        _per_type_table(type_counts, cfg),
        Text(),
        _activity_list(activity_lines, cfg["accent"]),
        _progress_renderable(processed, total, cfg["accent"]),
    )
    return Panel(
        body,
        title=f"[{cfg['accent']}] Session - {cfg['label']}",
        border_style=cfg["accent"],
        box=box.ASCII,
        expand=True,
    )


def _left_panel(cfg, body: Text) -> Panel:
    return Panel(
        body,
        title=f"[{cfg['accent']}] {cfg['label'].split('(')[0].strip()}",
        border_style=cfg["accent"],
        box=box.ASCII,
        expand=True,
    )


def _build_layout(cfg, left: Panel, right: Panel) -> Layout:
    layout = Layout(name="root")
    layout.split_row(
        Layout(left, name="left", ratio=2),
        Layout(right, name="right", ratio=3),
    )
    return layout


def _legend(mode_cfg) -> Text:
    t = Text("Legend:  ")
    first = True
    for kind, info in mode_cfg["types"].items():
        if not first:
            t.append("   ")
        first = False
        t.append(f"# {info['label']}", style=info["color"])
    t.append("   ")
    t.append("# fallback", style=YELLOW)
    t.append("   ")
    t.append("# error", style=RED)
    return t


def _legend_text(cfg) -> Text:
    t = Text()
    for kind, info in cfg["types"].items():
        t.append(f"# {info['label']}", style=info["color"])
        t.append("\n")
    t.append("# fallback", style=YELLOW)
    t.append("\n")
    t.append("# error", style=RED)
    return t


def _summary_panel(cfg, panel: dict, type_counts: dict, elapsed) -> Panel:
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2), expand=True)
    table.add_column("key")
    table.add_column("value", justify="right")

    rows = [
        ("Mode", f"{cfg['label']}"),
        ("Source folders scanned", str(panel["sources"])),
        ("Files scanned", str(panel["scanned"])),
        ("Files copied", str(panel["copied"])),
        ("Skipped (duplicates)", str(panel["duplicates"])),
        ("Fallback date used", str(panel["fallback"])),
        ("Errors", str(panel["errors"])),
        ("Elapsed", _fmt_elapsed(elapsed)),
    ]
    for label, value in rows:
        color = RED if label.startswith("Errors") else (GREEN if label == "Mode" else None)
        table.add_row(
            Text(label, style="bold" if label == "Mode" else None),
            Text(str(value), style=color) if color else Text(str(value)),
        )

    return Panel(table, title=f"[{GREEN}] Summary - {cfg['label']}",
                 border_style=GREEN, box=box.ASCII, expand=True)


def print_summary(panel, cfg, type_counts, elapsed) -> None:
    CONSOLE.print()
    CONSOLE.print(_summary_panel(cfg, panel, type_counts, elapsed))

    parts = []
    for kind, info in cfg["types"].items():
        parts.append(Text(f"{info['label']}: {type_counts.get(kind, 0)}", style=info["color"]))
    sep = Text("    ")
    line = Text()
    for i, p in enumerate(parts):
        if i:
            line.append_text(sep)
        line.append_text(p)
    CONSOLE.print(line)
    CONSOLE.print()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m pytest tests/test_ui.py -v`
Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/picsort/ui.py tests/test_ui.py
git commit -m "feat: add picsort.ui module with console primitives and rich renderables"
```

---

### Task 4: `update_check.py` — PyPI version check with 24h cache

**Files:**
- Create: `D:\pic-sort\src\picsort\update_check.py`
- Create: `D:\pic-sort\tests\test_update_check.py`

**Interfaces:**
- Consumes: `picsort.__version__`, `core.data_dir()`, optional `requests`.
- Produces:
  - `_cache_path() -> Path` — `data_dir()/update_check.json`.
  - `_cache_fresh(cache: dict | None) -> bool` — True if cached within 24h.
  - `_compare_versions(newer: str, older: str) -> bool` — True if `newer > older` (tuple numeric compare).
  - `check_for_update(print_if_newer=True, fetch=None) -> str | None` — returns the newer version string if an update is available, else None. Never raises. Uses `requests.get(URL, timeout=(2,3))`. When `fetch` is provided (callable returning JSON), uses it instead of the network (for tests); when `print_if_newer` and a newer version is found, prints the styled notice via `ui.console_print`.

**PyPI endpoint:** `https://pypi.org/pypi/picsort-cli/json`, field `info.version`.

- [ ] **Step 1: Write failing tests**

Create `D:\pic-sort\tests\test_update_check.py`:

```python
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

    # Version on disk simulates installed version lower than latest -> update available.
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
    monkeypatch = None
    # Directly test _write_cache / _read_cache round-trip
    path = tmp_path / "update_check.json"
    update_check._write_cache(path, {"info": {"version": "1.0.0"}}, checked=time.time())
    cached = update_check._read_cache(path)
    assert cached is not None
    assert cached["info"]["version"] == "1.0.0"
```

> Note: `_compare_versions` must handle `X.Y.Z` numeric tuple comparison. `_read_cache` returns `None` on missing/corrupt file. `_write_cache(path, data, checked=...)` writes JSON `{**data, "checked_at": checked}` atomically.

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m pytest tests/test_update_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'picsort.update_check'`.

- [ ] **Step 3: Write `src/picsort/update_check.py`**

```python
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
            f"Update available: v{latest} (you have v{__version__}) - run: pipx upgrade picsort-cli",
            "yellow",
        )
    _write_cache(path, {"latest": latest}, time.time())
    return latest
```

> Note: `check_for_update` only writes the cache when an update is found (to avoid caching "check failed") — consistent with "silent on any failure". A cached successful check suppresses a repeat network hit within 24h.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m pytest tests/test_update_check.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/picsort/update_check.py tests/test_update_check.py
git commit -m "feat: add picsort.update_check module with 24h-cached PyPI version check"
```

---

### Task 5: `cli.py` — entry point, prompts, `-V/--version`, interactive flow

**Files:**
- Create: `D:\pic-sort\src\picsort\cli.py`
- Create: `D:\pic-sort\tests\test_cli.py`

**Interfaces:**
- Consumes: `core` (MODE_CONFIGS, ensure_exiftool, read_capture_date, destination_for, scan_sources, _copy_one-equivalent logic, log_fallback via cli), `ui` (all renderables + console_print + CONSOLE), `update_check.check_for_update`, `picsort.__version__`.
- Produces:
  - `main(argv=None) -> None` — the entry point referenced by `[project.scripts] picsort = "picsort.cli:main"`. When `-V` or `--version` in argv, prints `picsort <__version__>` and returns immediately (no network, no prompts).
  - `select_mode() -> str`, `print_logo() -> None`, `prompt_input(prompt, default="") -> str`, `_exit_prompt() -> None`, `_rel(dest, day_dir) -> str`, `_copy_one(file_path, day_dir) -> tuple`.
  - The non-TTY interactive flow is combined here; the TTY `Live` path moves from the old `main()`.

**Important:** `_copy_one` copies the old logic using `core.file_identity`, `core.unique_copy_path`, `shutil.copy2`. `read_capture_date` for fallback uses `core.read_capture_date`.

- [ ] **Step 1: Write failing tests for `--version` and mode selection**

Create `D:\pic-sort\tests\test_cli.py`:

```python
import io
import sys
from contextlib import redirect_stdout

import pytest

from picsort import cli


def test_version_flag_short_circuits_no_network(capsys):
    # No monkeypatching of network here: --version must print and return
    # without touching requests / prompts.
    cli.main(["--version"])
    out = capsys.readouterr().out
    assert "picsort" in out
    assert "0.1.0" in out


def test_version_short_flag(capsys):
    cli.main(["-V"])
    out = capsys.readouterr().out
    assert "0.1.0" in out


def test_select_mode_returns_valid_key(monkeypatch):
    for choice, expect in (("1", "media"), ("2", "documents")):
        monkeypatch.setattr("builtins.input", lambda *a, **k: choice)
        assert cli.select_mode() == expect
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'picsort.cli'`.

- [ ] **Step 3: Write `src/picsort/cli.py`**

Create the full module (this is the interactive flow from `picsort.py` adapted, plus `--version` short-circuit and update-check wiring):

```python
#!/usr/bin/env python3
"""PicSort - CLI entry point, prompts, and interactive flow."""

import datetime
import shutil
import sys
import time
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from picsort import __version__, core, ui
from picsort import update_check

GREEN = core.GREEN
YELLOW = core.YELLOW
RED = core.RED
CYAN = core.CYAN
DIM = core.DIM

CONSOLE = ui.CONSOLE


def _print_version() -> None:
    print(f"picsort {__version__}")


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-V" in argv or "--version" in argv:
        _print_version()
        return

    print_logo()
    update_check.check_for_update()

    mode = select_mode()
    cfg = core.MODE_CONFIGS[mode]

    core.ensure_exiftool()

    raw = prompt_input("Enter source folder path(s) (separate multiple with commas): ").strip()
    source_raw = raw
    candidates = [s.strip().strip('"').strip("'") for s in source_raw.split(",")]
    sources = []
    for s in candidates:
        if not s:
            continue
        p = Path(s)
        if p.is_dir():
            sources.append(p)
        else:
            console_print(f"  [!] Warning: source folder not found, skipping: {s}", YELLOW)

    if not sources:
        console_print("  No valid source folders provided. Exiting.", RED)
        _exit_prompt()
        return

    raw_dst = prompt_input("Enter destination folder path: ").strip()
    dest = Path(raw_dst).expanduser()
    if not str(dest).strip():
        console_print("  No destination provided. Exiting.", RED)
        _exit_prompt()
        return

    all_files = list(core.scan_sources(sources, cfg["extensions"]))
    total = len(all_files)
    if total == 0:
        console_print(f"  No {cfg['label']} files found in the given source folder(s).", YELLOW)
        console_print(f"  (Active extensions: {', '.join(sorted(e for e in cfg['extensions']))})", "dim")
        _exit_prompt()
        return

    console_print(f"  Sorting {len(sources)} source folder(s) into {dest} ...", GREEN)
    console_print(f"  Found {total} file(s).", GREEN)
    console_print("")
    console_print(ui._legend(cfg))
    console_print("")

    panel = {"sources": len(sources), "scanned": total,
             "copied": 0, "duplicates": 0, "fallback": 0, "errors": 0}
    type_counts: dict = {k: 0 for k in cfg["types"]}
    start = time.time()

    drive_src = ui._drive_free(sources[0])
    drive_dest = ui._drive_free(dest)
    tick = 0

    is_tty = sys.stdout.isatty()

    if not is_tty:
        for i, file_path in enumerate(all_files, 1):
            try:
                dt = core.read_capture_date(file_path, cfg["date_tags"])
                color = GREEN
                is_fallback = False
                if dt is None:
                    mtime = file_path.stat().st_mtime
                    dt = datetime.datetime.fromtimestamp(mtime)
                    panel["fallback"] += 1
                    core.log_fallback(file_path, dt)
                    is_fallback = True
                    color = YELLOW

                day_dir = core.destination_for(dest, dt)
                status, day_dir, err_msg = _copy_one(file_path, day_dir)
                day_rel = _rel(dest, day_dir)
                if status == "copied":
                    panel["copied"] += 1
                elif status == "dup":
                    panel["duplicates"] += 1
                elif status == "err":
                    panel["errors"] += 1

                core._bump_type_counts(type_counts, file_path.suffix, cfg)

                line = ui._current_file_line(file_path, day_rel, status, is_fallback, color, cfg)
                t_line = Text()
                t_line.append(f"[{i}/{total}] ", style=GREEN)
                t_line.append_text(line)
                if status == "err":
                    t_line.append(f"  (ERROR {err_msg})", style=RED)
                CONSOLE.print(t_line)
            except Exception as exc:  # noqa: BLE001
                panel["errors"] += 1
                core._bump_type_counts(type_counts, file_path.suffix, cfg)
                CONSOLE.print(Text(f"[{i}/{total}] ERROR {file_path}: {exc}", style=RED))
    else:
        activity_lines = []
        left_body = Text()
        left_body.append(cfg["icon"], style=cfg["accent"])
        left_body.append("\n\n")
        left_body.append_text(ui._legend_text(cfg))
        left = ui._left_panel(cfg, left_body)
        layout = ui._build_layout(cfg, left, ui._right_panel(
            cfg, panel, type_counts, activity_lines, total, 0,
            start, drive_src, drive_dest))
        try:
            with Live(layout, console=CONSOLE, refresh_per_second=10,
                      screen=False, redirect_stdout=False, get_renderable=None) as live:
                for i, file_path in enumerate(all_files, 1):
                    try:
                        dt = core.read_capture_date(file_path, cfg["date_tags"])
                        is_fallback = False
                        color = cfg["accent"]
                        if dt is None:
                            mtime = file_path.stat().st_mtime
                            dt = datetime.datetime.fromtimestamp(mtime)
                            panel["fallback"] += 1
                            core.log_fallback(file_path, dt)
                            is_fallback = True
                            color = YELLOW

                        day_dir = core.destination_for(dest, dt)
                        status, day_dir, err_msg = _copy_one(file_path, day_dir)
                        day_rel = _rel(dest, day_dir)
                        if status == "copied":
                            panel["copied"] += 1
                        elif status == "dup":
                            panel["duplicates"] += 1
                        elif status == "err":
                            panel["errors"] += 1

                        core._bump_type_counts(type_counts, file_path.suffix, cfg)

                        cur = ui._current_file_line(file_path, day_rel, status, is_fallback, color, cfg)
                        if status == "err":
                            cur.append(f"  (ERROR {err_msg})", style=RED)
                        prog = Text("-> ", style=cfg["accent"])
                        prog.append_text(cur)
                        prog.append("\n")
                        activity_lines.append(prog)
                        tick += 1
                        if tick % 50 == 0:
                            drive_src = ui._drive_free(sources[0])
                            drive_dest = ui._drive_free(dest)

                        live.update(ui._build_layout(
                            cfg, left, ui._right_panel(
                                cfg, panel, type_counts, activity_lines, total, i,
                                start, drive_src, drive_dest)))
                    except Exception as exc:  # noqa: BLE001
                        panel["errors"] += 1
                        core._bump_type_counts(type_counts, file_path.suffix, cfg)
                        errl = Text("-> ", style=cfg["accent"])
                        errl.append(Text(f"ERROR {file_path}: {exc}", style=RED))
                        errl.append("\n")
                        activity_lines.append(errl)
                        live.update(ui._build_layout(
                            cfg, left, ui._right_panel(
                                cfg, panel, type_counts, activity_lines, total, i,
                                start, drive_src, drive_dest)))
        except KeyboardInterrupt:
            CONSOLE.print(Text("\n  Cancelled by user.", style=RED))
            _exit_prompt()
            return

    if is_tty:
        left2 = ui._left_panel(cfg, ui._summary_panel(cfg, panel, type_counts, time.time() - start))
        final_layout = ui._build_layout(cfg, left2, ui._right_panel(
            cfg, panel, type_counts, activity_lines, total, len(all_files),
            start, drive_src, drive_dest))
        CONSOLE.print()
        CONSOLE.print(ui._render_text(final_layout))
        CONSOLE.print()

    ui.print_summary(panel, cfg, type_counts, time.time() - start)
    _exit_prompt()


# ---------------------------------------------------------------------------
# Prompts & helpers
# ---------------------------------------------------------------------------

def prompt_input(prompt: str, default: str = "") -> str:
    if default:
        prompt = f"{prompt} [{default}] "
    return input(prompt).strip()


def console_print(text="", style="", **kwargs):
    return ui.console_print(text, style, **kwargs)


def _center_block(text: str) -> str:
    return ui._center_block(text)


_MODE_SUBTITLES = {
    "media": "Sort photos & videos by capture date",
    "documents": "Sort PDF, Word, Excel & PowerPoint by creation date",
}


def select_mode() -> str:
    keys = list(core.MODE_CONFIGS)
    box_body = Text()
    box_body.append("Select mode:  ", style=f"bold {GREEN}")
    box_body.append("\n")
    for i, k in enumerate(keys, 1):
        box_body.append(f"[{i}] {core.MODE_CONFIGS[k]['label']}\n")
        sub_text = _MODE_SUBTITLES.get(k, "")
        if sub_text:
            box_body.append(f"     {sub_text}\n")
        box_body.append("\n")
    panel = Panel(
        box_body,
        title=f"[{GREEN}] PIC-SORT MODE",
        title_align="left",
        border_style=GREEN,
        box=box.ASCII,
        padding=(1, 2),
        width=max(0, min(70, CONSOLE.width - 4)),
    )
    CONSOLE.print(Text("\n"))
    CONSOLE.print(panel)
    while True:
        choice = input(f"  Mode [1-{len(keys)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            return keys[int(choice) - 1]
        CONSOLE.print(Text("  Invalid choice. Please try again.", style=YELLOW))


def _exit_prompt() -> None:
    try:
        input(f"\x1b[32mPress Enter to exit...\x1b[0m")
    except EOFError:
        pass


def _rel(dest: Path, day_dir: Path) -> str:
    try:
        return str(day_dir.relative_to(dest)).replace("\\", "/")
    except ValueError:
        return str(day_dir)


def _copy_one(file_path: Path, day_dir: Path):
    try:
        src_identity = core.file_identity(file_path)
        target = core.unique_copy_path(day_dir, file_path.name, src_identity)
        if target is None:
            return "dup", day_dir, None
        shutil.copy2(file_path, target)
        return "copied", day_dir, None
    except OSError as exc:
        return "err", day_dir, exc


def print_logo() -> None:
    CONSOLE.print()
    CONSOLE.print(Text(ui._center_block(core.LOGO_ART), style=GREEN))
    sub = Text()
    padding = " " * max(0, (CONSOLE.width - len(core.TAGLINE)) // 2)
    sub.append(padding + core.TAGLINE, style=f"bold {GREEN}")
    CONSOLE.print(sub)
    CONSOLE.print(Text(" " * max(0, (CONSOLE.width - 62) // 2) + "=" * 62, style="dim"))
    CONSOLE.print()
```

> Implementation caution: the old `print_logo` referenced module-local `LOGO_ART` / `TAGLINE`; those now live in `core` as `core.LOGO_ART` / `core.TAGLINE`. `_center_block` is delegated to `ui._center_block`. The `panel["scanned"]` key is set to `total` for summary display, matching the original.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m pytest tests/test_cli.py -v`
Expected: all 3 tests pass.

> The `--version` path must NOT import `requests`/hit the network. In `main`, the version check returns before `update_check.check_for_update()` is called, so no network occurs. Confirm the tests pass without network.

- [ ] **Step 5: Import smoke check**

Run: `py -c "import sys; sys.path.insert(0,'src'); from picsort.cli import main; print('cli OK')"`
Expected: `cli OK`.

- [ ] **Step 6: Commit**

```bash
git add src/picsort/cli.py tests/test_cli.py
git commit -m "feat: add picsort.cli entry point with --version flag and interactive flow"
```

---

### Task 6: Remove the old single-file `picsort.py` and run the full test suite

**Files:**
- Delete: `D:\pic-sort\picsort.py`

**Interfaces:**
- Consumes: all modules from Tasks 1–5.
- Produces: a repo with no top-level `picsort.py`; the package is exclusively under `src/picsort/`.

- [ ] **Step 1: Run the full suite first (before deletion)**

Run: `py -m pytest -v`
Expected: all tests pass (2 + 7 + 5 + 6 + 3 = 23 passed).

- [ ] **Step 2: Verify nothing still imports the top-level `picsort.py`**

Run: `Select-String -Path src\picsort\*.py -Pattern "from picsort|import picsort"` from `D:\pic-sort`
Expected: only intra-package `from picsort import ...` / `from picsort.ui import ...` etc. (these resolve to the `src` package). No top-level dependency.

- [ ] **Step 3: Delete `picsort.py`**

```bash
Remove-Item "D:\pic-sort\picsort.py"
```

- [ ] **Step 4: Re-run the suite to confirm the package is self-contained**

Run: `py -m pytest -v`
Expected: all 23 tests still pass (conftest injects `src` so `import picsort` finds the package, not the deleted file).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy single-file picsort.py in favor of src-layout package"
```

---

### Task 7: Clean up EXE cruft (chosen scope)

**Files:**
- Delete: `D:\pic-sort\build.bat`
- Delete: `D:\pic-sort\PicSort.spec`
- Delete: `D:\pic-sort\.github\workflows\build-release.yml`
- Untrack (git rm): `D:\pic-sort\dist`, `D:\pic-sort\build`, `D:\pic-sort\tools`, `D:\pic-sort\fallback_used.log` (if tracked)

**Interfaces:**
- Consumes: nothing.
- Produces: a clean repo with no PyInstaller/EXE artifacts.

- [ ] **Step 1: Identify tracked cruft**

Run: `git ls-files` from `D:\pic-sort`
Expected: a listing; note whether `dist/`, `build/`, `tools/`, `fallback_used.log`, `build.bat`, `PicSort.spec`, `.github/workflows/build-release.yml` are tracked.

- [ ] **Step 2: Delete the static build files**

```bash
Remove-Item "D:\pic-sort\build.bat", "D:\pic-sort\PicSort.spec" -Force -ErrorAction SilentlyContinue
Remove-Item "D:\pic-sort\.github\workflows\build-release.yml" -Force
```

- [ ] **Step 3: Remove tracked EXE artifacts from git (if any are tracked)**

```bash
git rm -r --ignore-unmatch dist build tools fallback_used.log
```

- [ ] **Step 4: Re-run tests and confirm nothing references the exe**

Run: `py -m pytest -q` then `Select-String -Path README.md -Pattern "\.exe|build\.bat|PicSort\.exe|GitHub Release" -SimpleMatch`
Expected: tests pass; README matches are expected at this point (rewritten in Task 9), but no remaining `.py` references to exe/build.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove PyInstaller/EXE build cruft and old release workflow"
```

---

### Task 8: GitHub Actions workflows — `ci.yml` and `publish.yml`

**Files:**
- Create: `D:\pic-sort\.github\workflows\ci.yml`
- Create: `D:\pic-sort\.github\workflows\publish.yml`

**Interfaces:**
- Consumes: the installable package (`pip install .` must succeed; `picsort --version` must work).
- Produces: CI on every push/PR and PyPI publishing on tag push via Trusted Publishing.

- [ ] **Step 1: Create `ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install package
        run: pip install .
      - name: Import check
        run: python -c "import picsort; print(picsort.__version__)"
      - name: Entry point check
        run: picsort --version
```

- [ ] **Step 2: Create `publish.yml`**

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install build
        run: pip install build
      - name: Build sdist and wheel
        run: python -m build
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

> Note: Trusted Publishing on PyPI is configured against project name **`picsort-cli`**. No API tokens are stored. The workflow filename is exactly `publish.yml`, matching the PyPI trusted-publisher settings.

- [ ] **Step 3: Validate YAML parses**

Run: `python -c "import yaml,sys; [yaml.safe_load(open(p)) for p in ['D:\\\\pic-sort\\\\.github\\\\workflows\\\\ci.yml','D:\\\\pic-sort\\\\.github\\\\workflows\\\\publish.yml']]; print('yaml OK')"` (if PyYAML installed; otherwise skip and rely on visual review)
Expected: `yaml OK` (or a manual inspection note).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/publish.yml
git commit -m "ci: add CI and PyPI trusted-publisher publish workflows"
```

---

### Task 9: README rewrite

**Files:**
- Modify: `D:\pic-sort\README.md` (full rewrite)

**Interfaces:**
- Consumes: the final package (`pipx install picsort-cli`, `picsort`, `pipx upgrade picsort-cli`).
- Produces: user-facing install/run/upgrade/uninstall/release instructions; no exe/build references.

- [ ] **Step 1: Replace README.md content**

Save the following as the new `D:\pic-sort\README.md` (replaces the EXE-based doc entirely):

```markdown
<div align="center">

# 📸 PicSort

**sort your entire photo, video & document library by date, automatically**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/picsort-cli)](https://pypi.org/project/picsort-cli/)

*A global CLI tool that sorts **photos, videos and documents** from any folders into a clean `YYYY/Month/DD` structure — safe to re-run, dedupe-aware. Pick a **Media** or **Documents** mode at startup.*

</div>

---

## ✨ Features

- 🖥️ **Two modes at startup** — choose **Media** (photos & videos) or **Documents** (PDF, Word, Excel, PowerPoint).
- 📅 **Metadata-based sorting** — **Media** reads the real capture date from EXIF / MOV metadata; **Documents** reads the **creation** date per format. Both fall back to the file's modified date only when no metadata exists.
- 🔁 **Safe to re-run** — **copy** only, never move or rename originals. Repeated runs merge into existing folders with no data loss.
- 🧬 **Hash deduplication** — every file is hashed against what's already in the destination day-folder; content-identical files are skipped. Large files (>100 MB) use a fast size + partial-hash fingerprint.
- 🔮 **Global CLI** — install once with `pipx`, then run `picsort` from any folder, any terminal.
- ⚡ **Auto-fetches ExifTool on first run** — downloads ExifTool into your per-user app-data folder automatically, then skips setup on later runs.
- 🚀 **Auto-update notice** — checks PyPI silently and shows a one-line "update available" hint when a newer release exists.
- 🎨 **Live split-panel terminal UI** (built on `rich`) — a left panel shows the mode icon (camera / folder) while a right panel drives a live progress bar, per-file-type running totals, elapsed time, drive free space, and copied/dup/fallback/error counters, with a per-type color legend.
- 📊 **Boxed summary panel** at the end with per-mode totals (e.g. `Photos: 120  Videos: 8`).

---

## 📁 How it works

Every file in your source folder(s) is read for its date (capture date for **Media**, creation date for **Documents**), then **copied** into the destination, always merged into:

```
<Destination>/
└── 2026/
    └── August/
        └── 26/
            ├── IMG_20240826_143200.jpg
            ├── IMG_20240826_143355.jpg
            └── VID_20240826_150012.mp4
```

The structure is **always** `YYYY / MonthName / DD` — regardless of which source folder a file came from. Multiple source folders feed the same flat, date-based tree.

---

## 🚀 Quick Start — Install & Run

### Prerequisites (only once)

Install `pipx` if you don't have it:

```
python -m pip install --user pipx
python -m pipx ensurepath
```

Close and reopen your terminal afterward (or `pipx ensurepath` adds the needed PATH entry for the next session).

### Install

```
pipx install picsort-cli
```

### Run

```
picsort
```

Run `picsort` from any folder, any terminal:
1. Choose a mode: **`[1] Media`** (photos & videos) or **`[2] Documents`** (PDF, Word, Excel, PowerPoint).
2. First run downloads ExifTool automatically (needs internet once; stored in your per-user app-data folder).
3. Enter your **source folder(s)** (comma-separated for multiple) and a **destination folder**.
4. Watch it copy everything into `Destination/YYYY/MonthName/DD`.

### Upgrade

```
pipx upgrade picsort-cli
```

### Uninstall

```
pipx uninstall picsort-cli
```

---

## 🔄 Notes on merge & dedup behavior

- **Never deletes or recreates** existing `Year/Month/Day` folders — it always **merges** into them.
- **Repeated runs are safe**: run the same sources against the same destination a hundred times; files already copied are skipped via hashing, so nothing is duplicated.
- **Multiple source folders** can feed the same destination over time. Files with identical content are skipped; different files that happen to share a filename get a `_1`, `_2`, … suffix **before the extension only** (e.g. `IMG_2024.jpg`, `IMG_2024_1.jpg`).
- **Never renames or moves** the original source files. PicSort only ever **copies** (`copy2`, preserving timestamps).
- **Metadata-first**: dates come from ExifTool metadata; only files with no readable metadata fall back to the file's modified date. Any fallback use is logged to `fallback_used.log` in your per-user app-data folder.

---

## 🚀 Releasing a New Version (maintainers)

1. Bump `__version__` in `src/picsort/__init__.py` (e.g. `0.1.0` → `0.2.0`).
2. Commit the change.
3. Tag and push:

```
git tag v0.2.0
git push origin v0.2.0
```

GitHub Actions builds the package and publishes to PyPI **automatically** via Trusted Publishing (OIDC) — no tokens required. The package name on PyPI is `picsort-cli`; the installed command stays `picsort`.

---

## 🛠 Troubleshooting

### `picsort: command not found` after install
Close and reopen your terminal, or re-run:

```
python -m pipx ensurepath
```

and restart the terminal.

### Internet required on first run
The first run downloads ExifTool automatically into your per-user app-data folder. To find the **current** version (versions rotate, old links stop working), PicSort scrapes exiftool.org for the latest Windows 64-bit download link instead of hardcoding a version. If you're offline or the site is unreachable, PicSort prints manual instructions:
1. Download the **Windows Executable** zip (64-bit) from https://exiftool.org
2. Extract the whole ZIP — **keep the `exiftool_files` folder** alongside it
3. Copy the exe **and** the `exiftool_files` folder into `<user-app-data>\picsort\tools\`, renaming `exiftool(-k).exe` → `exiftool.exe`
4. Re-run `picsort`.

### ❓ Files sorted by the wrong date
Some files (esp. screen recordings, edited exports, or files stripped of metadata) have no readable capture date. PicSort falls back to the file's **modified date** and logs it in `fallback_used.log`. If that's wrong, correct the file's modified timestamp and re-run — already-copied files are skipped, so use a fresh destination folder to re-sort.

---

## 📸 Screenshot / Demo

*(Add a screenshot or animated GIF of the terminal output here.)*

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.
```

- [ ] **Step 2: Verify naming consistency (package = picsort-cli only in install/upgrade/uninstall)**

Run: `Select-String -Path README.md -Pattern "picsort-cli"`; review each occurrence is in an install/upgrade/uninstall/release/package-name context, not as the run command.
Expected: `picsort-cli` appears in pipx install/upgrade/uninstall and the note; the run command is `picsort`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for PyPI pipx install/run/upgrade/uninstall"
```

---

### Task 10: Local verification (§10 of spec) before tagging

**Files:**
- No source edits. Creates temp verification artifacts in the OS temp dir (outside the repo).

**Interfaces:**
- Consumes: the built package (`pip install -e .` + `picsort` entry point).
- Produces: confirmation that the entry point resolves globally and exiftool downloads to the new per-user app-data location.

- [ ] **Step 1: Editable install and `--version`**

```bash
py -m pip install -e .
picsort --version
```
Expected: `picsort 0.1.0` printed instantly (no network delay).

- [ ] **Step 2: Confirm import after install**

Run: `py -c "import picsort; print(picsort.__version__)"`
Expected: `0.1.0`.

- [ ] **Step 3: Run from a different folder — confirm entry point resolves**

Create and use the OS temp dir (pre-approved external dir):
```bash
py -c "import os; print(os.environ['TEMP'])"
```
Then `cd` via workdir to that folder and run `picsort --version` again — it must work from outside the repo, proving the global script resolves.

- [ ] **Step 4: Confirm exiftool downloads to the per-user app-data path**

Run `picsort` from the temp folder with piped inputs (Media mode, a tiny source, a fresh destination) and confirm ExifTool is downloaded to the app-data dir:
```powershell
$temp = $env:TEMP
New-Item -ItemType Directory -Force -Path "$temp\picsort_src" | Out-Null
Set-Content -Path "$temp\picsort_src\sample.jpg" -Value "test" -Encoding Byte
Remove-Item -Recurse -Force "$temp\picsort_dest" -ErrorAction SilentlyContinue
"1`n$temp\picsort_src`n$temp\picsort_dest`n`n" | picsort 2>&1 | Select-Object -First 5
Test-Path (Join-Path $env:LOCALAPPDATA "picsort\tools\exiftool.exe")
```
Expected: the run prints the banner + first-run download lines; `Test-Path` returns `True`, confirming exiftool landed at `%LOCALAPPDATA%\picsort\tools\exiftool.exe`.

> If the machine is offline, this step fails to download (expected) — that's the graceful manual-fallback path. Document it but move on; the retarget assertion is that `tools_exiftool()` returns the app-data path and `data_dir()` reports `%LOCALAPPDATA%\picsort`.

- [ ] **Step 5: Clean up temp artifacts**

```powershell
Remove-Item -Recurse -Force "$env:TEMP\picsort_src", "$env:TEMP\picsort_dest" -ErrorAction SilentlyContinue
```

- [ ] **Step 6: Full test suite one final time**

Run: `py -m pytest -q`
Expected: 23 passed.

- [ ] **Step 7: Commit any leftover docs (README/License) or plan**

```bash
git status
```
Expected: clean (all work committed). If `LICENSE` was never updated, leave as-is (MIT already present).

- [ ] **Step 8: Do NOT tag without explicit user confirmation**

Only the user tags and pushes v0.1.0 (per spec §10). Flag the completion. Do not run `git tag` or `git push` on your own.

---

## Self-Review Notes

- **Spec coverage**
  - §1 package split (`__init__/cli/core/ui/update_check`) → Tasks 1–5.
  - §2 pyproject (name `picsort-cli`, dynamic version from init, scripts entry) → Task 1 Step 2 + Task 1 test.
  - §3 publish.yml (Trusted Publishing, OIDC, tag trigger, ubuntu, filename exact) → Task 8.
  - §4 ci.yml (install/import/--version on push/PR) → Task 8.
  - §5 exiftool retarget to `%LOCALAPPDATA%\picsort\tools` w/ `~/.picsort` fallback → Task 2 `data_dir`/`tools_exiftool` + Task 10.
  - §6 update check (PyPI JSON for picsort-cli, 2–3s timeout, 24h cache, silent fail, styled notice, runs before mode select) → Task 4 + Task 5 (call order in `main`).
  - §7 README rewrite → Task 9.
  - §8 keep-unchanged behavior → Tasks 2/3/5 preserve exact logic; tests guard it.
  - §9 cleanup (remove all EXE cruft) → Task 7.
  - §10 local verification before tagging → Task 10.
  - `--version` short-circuit before update/exiftool/menu → Task 5 `main` + tests (Task 5 Step 1) + Task 10.
- **Placeholder scan:** every code-bearing step includes full code. No TBD/TODO. The YAML validate step has an explicit skip-and-note fallback.
- **Type consistency:** `data_dir()`, `tools_exiftool()`, `fallback_log_path()` defined in Task 2 and used in Tasks 4/5. `console_print`, `CONSOLE`, `_center_block`, `_legend`, `_summary_panel`, `_right_panel`, `_left_panel`, `_build_layout`, `_current_file_line`, `_per_type_table`, `_stats_table`, `_progress_renderable`, `_legend_text`, `_render_text`, `_drive_free`, `_human_bytes`, `_fmt_elapsed` exposed by Task 3 and consumed by Task 5. `core.MODE_CONFIGS`, `core.scan_sources`, `core.read_capture_date`, `core.destination_for`, `core.file_identity`, `core.unique_copy_path`, `core.log_fallback`, `core._bump_type_counts`, `core.LOGO_ART`, `core.TAGLINE`, `core.GREEN/YELLOW/RED/CYAN/DIM` consumed by Task 5. `update_check.check_for_update()` (default `fetch=None`) consumed by Task 5.
- **Import cycle check:** `ui.py` imports `core` (constants/types) but `core.py` imports `ui` only lazily inside `ensure_exiftool`/`_discover_exiftool_url`/`_manual_fallback` (function-local `from picsort.ui import console_print`) to avoid a top-level cycle. `cli.py` imports both. `update_check.py` imports `core` and lazily `ui` inside `check_for_update`. This breaks the would-be `core ↔ ui` cycle.
- **Test count reference:** 2 (version) + 7 (core) + 5 (ui) + 6 (update_check) + 3 (cli) = 23.
