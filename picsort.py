#!/usr/bin/env python3
"""
PicSort - organize your entire photo & video library by date, automatically.

PicSort is a single-file, terminal-based tool that:
  * Recursively scans one or more source folders.
  * Reads each file's capture date from EXIF/MOV metadata via ExifTool.
  * Copies every file (never moves, never renames beyond collision suffixes)
    into a single destination merged into:  <Dest>/YYYY/MonthName/DD/.
  * De-duplicates via hashing so repeated / multi-source runs stay safe.

Packaged as a single portable .exe with PyInstaller (see build.bat). On first
run the tool auto-downloads ExifTool into a `tools/` folder next to the exe.

Early tool-cancel:  Ctrl+C at any prompt or during processing.
"""

import datetime
import hashlib
import json
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

try:
    from colorama import just_fix_windows_console
    just_fix_windows_console()
except Exception:
    pass

# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

# ExifTool metadata tags to try, in priority order.
DATE_TAGS = [
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    "CreationDate",
]

# Image file extensions we care about.
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff",
    ".webp", ".heic", ".heif", ".avif", ".raw", ".cr2", ".nef",
    ".arw", ".dng", ".insv", ".insp",   # Insta360
}

# Video file extensions we care about.
VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v",
    ".3gp", ".webm", ".mts", ".m2ts",   # camcorder / GoPro AVCHD
}

# Files larger than this get a fast partial hash (size + first+last 1MB)
# instead of a full SHA-256, to keep dedup fast on multi-GB videos.
PARTIAL_HASH_THRESHOLD = 100 * 1024 * 1024   # 100 MB
PARTIAL_HASH_CHUNK = 1024 * 1024             # 1 MB each end

EXIFTOOL_PAGE_URL = "https://exiftool.org/"  # homepage scraped to find the current download URL

GREEN = "\x1b[32m"
DIM_GREEN = "\x1b[32;2m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
CYAN = "\x1b[36m"
RESET = "\x1b[0m"
BOLD = "\x1b[1m"


# ---------------------------------------------------------------------------
# Exe-relative path resolution (works frozen via PyInstaller AND from source)
# ---------------------------------------------------------------------------

def app_dir() -> Path:
    """Return the folder PicSort considers "home" (next to the exe/script).

    When frozen by PyInstaller, sys.executable is the .exe and its folder is
    the true app folder. When run from source, fall back to the script dir.
    Never use __file__ for the app folder once packaged - it resolves to a
    temp _MEIPASS extraction dir.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(os.path.abspath(__file__)).resolve().parent


def tools_exiftool() -> Path:
    """Absolute path to tools\\exiftool.exe, always relative to the exe."""
    return app_dir() / "tools" / "exiftool.exe"


def last_used_path() -> Path:
    return app_dir() / "last_used.json"


def fallback_log_path() -> Path:
    return app_dir() / "fallback_used.log"


# ---------------------------------------------------------------------------
# Matrix-style terminal UI helpers
# ---------------------------------------------------------------------------

def c(color: str, text: str) -> str:
    """Wrap text in an ANSI color for terminals that support it."""
    return f"{color}{text}{RESET}"


def print_banner() -> None:
    """Stylized ASCII PIC-SORT banner in bright green."""
    banner = r"""
  ____ ___ ____     ____   ___  ____ _____ 
 |  _ \_ _/ ___|   / ___| / _ \|  _ \_   _|
 | |_) | | |   ____\___ \| | | | |_) || |  
 |  __/| | |__|_____|__) | |_| |  _ < | |  
 |_|  |___\____|   |____/ \___/|_| \_\|_|  
