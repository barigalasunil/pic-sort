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
    ".arw", ".dng", ".insv", ".insp",   # Insta360
}

VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v",
    ".3gp", ".webm", ".mts", ".m2ts",   # camcorder / GoPro AVCHD
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

THEME = {
    "header":   "#61AFEF",
    "success":  "#98C379",
    "warning":  "#E5C07B",
    "fallback": "#D19A66",
    "error":    "#E06C75",
    "dim":      "#5C6370",
    "panel_bg": "#282828",
    "teal":     "#56B6C2",
    "purple":   "#C678DD",
}

GREEN = THEME["success"]
YELLOW = THEME["warning"]
RED = THEME["error"]
DIM = THEME["dim"]
FALLBACK = THEME["fallback"]

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
        "accent": THEME["teal"],
        "dim": THEME["dim"],
        "types": {
            "photo": {"exts": IMAGE_EXTS,  "color": THEME["success"], "label": "Photos"},
            "video": {"exts": VIDEO_EXTS,  "color": THEME["header"],  "label": "Videos"},
        },
    },
    "documents": {
        "label": "Documents (PDF, Word, Excel, PowerPoint)",
        "extensions": DOCUMENT_EXTS,
        "date_tags": DOCS_DATE_TAGS,
        "icon": FOLDER_ICON,
        "accent": THEME["purple"],
        "dim": THEME["dim"],
        "types": {
            "pdf":     {"exts": {".pdf"},             "color": THEME["error"],   "label": "PDF"},
            "word":    {"exts": {".doc", ".docx"},    "color": THEME["header"],  "label": "Word"},
            "excel":   {"exts": {".xls", ".xlsx"},    "color": THEME["success"], "label": "Excel"},
            "ppt":     {"exts": {".ppt", ".pptx"},    "color": THEME["purple"],  "label": "PowerPoint"},
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
