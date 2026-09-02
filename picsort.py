#!/usr/bin/env python3
"""
PicSort - organize photos, videos, and documents by date, automatically.

PicSort is a single-file, terminal-based tool that:
  * Recursively scans one or more source folders.
  * Reads each file's capture/creation date from metadata via ExifTool.
  * Copies every file (never moves, never renames beyond collision suffixes)
    into a single destination merged into:  <Dest>/YYYY/MonthName/DD/.
  * De-duplicates via hashing so repeated / multi-source runs stay safe.

Two modes (soon to be combinable):
  * Media     - photos (.jpg .png .heic .raw ...) and videos (.mp4 .mov ...)
  * Documents - PDF, Word, Excel, PowerPoint

Each mode is described by an entry in MODE_CONFIGS (extensions, date-tag
priority, icon, accent color, per-type colors), so a future *combined*
mode can be added without restructuring the core scan/copy logic.

Packaged as a single portable .exe with PyInstaller (see build.bat). On first
run the tool auto-downloads ExifTool into a `tools/` folder next to the exe.

Early tool-cancel:  Ctrl+C at any prompt or during processing.
"""

import datetime
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

try:
    import requests  # only needed for first-run ExifTool download
except ImportError:
    requests = None

from rich import box
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

# Files larger than this get a fast partial hash (size + first+last 1MB)
# instead of a full SHA-256, to keep dedup fast on multi-GB videos.
PARTIAL_HASH_THRESHOLD = 100 * 1024 * 1024   # 100 MB
PARTIAL_HASH_CHUNK = 1024 * 1024             # 1 MB each end

EXIFTOOL_PAGE_URL = "https://exiftool.org/"  # homepage scraped to find the current download URL

# Every file is copied into <Dest>/YYYY/MonthName/DD regardless of source.
TABLE_HEADERS = ("Copied", "Duplicates", "Fallback", "Errors")

# Image file extensions.
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff",
    ".webp", ".heic", ".heif", ".avif", ".raw", ".cr2", ".nef",
    ".arw", ".dng", ".insv", ".insp",   # Insta360
}

# Video file extensions.
VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v",
    ".3gp", ".webm", ".mts", ".m2ts",   # camcorder / GoPro AVCHD
}

# Document file extensions.
DOCUMENT_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}

# ExifTool priority order for reading a file's date in each mode.
# Media mode reads the *capture* date (EXIF/MOV metadata).
MEDIA_DATE_TAGS = [
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    "CreationDate",
]

# Documents use *creation* date as primary. Different document formats expose
# it under different tags (PDF: CreateDate / PDF:ModifyDate; Office OpenXML
# and OLE binary docs expose CreateDate / CreateTime / CreationDate). These
# are all creation-oriented; we never prefer a "modified" tag over creation.
DOCS_DATE_TAGS = [
    "CreateDate",
    "CreateTime",
    "CreationDate",
    "DateCreated",
]

# ASCII art rendered per mode (icon of the day) and the startup wordmark.
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

# ---------------------------------------------------------------------------
# Mode configuration.  Add a mode here (or a combined one) without touching
# the core scan/copy path - the driver only reads "extensions"/"date_tags".
# ---------------------------------------------------------------------------

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
            "pdf":     {"exts": {".pdf"},               "color": "orange1",    "label": "PDF"},
            "word":    {"exts": {".doc", ".docx"},      "color": "bright_blue", "label": "Word"},
            "excel":   {"exts": {".xls", ".xlsx"},      "color": "bright_green","label": "Excel"},
            "ppt":     {"exts": {".ppt", ".pptx"},      "color": "bright_magenta","label": "PowerPoint"},
        },
    },
}

# Type lookup: suffix -> (kind key, config) built once from MODE_CONFIGS.
_TYPE_BY_EXT: dict = {}
for _cfg in MODE_CONFIGS.values():
    for _kind, _info in _cfg["types"].items():
        for _ext in _info["exts"]:
            _TYPE_BY_EXT.setdefault(_ext, (_kind, _info["label"], _info["color"]))

GREEN = "bright_green"
YELLOW = "yellow"
RED = "bright_red"
CYAN = "bright_cyan"
DIM = "bright_black"

CONSOLE = Console()


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