"""
    print(c(GREEN, banner))
    print(c(GREEN, BOLD + "  sort your entire photo & video library by date, automatically"))
    print(c(DIM_GREEN, "  " + "=" * 62))
    print()


def print_summary(panel: dict) -> None:
    """Boxed summary panel in the Matrix theme."""
    width = 56
    print()
    print(c(GREEN, "  " + "+" + "-" * (width - 2) + "+"))
    print(c(GREEN, "  |") + c(CYAN, BOLD + "  Summary".ljust(width - 4)) + c(GREEN, "|"))
    print(c(GREEN, "  |" + " " * (width - 2) + "|"))

    rows = [
        ("Source folders scanned", str(panel["sources"])),
        ("Files scanned", str(panel["scanned"])),
        ("Files copied", str(panel["copied"])),
        ("Skipped (duplicates)", str(panel["duplicates"])),
        ("Fallback date used", str(panel["fallback"])),
        ("Errors", str(panel["errors"])),
    ]
    for label, value in rows:
        color = YELLOW if label.startswith("Errors") else GREEN
        line = f"  |  {label:<22}{value:>24}  |"
        print(c(GREEN, "  |") + c(color, line.strip(" |")) + c(GREEN, "  |"))
    print(c(GREEN, "  |" + " " * (width - 2) + "|"))
    print(c(GREEN, "  " + "+" + "-" * (width - 2) + "+"))
    print()


# ---------------------------------------------------------------------------
# First-run ExifTool auto-download
# ---------------------------------------------------------------------------

def ensure_exiftool() -> Path:
    """Return the path to a working exiftool.exe, downloading if necessary.

    Returns the path on success. On failure prints manual fallback
    instructions and exits cleanly (never hard-crashes the user's run).
    """
    exe = tools_exiftool()
    if exe.exists():
        return exe

    print(c(GREEN, "First-time setup: downloading ExifTool..."))
    if requests is None:
        _manual_fallback("requests module not available (re-install with: pip install requests)")
        sys.exit(1)

    tmp = Path(tempfile.mkdtemp(prefix="picsort_"))
    try:
        url = _discover_exiftool_url()
        zip_path = tmp / "exiftool.zip"
        print(c(GREEN, f"  Downloading from {url} ..."))
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        extract_dir = tmp / "exiftool"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)

        # The zip contains exiftool(-k).exe nested under a version folder;
        # search recursively (rglob) to find it regardless of layout.
        candidates = list(extract_dir.rglob("exiftool*.exe"))
        if not candidates:
            _manual_fallback("downloaded zip did not contain an exe")
            sys.exit(1)
        src = candidates[0]

        # IMPORTANT: the Windows exe (exiftool(-k).exe) is a small launcher
        # that REQUIRES its companion "exiftool_files" folder alongside it.
        # So we install the entire extracted distribution into tools/, then
        # rename the launcher to exiftool.exe in place. Result:
        #   tools/exiftool.exe
        #   tools/exiftool_files/
        #   tools/README.txt
        src_root = src.parent
        tools_dir = app_dir() / "tools"
        tools_dir.mkdir(exist_ok=True)
        for item in src_root.iterdir():
            dst = tools_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)

        e = tools_dir / "exiftool.exe"
        shutil.move(tools_dir / src.name, e)  # rename exiftool(-k).exe -> exiftool.exe
        print(c(GREEN, f"  Installed ExifTool -> {e}"))
        return e
    except (OSError, requests.RequestException, ValueError) as exc:
        _manual_fallback(str(exc))
        sys.exit(1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _discover_exiftool_url() -> str:
    """Dynamically find the current Windows 64-bit ExifTool download URL.

    Rather than hardcoding a version number in the URL (exiftool.org rotates
    versions and old URLs go 404), we fetch the homepage and extract the href
    of the "64-bit" Windows executable zip (e.g. exiftool-13.59_64.zip).
    Download links currently point at SourceForge; requests follows the
    redirect to the actual file. Raises ValueError if the link can't be found.
    """
    print(c(GREEN, f"  Fetching {EXIFTOOL_PAGE_URL} to find current version ..."))
    resp = requests.get(EXIFTOOL_PAGE_URL, timeout=60)
    resp.raise_for_status()
    html = resp.text

    # The 64-bit Windows link looks like:
    #   <a href=".../exiftool-<ver>_64.zip/download"> exiftool-<ver>_64.zip</a>
    match = re.search(r'href="([^"]*exiftool-\d+(?:\.\d+)+_64\.zip[^"]*)"', html, re.IGNORECASE)
    if not match:
        raise ValueError("could not find the Windows 64-bit ExifTool download link on the page")
    return match.group(1)


def _manual_fallback(reason: str) -> None:
    print(c(RED, f"\n  [!] ExifTool download failed: {reason}"))
    print(c(YELLOW, "  Manual setup required. Please:"))
    print(c(YELLOW, "    1. Download the 'Windows Executable' zip from:  https://exiftool.org/"))
    print(c(YELLOW, "       (use the 64-bit one, e.g. exiftool-<version>_64.zip)"))
    print(c(YELLOW, "    2. Extract the whole ZIP (keep the 'exiftool_files' folder!)"))
    print(c(YELLOW, "    3. Copy the exe AND its 'exiftool_files' folder into a 'tools' dir"))
    print(c(YELLOW, "       next to PicSort.exe, renaming exiftool(-k).exe -> exiftool.exe:"))
    print(c(YELLOW, f"       -> {tools_exiftool()}"))
    print(c(YELLOW, "       -> exiftool_files\\  (must sit right beside exiftool.exe)"))
    print(c(YELLOW, "  Then re-run PicSort."))


# ---------------------------------------------------------------------------
# ExifTool metadata reading
# ---------------------------------------------------------------------------

def read_capture_date(file_path: Path) -> datetime.datetime | None:
    """Read the capture date of an image/video via ExifTool.

    Tags are checked in DATE_TAGS priority order; the first parseable value
    wins. Returns a naive datetime or None if nothing usable was found.
    """
    exe = tools_exiftool()
    tags = DATE_TAGS
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
    """Parse an EXIF-ish datetime string; tolerant of common quirks.

    Handles the classic "2024:08:26 14:30:00" colon format, ISO-style with a
    'T' separator, fractional seconds, and trailing timezone suffixes.
    """
    text = value.strip()
    # Common EXIF style uses colons between date parts:  2024:08:26 14:30:00
    text = re.sub(r"^(\d{4}):(\d{2}):(\d{2})", r"\1-\2-\3", text)
    # Also tolerate forward slashes:  2024/08/26 ...
    text = re.sub(r"^(\d{4})/(\d{2})/(\d{2})", r"\1-\2-\3", text)
    # Normalise 'T' separator and collapse whitespace.
    text = re.sub(r"[Tt]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    # Drop fractional seconds like .123456 and timezone suffixes (+02:00 / Z).
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
    """Return a comparable identity tuple for a file for dedup purposes.

    Small/medium files (<=100MB): full SHA-256 for a strong guarantee.
    Large files (>100MB): (size, first-1MB hash, last-1MB hash) which is much
    faster on multi-GB videos while still being a strong fingerprint.
    """
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
    """Compute <dest>/YYYY/MonthName/DD regardless of source."""
    month_name = dt.strftime("%B")
    return dest_root / str(dt.year) / month_name / f"{dt.day:02d}"


def unique_copy_path(dest_day_dir: Path, filename: str, src_identity) -> Path | None:
    """Determine destination path, handling collisions and dedup.

    Returns the target path to copy to, or None if a content-identical file
    already exists there (i.e. skip: it's a duplicate).
    """
    dest_day_dir.mkdir(parents=True, exist_ok=True)

    for candidate in _candidate_names(dest_day_dir, filename):
        verdict = _probe(dest_day_dir, candidate, src_identity)
        if verdict == "same":
            return None            # identical content already present -> dup
        if verdict == "free":
            cache_put(dest_day_dir, candidate, src_identity)
            return candidate
        # verdict == "diff": name taken by a different file -> try next name
    return None  # unreachable (generator is bounded)


def _candidate_names(dest_day_dir: Path, filename: str):
    """Yield candidate destination names: exact, then _1, _2, ... before ext.

    Bounded to a generous maximum to avoid an infinite loop if a day-folder
    somehow holds >10000 files sharing one base name.
    """
    p = Path(filename)
    stem, ext = p.stem, p.suffix
    yield dest_day_dir / filename
    for counter in range(1, 10000):
        yield dest_day_dir / f"{stem}_{counter}{ext}"


# In-memory cache of (day_dir, filename) -> identity, to dedup within one run
# even when scanning the same day-folder repeatedly across sources.
_IDENTITY_CACHE: dict = {}


def _probe(day_dir: Path, filename: Path, identity) -> str:
    """Classify a candidate destination path vs `identity`.

    Returns one of:
      "same" - an identical file already exists here (duplicate).
      "diff" - a different file occupies this name (need collision suffix).
      "free" - the name is available to use.
    """
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
# Last-used persistence
# ---------------------------------------------------------------------------

def load_last_used():
    try:
        with open(last_used_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_last_used(sources, destination):
    try:
        with open(last_used_path(), "w", encoding="utf-8") as f:
            json.dump({"sources": sources, "destination": destination}, f, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Source scanning
# ---------------------------------------------------------------------------

def scan_sources(sources):
    """Yield every image/video file under the given source folders."""
    exts = IMAGE_EXTS | VIDEO_EXTS
    for src in sources:
        for root, _dirs, files in os.walk(src):
            for name in files:
                if Path(name).suffix.lower() in exts:
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
# Main interactive flow
# ---------------------------------------------------------------------------

def prompt_input(prompt: str, default: str = "") -> str:
    if default:
        prompt = f"{prompt} [{default}] "
    return input(prompt).strip()


def main() -> None:
    print_banner()
    ensure_exiftool()

    last = load_last_used()
    default_src = ", ".join(last.get("sources", []))
    default_dst = last.get("destination", "")

    # --- Source input -----------------------------------------------------
    raw = prompt_input("Enter source folder path(s) (separate multiple with commas): ", default_src).strip()
    source_raw = raw or default_src
    candidates = [s.strip().strip('"').strip("'") for s in source_raw.split(",")]
    sources = []
    for s in candidates:
        if not s:
            continue
        p = Path(s)
        if p.is_dir():
            sources.append(p)
        else:
            print(c(YELLOW, f"  [!] Warning: source folder not found, skipping: {s}"))

    if not sources:
        print(c(RED, "  No valid source folders provided. Exiting."))
        _exit_prompt()
        return

    # --- Destination input ------------------------------------------------
    raw_dst = prompt_input("Enter destination folder path: ", default_dst).strip()
    dest = Path(raw_dst or default_dst).expanduser()
    if not str(dest).strip():
        print(c(RED, "  No destination provided. Exiting."))
        _exit_prompt()
        return

    save_last_used([str(s) for s in sources], str(dest))

    # --- Process -----------------------------------------------------------
    print()
    print(c(GREEN, f"  Sorting {len(sources)} source folder(s) into {dest} ..."))
    all_files = list(scan_sources(sources))
    total = len(all_files)
    print(c(GREEN, f"  Found {total} image/video file(s)."))
    print()

    panel = {"sources": len(sources), "scanned": total,
             "copied": 0, "duplicates": 0, "fallback": 0, "errors": 0}

    for i, file_path in enumerate(all_files, 1):
        try:
            dt = read_capture_date(file_path)
            if dt is None:
                mtime = file_path.stat().st_mtime
                dt = datetime.datetime.fromtimestamp(mtime)
                panel["fallback"] += 1
                log_fallback(file_path, dt)
                color = DIM_GREEN
            else:
                color = GREEN

            day_dir = destination_for(dest, dt)
            status, day_rel = _copy_one(file_path, day_dir)
            if status == "copied":
                panel["copied"] += 1
            elif status == "dup":
                panel["duplicates"] += 1
            elif status == "err":
                panel["errors"] += 1

            line = f"{c(GREEN, f'[{i}/{total}]')} {color}{file_path.name} -> {c(CYAN, day_rel)}"
            if status == "err":
                line += c(RED, "  (ERROR)")
            elif status == "dup":
                line += c(YELLOW, "  (dup)")
            print(line)
        except Exception as exc:  # noqa: BLE001 - keep going on any single-file failure
            panel["errors"] += 1
            print(f"{c(GREEN, f'[{i}/{total}]')} {c(RED, 'ERROR')} {file_path}: {exc}")

    print_summary(panel)
    _exit_prompt()


def _copy_one(file_path: Path, day_dir: Path):
    """Copy a single file handling dedup + collision rename.

    Returns (status, day_rel) where status is one of "copied"/"dup"/"err" and
    day_rel is the destination sub-path (e.g. "2026/August/26") for display.
    """
    try:
        src_identity = file_identity(file_path)
        target = unique_copy_path(day_dir, file_path.name, src_identity)
        if target is None:
            return "dup", _rel(day_dir)
        shutil.copy2(file_path, target)
        return "copied", _rel(day_dir)
    except OSError as exc:
        return "err", f"{_rel(day_dir)}  ({exc})"


def _rel(day_dir: Path) -> str:
    """Return the display sub-path of a day folder (e.g. 2026/August/26)."""
    return str(day_dir)


def _exit_prompt() -> None:
    input(c(GREEN, "\nPress Enter to exit..."))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c(RED, "\n  Cancelled by user."))
        try:
            input(c(GREEN, "\nPress Enter to exit..."))
        except EOFError:
            pass
