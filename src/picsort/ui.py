#!/usr/bin/env python3
"""PicSort - Rich console primitives and renderables (no data logic)."""

import shutil
import sys
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
DIM = core.DIM
FALLBACK = core.FALLBACK

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
    tmp = _Console(width=max(80, CONSOLE.width), force_terminal=False, record=True)
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
        base.append(name, style=f"{FALLBACK}")
        base.append(f"  (fallback date)", style=FALLBACK)
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
    grid.add_row(Text("Fallback date", style=FALLBACK), Text(str(counts["fallback"]), style=FALLBACK))
    grid.add_row(Text("Errors", style=RED), Text(str(counts["errors"]), style=RED))
    grid.add_row(Text("Elapsed", style=DIM), Text(_fmt_elapsed(elapsed), style=DIM))

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
        box=box.ROUNDED,
        expand=True,
    )


def _left_panel(cfg, body: Text) -> Panel:
    return Panel(
        body,
        title=f"[{cfg['accent']}] {cfg['label'].split('(')[0].strip()}",
        border_style=cfg["accent"],
        box=box.ROUNDED,
        expand=True,
    )


def _title_bar() -> Panel:
    """macOS-style window title bar: traffic-light dots + centered app name."""
    t = Text()
    _dot = "●"
    try:
        _dot.encode(sys.stdout.encoding or "utf-8")
    except (UnicodeEncodeError, LookupError):
        _dot = "o"
    for dot in ("#FF5F56", "#FFBD2E", "#27C93F"):
        t.append(f" {_dot}", style=dot)
    t.append("   ")
    t.append("picsort", style=core.THEME["header"])
    return Panel(t, box=box.ROUNDED, padding=(0, 1), expand=True,
                 border_style=core.THEME["header"])


def _build_layout(cfg, left: Panel, right: Panel) -> Layout:
    layout = Layout(name="root")
    layout.split(
        Layout(_title_bar(), name="title", size=3),
        Layout(
            Layout.split_row(
                Layout(left, name="left", ratio=2),
                Layout(right, name="right", ratio=3),
            ),
            name="body",
        ),
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
    t.append("# fallback", style=FALLBACK)
    t.append("   ")
    t.append("# error", style=RED)
    return t


def _legend_text(cfg) -> Text:
    t = Text()
    for kind, info in cfg["types"].items():
        t.append(f"# {info['label']}", style=info["color"])
        t.append("\n")
    t.append("# fallback", style=FALLBACK)
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
        color = RED if label.startswith("Errors") else (GREEN if label == "Mode" else DIM)
        table.add_row(
            Text(label, style="bold" if label == "Mode" else None),
            Text(str(value), style=color),
        )

    return Panel(table, title=f"[{GREEN}] Summary - {cfg['label']}",
                 border_style=GREEN, box=box.ROUNDED, expand=True)


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


def _center_block(text: str) -> str:
    """Horizontally center each line of a multi-line string for the console."""
    width = CONSOLE.width
    lines = text.rstrip("\n").split("\n")
    return "\n".join(
        "".ljust(max(0, (width - len(l)) // 2)) + l for l in lines
    )