def fallback_log_path() -> Path:
    return app_dir() / "fallback_used.log"


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
        # rename the launcher to exiftool.exe in place.
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
        console_print(f"  Installed ExifTool -> {e}", GREEN)
        return e
    except (OSError, requests.RequestException, ValueError) as exc:
        _manual_fallback(str(exc))
        sys.exit(1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _discover_exiftool_url() -> str:
    """Dynamically find the current Windows 64-bit ExifTool download URL."""
    console_print(f"  Fetching {EXIFTOOL_PAGE_URL} to find current version ...", GREEN)
    resp = requests.get(EXIFTOOL_PAGE_URL, timeout=60)
    resp.raise_for_status()
    html = resp.text

    match = re.search(r'href="([^"]*exiftool-\d+(?:\.\d+)+_64\.zip[^"]*)"', html, re.IGNORECASE)
    if not match:
        raise ValueError("could not find the Windows 64-bit ExifTool download link on the page")
    return match.group(1)


def _manual_fallback(reason: str) -> None:
    console_print(f"\n  [!] ExifTool download failed: {reason}", RED)
    console_print("  Manual setup required. Please:", YELLOW)
    console_print("    1. Download the 'Windows Executable' zip from:  https://exiftool.org/", YELLOW)
    console_print("       (use the 64-bit one, e.g. exiftool-<version>_64.zip)", YELLOW)
    console_print("    2. Extract the whole ZIP (keep the 'exiftool_files' folder!)", YELLOW)
    console_print("    3. Copy the exe AND its 'exiftool_files' folder into a 'tools' dir", YELLOW)
    console_print("       next to PicSort.exe, renaming exiftool(-k).exe -> exiftool.exe:", YELLOW)
    console_print(f"       -> {tools_exiftool()}", YELLOW)
    console_print("       -> exiftool_files\\  (must sit right beside exiftool.exe)", YELLOW)
    console_print("  Then re-run PicSort.", YELLOW)


# ---------------------------------------------------------------------------
# ExifTool metadata reading
# ---------------------------------------------------------------------------

def read_capture_date(file_path: Path, tags) -> datetime.datetime | None:
    """Read a file's date via ExifTool.

    `tags` is the mode's date-tag priority list; the first parseable value
    wins. Returns a naive datetime or None if nothing usable was found.
    """
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
    """Parse an EXIF-ish datetime string; tolerant of common quirks."""
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
    """Yield candidate destination names: exact, then _1, _2, ... before ext."""
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
# Source scanning
# ---------------------------------------------------------------------------

def scan_sources(sources, extensions):
    """Yield every file under the given source folders with a matching ext."""
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
# Rich UI helpers
# ---------------------------------------------------------------------------

def console_print(text="", style="", **kwargs):
    """Print a plain (non-live) line, optionally styled with a rich color."""
    if isinstance(text, Text):
        CONSOLE.print(text, **kwargs)
    elif style:
        CONSOLE.print(Text(str(text), style=style), **kwargs)
    else:
        CONSOLE.print(str(text), **kwargs)


def _human_bytes(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return str(n)


def _drive_free(path: Path):
    """Return (free, total) bytes for the disk holding `path`, or None."""
    try:
        root = path if path.is_dir() else path.parent
        u = shutil.disk_usage(root)
        return u.free, u.total
    except OSError:
        return None


def _type_lookup(ext: str):
    """Map a lowercase extension to (kind, label, color) or None."""
    info = _TYPE_BY_EXT.get(ext.lower())
    if info:
        return info
    # fall back: any file we scan belongs to the active mode, give it generic
    return None


_ACTIVITY_MAX = 8


def _activity_list(activity_lines: list, accent: str) -> Group:
    """Fixed-height, non-scrolling recent-activity list.

    Completed lines appear newest-at-bottom; the final in-progress line is
    always the 'currently processing' file. The list is truncated to at most
    _ACTIVITY_MAX lines so it never overflows the panel.
    """
    lines = activity_lines[-_ACTIVITY_MAX:] if len(activity_lines) > _ACTIVITY_MAX else activity_lines
    return Group(*lines) if lines else Group(Text("Scanning ...", style="dim"))


def _current_file_line(file_path: Path, day_rel: str, status: str,
                       is_fallback: bool, color: str, mode_cfg) -> Text:
    """Build the colored single-file progress line shown in the live panel."""
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
    """Table of running totals per file type, colored per type."""
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
    """Right-panel stats grid: progress, counters, elapsed, drive space."""
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


def _fmt_elapsed(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m:02d}m {s:02d}s"


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
    """Narrow left panel: mode icon + legend (or summary after the run ends)."""
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
    """One-time color legend for the active mode's file types."""
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
    """Build the color legend as multi-line Text (used in the left panel)."""
    t = Text()
    for kind, info in cfg["types"].items():
        t.append(f"# {info['label']}", style=info["color"])
        t.append("\n")
    t.append("# fallback", style=YELLOW)
    t.append("\n")
    t.append("# error", style=RED)
    return t


# ---------------------------------------------------------------------------
# Main interactive flow
# ---------------------------------------------------------------------------

def prompt_input(prompt: str, default: str = "") -> str:
    if default:
        prompt = f"{prompt} [{default}] "
    return input(prompt).strip()


_MODE_SUBTITLES = {
    "media": "Sort photos & videos by capture date",
    "documents": "Sort PDF, Word, Excel & PowerPoint by creation date",
}


def _center_block(text: str) -> str:
    """Horizontally center each line of a multi-line string for the console."""
    width = CONSOLE.width
    lines = text.rstrip("\n").split("\n")
    return "\n".join(
        "".ljust(max(0, (width - len(l)) // 2)) + l for l in lines
    )


def select_mode() -> str:
    """Ask the user which mode to run and return its MODE_CONFIGS key."""
    keys = list(MODE_CONFIGS)
    box_body = Text()
    box_body.append("Select mode:  ", style=f"bold {GREEN}")
    box_body.append("\n")
    for i, k in enumerate(keys, 1):
        box_body.append(f"[{i}] {MODE_CONFIGS[k]['label']}\n")
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


def print_logo() -> None:
    CONSOLE.print()
    CONSOLE.print(Text(_center_block(LOGO_ART), style=GREEN))
    sub = Text()
    padding = " " * max(0, (CONSOLE.width - len(TAGLINE)) // 2)
    sub.append(padding + TAGLINE, style=f"bold {GREEN}")
    CONSOLE.print(sub)
    CONSOLE.print(Text(" " * max(0, (CONSOLE.width - 62) // 2) + "=" * 62, style="dim"))
    CONSOLE.print()


def _summary_panel(cfg, panel: dict, type_counts: dict, elapsed) -> Panel:
    """Build the end-of-run summary as a reusable rich Panel (does not print)."""
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
    """Print the boxed summary panel plus the per-type totals line."""
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


def _exit_prompt() -> None:
    input(f"\x1b[32mPress Enter to exit...\x1b[0m")


def _rel(dest: Path, day_dir: Path) -> str:
    """Return the display sub-path of a day folder (e.g. 2026/August/26)."""
    try:
        return str(day_dir.relative_to(dest)).replace("\\", "/")
    except ValueError:
        return str(day_dir)


def _copy_one(file_path: Path, day_dir: Path):
    """Copy a single file handling dedup + collision rename.

    Returns (status, day_dir, err_msg) where status is one of
    "copied"/"dup"/"err", day_dir is the destination day folder (a Path), and
    err_msg is the OSError text when status == "err" else None.
    """
    try:
        src_identity = file_identity(file_path)
        target = unique_copy_path(day_dir, file_path.name, src_identity)
        if target is None:
            return "dup", day_dir, None
        shutil.copy2(file_path, target)
        return "copied", day_dir, None
    except OSError as exc:
        return "err", day_dir, exc


def main() -> None:
    print_logo()
    mode = select_mode()
    cfg = MODE_CONFIGS[mode]

    ensure_exiftool()

    # --- Source input -----------------------------------------------------
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

    # --- Destination input ------------------------------------------------
    raw_dst = prompt_input("Enter destination folder path: ").strip()
    dest = Path(raw_dst).expanduser()
    if not str(dest).strip():
        console_print("  No destination provided. Exiting.", RED)
        _exit_prompt()
        return

    # --- Scan --------------------------------------------------------------
    all_files = list(scan_sources(sources, cfg["extensions"]))
    total = len(all_files)
    if total == 0:
        console_print(f"  No {cfg['label']} files found in the given source folder(s).", YELLOW)
        console_print(f"  (Active extensions: {', '.join(sorted(e for e in cfg['extensions']))})", "dim")
        _exit_prompt()
        return

    console_print(f"  Sorting {len(sources)} source folder(s) into {dest} ...", GREEN)
    console_print(f"  Found {total} file(s).", GREEN)
    console_print("")
    console_print(_legend(cfg))
    console_print("")

    panel = {"sources": len(sources), "scanned": total,
             "copied": 0, "duplicates": 0, "fallback": 0, "errors": 0}
    type_counts: dict = {k: 0 for k in cfg["types"]}
    start = time.time()

    # Drive space: first source drive + destination drive (refreshed every 50).
    drive_src = _drive_free(sources[0])
    drive_dest = _drive_free(dest)
    tick = 0

    is_tty = sys.stdout.isatty()

    if not is_tty:
        # Non-interactive / piped: sequential progress lines (also great for
        # logs and for running under automation or a redirected console).
        for i, file_path in enumerate(all_files, 1):
            try:
                dt = read_capture_date(file_path, cfg["date_tags"])
                color = GREEN
                is_fallback = False
                if dt is None:
                    mtime = file_path.stat().st_mtime
                    dt = datetime.datetime.fromtimestamp(mtime)
                    panel["fallback"] += 1
                    log_fallback(file_path, dt)
                    is_fallback = True
                    color = YELLOW

                day_dir = destination_for(dest, dt)
                status, day_dir, err_msg = _copy_one(file_path, day_dir)
                day_rel = _rel(dest, day_dir)
                if status == "copied":
                    panel["copied"] += 1
                elif status == "dup":
                    panel["duplicates"] += 1
                elif status == "err":
                    panel["errors"] += 1

                _bump_type_counts(type_counts, file_path.suffix, cfg)

                line = _current_file_line(file_path, day_rel, status, is_fallback, color, cfg)
                t_line = Text()
                t_line.append(f"[{i}/{total}] ", style=GREEN)
                t_line.append_text(line)
                if status == "err":
                    t_line.append(f"  (ERROR {err_msg})", style=RED)
                CONSOLE.print(t_line)
            except Exception as exc:  # noqa: BLE001
                panel["errors"] += 1
                _bump_type_counts(type_counts, file_path.suffix, cfg)
                CONSOLE.print(Text(f"[{i}/{total}] ERROR {file_path}: {exc}", style=RED))
    else:
        # Interactive: live split-panel dashboard.
        activity_lines = []
        left_body = Text()
        left_body.append(cfg["icon"], style=cfg["accent"])
        left_body.append("\n\n")
        left_body.append_text(_legend_text(cfg))
        left = _left_panel(cfg, left_body)
        layout = _build_layout(cfg, left, _right_panel(
            cfg, panel, type_counts, activity_lines, total, 0,
            start, drive_src, drive_dest))
        try:
            with Live(layout, console=CONSOLE, refresh_per_second=10,
                      screen=False, redirect_stdout=False, get_renderable=None) as live:
                for i, file_path in enumerate(all_files, 1):
                    try:
                        dt = read_capture_date(file_path, cfg["date_tags"])
                        is_fallback = False
                        color = cfg["accent"]
                        if dt is None:
                            mtime = file_path.stat().st_mtime
                            dt = datetime.datetime.fromtimestamp(mtime)
                            panel["fallback"] += 1
                            log_fallback(file_path, dt)
                            is_fallback = True
                            color = YELLOW

                        day_dir = destination_for(dest, dt)
                        status, day_dir, err_msg = _copy_one(file_path, day_dir)
                        day_rel = _rel(dest, day_dir)
                        if status == "copied":
                            panel["copied"] += 1
                        elif status == "dup":
                            panel["duplicates"] += 1
                        elif status == "err":
                            panel["errors"] += 1

                        _bump_type_counts(type_counts, file_path.suffix, cfg)

                        cur = _current_file_line(file_path, day_rel, status, is_fallback, color, cfg)
                        if status == "err":
                            cur.append(f"  (ERROR {err_msg})", style=RED)
                        prog = Text("-> ", style=cfg["accent"])
                        prog.append_text(cur)
                        prog.append("\n")
                        activity_lines.append(prog)
                        tick += 1
                        if tick % 50 == 0:
                            drive_src = _drive_free(sources[0])
                            drive_dest = _drive_free(dest)

                        live.update(_build_layout(
                            cfg, left, _right_panel(
                                cfg, panel, type_counts, activity_lines, total, i,
                                start, drive_src, drive_dest)))
                    except Exception as exc:  # noqa: BLE001
                        panel["errors"] += 1
                        _bump_type_counts(type_counts, file_path.suffix, cfg)
                        cur = Text(f"ERROR {file_path}: {exc}", style=RED)
                        activity_lines.append(cur)
                        live.update(_build_layout(
                            cfg, left, _right_panel(
                                cfg, panel, type_counts, activity_lines, total, i,
                                start, drive_src, drive_dest)))
        except KeyboardInterrupt:
            CONSOLE.print(Text("\n  Cancelled by user.", style=RED))
            _exit_prompt()
            return

    if is_tty:
        left2 = _left_panel(cfg, _summary_panel(cfg, panel, type_counts, time.time() - start))
        final_layout = _build_layout(cfg, left2, _right_panel(
            cfg, panel, type_counts, activity_lines, total, len(all_files),
            start, drive_src, drive_dest))
        CONSOLE.print()
        CONSOLE.print(final_layout)
        CONSOLE.print()

    print_summary(panel, cfg, type_counts, time.time() - start)
    _exit_prompt()


def _bump_type_counts(type_counts: dict, ext: str, cfg: dict) -> None:
    """Increment the matching per-type counter for an extension."""
    for kind, info in cfg["types"].items():
        if ext.lower() in info["exts"]:
            type_counts[kind] = type_counts.get(kind, 0) + 1
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console_print("\n  Cancelled by user.", RED)
        try:
            input(f"\x1b[32mPress Enter to exit...\x1b[0m")
        except EOFError:
            pass
