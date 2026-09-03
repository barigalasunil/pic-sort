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
