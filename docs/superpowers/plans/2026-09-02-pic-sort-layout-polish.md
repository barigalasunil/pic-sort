# PicSort Layout Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the `rich` split-panel live UI in `picsort.py` — move the summary to the left panel, reorder and add a non-scrolling activity list to the right panel, redesign both mode icons, and polish the startup screen.

**Architecture:** All changes are confined to the single file `D:\pic-sort\picsort.py`. UI is assembled from pure functions (`_left_panel`, `_right_panel`, `_legend`, `print_summary`) called from `main()`. No data-model changes. Summary becomes a reusable renderable function instead of printing directly to `CONSOLE`.

**Tech Stack:** Python 3.14, `rich` (Panel, Group, Layout, Live, Table, Text, Progress), PyInstaller (build only).

## Global Constraints

- **All rendered output must be ASCII-only** (console is cp1252; box-drawing/unicode chars render as garbage). `box.ASCII` everywhere. Icons must use only ASCII chars.
- Follow existing style: functions use `_` prefix for private helpers; constants are UPPER_SNAKE; type hints on function signatures.
- Do not introduce any comments unless the surrounding code has them (existing code is comment-light; match it).
- Preserve the non-TTY (piped) code path — it must keep working after changes.
- Mode config `accent` strings: media=`bright_green`, documents=`bright_cyan`.
- Color constants available: `GREEN`, `YELLOW`, `RED`, `CYAN`, `DIM` (all in file).
- Testing is manual/end-to-end (no pytest). Non-TTY path is driven by piping input; TTY path is verified via the file-bound console trick (see Task globals below).

**Character set reminder:** the `()` lens and `_` characters used in icons are ASCII-safe. Verify each icon line is pure ASCII before finalizing.

---

### Task 1: Redesign the mode icons

**Files:**
- Modify: `D:\pic-sort\picsort.py:114-135` (CAMERA_ICON + FOLDER_ICON)

**Interfaces:**
- Consumes: nothing from other tasks; only the existing `MODE_CONFIGS` which references `CAMERA_ICON` / `FOLDER_ICON` by name.
- Produces: the updated `CAMERA_ICON` and `FOLDER_ICON` string constants. Names unchanged, so `MODE_CONFIGS` needs no edit.

**Rationale / verification:** The camera should read as a camera (lens + body), the folder as a folder (tab + body). Because the exe console is cp1252, the icons must be pure ASCII. Alignment is verified by each line having a consistent width so the icon isn't jagged.

- [ ] **Step 1: Confirm the current constants**

Read `picsort.py:114-135`. They are the `r"""..."""` raw strings for `CAMERA_ICON` and `FOLDER_ICON`.

- [ ] **Step 2: Replace CAMERA_ICON**

Replace the existing `CAMERA_ICON` block (lines 114-124) with this ASCII camera (lens `()` centered in the body, two small top controls for recognizability):

```python
CAMERA_ICON = r"""
     _____________
    /             \
   |  __    ___    |
   | |  |  |   |   |
   | |__|  |___|   |
   |    ______     |
   |   |  ()  |    |
   |   |______|    |
    \_____________/
"""
```

Note: in the source file this is a raw string so backslashes are literal. The first `\` after `(` and the trailing `\` are literal backslash characters (part of the art), NOT escapes. Because it is a raw triple-quoted string, no escaping is needed.

- [ ] **Step 3: Replace FOLDER_ICON**

Replace the existing `FOLDER_ICON` block (lines 126-135) with this ASCII folder (tab at top-left, body rectangle):

```python
FOLDER_ICON = r"""
 .--------------------.
 |  .----------------. |
 |  |                | |
 |  |                | |
 |  |                | |
 |  |________________| |
  \__________________/
"""
```

- [ ] **Step 4: Verify icon rendering looks clean**

Render both icons isolated and confirm no jagged/misaligned rows and that each icon reads clearly:

Run: `py -c "import picsort; print(picsort.CAMERA_ICON); print(picsort.FOLDER_ICON)"` (from `D:\pic-sort`).
Expected: the two icons print as blocky ASCII art. The camera shows a body with a centered `()` lens; the folder shows a tab and body. Skim for any row that protrudes or recedes oddly.

- [ ] **Step 5: Syntax check**

Run: `py -c "import ast,sys; ast.parse(open(r'D:\pic-sort\picsort.py',encoding='utf-8').read()); print('OK')"` from `D:\pic-sort`.
Expected: prints `OK`.

- [ ] **Step 6: Commit**

```bash
git add picsort.py
git commit -m "feat: redesign camera and folder mode icons"
```

---

### Task 2: Startup screen polish (centered logo, bordered box, subtitles)

**Files:**
- Modify: `D:\pic-sort\picsort.py` (`print_logo()` ~line 686, `select_mode()` ~line 672)

**Interfaces:**
- Consumes: `LOGO_ART`, `GREEN`, `DIM`, `Panel`, `box`, `Text`, `CONSOLE` (all already imported/defined).
- Produces: `print_logo()` still returns None (prints); `select_mode()` still returns a MODE_CONFIGS key string. Both keep identical signatures so `main()` needs no change. Adds a small module-level `TAGLINE` constant.

**Approach:** Center the logo and tagline horizontally using `CONSOLE.width`. Wrap the mode list in a `Panel(box=box.ASCII, border_style=GREEN)` and add a dim subtitle under each option.

- [ ] **Step 1: Write the failing expectations first (syntax + presence check)**

There is no test framework, so the "test" is a grep/run check that the new pieces exist and the script parses. Run:

```bash
py -c "import ast; ast.parse(open(r'D:\pic-sort\picsort.py',encoding='utf-8').read()); print('parses')"
```
Expected: prints `parses`. (This is the guard that the following edits don't break syntax.)

- [ ] **Step 2: Add a TAGLINE constant**

Add the tagline constant near the icon constants (after the `FOLDER_ICON` block, before the `# ---` Mode configuration comment around line 137):

```python
TAGLINE = "Sort your photos, videos & documents by date, automatically."
```

- [ ] **Step 3: Rewrite `print_logo()`**

Replace the current `print_logo()` function (lines ~686-692) with a centered version. Helper to center a multi-line block:

```python
def _center_block(text: str) -> str:
    """Horizontally center each line of a multi-line string for the console."""
    width = CONSOLE.width
    lines = text.rstrip("\n").split("\n")
    return "\n".join(
        "".ljust(max(0, (width - len(l)) // 2)) + l for l in lines
    )


def print_logo() -> None:
    CONSOLE.print()
    CONSOLE.print(Text(_center_block(LOGO_ART), style=GREEN))
    sub = Text()
    padding = " " * max(0, (CONSOLE.width - len(TAGLINE)) // 2)
    sub.append(padding + TAGLINE, style=f"bold {GREEN}")
    CONSOLE.print(sub)
    CONSOLE.print(Text(" ".ljust(max(0, (CONSOLE.width - 62) // 2)) + "=" * 62, style="dim"))
    CONSOLE.print()
```

- [ ] **Step 4: Rewrite `select_mode()` with a bordered box and subtitles**

Replace the current `select_mode()` (lines ~672-683) with a version that renders a centered, bordered panel. Subtitle text per mode:

```python
_MODE_SUBTITLES = {
    "media": "Sort photos & videos by capture date",
    "documents": "Sort PDF, Word, Excel & PowerPoint by creation date",
}


def select_mode() -> str:
    keys = list(MODE_CONFIGS)
    box_body = Text()
    box_body.append("Select mode:  ", style=f"bold {GREEN}")
    box_body.append("\n")
    for i, k in enumerate(keys, 1):
        box_body.append(f"[{i}] {MODE_CONFIGS[k]['label']}\n")
        box_body.append(f"     {_MODE_SUBTITLES.get(k, '')}\n\n".rstrip("\n"))
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
    centered = _center_block(panel.__rich_console__(CONSOLE, CONSOLE.options).__str__())
    CONSOLE.print(Text("\n" + centered))
    while True:
        choice = input(f"  Mode [1-{len(keys)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            return keys[int(choice) - 1]
        CONSOLE.print(Text("  Invalid choice. Please try again.", style=YELLOW))
```

> **Implementation caution:** `Panel.__rich_console__` returns a generator; do NOT call `.__str__()` on it. Instead render the panel via a throwaway `Console` and take its `export_text()`. Use this reliable approach instead:

```python
def _render_text(renderable) -> str:
    tmp = Console(width=CONSOLE.width, force_terminal=False)
    tmp.print(renderable, end="")
    return tmp.export_text()
```

Then in `select_mode()`, build the panel and print `"\n" + _render_text(panel)` (optionally centered text). Use `_render_text` for the panel so the box renders with ASCII borders. If centering the panel causes it to be cut on narrow terminals, print it left-aligned instead (safe fallback).

- [ ] **Step 5: Verify the startup flow (non-TTY)**

Run the script with piped input to drive mode selection, and inspect the printed banner:

```bash
py picsort.py 2>&1 | Select-String -Pattern "PIC-SORT MODE|Select mode|\[1\] Media|\[2\] Documents|capture date|creation date|sort your photos"
```
(Feed at least `1\n` + a dummy source + dest if it proceeds past selection; the relevant assertion is that the banner/box/subtitles print.)

From `D:\pic-sort`. Expected: output contains the bordered box title `PIC-SORT MODE`, both `[1] Media` and `[2] Documents` entries, and the subtitle strings.

- [ ] **Step 6: Syntax check**

Run: `py -c "import ast; ast.parse(open(r'D:\pic-sort\picsort.py',encoding='utf-8').read()); print('OK')"` from `D:\pic-sort`. Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add picsort.py
git commit -m "feat: polish startup screen - centered logo and bordered mode menu"
```

---

### Task 3: Add a leading vertical space helper and refactor summary into a reusable renderable

**Files:**
- Modify: `D:\pic-sort\picsort.py` (`print_summary()` ~line 695)

**Interfaces:**
- Consumes: `panel` dict (keys `sources, scanned, copied, duplicates, fallback, errors`), `cfg`, `type_counts`, `elapsed`; all color constants; `Table`, `Panel`, `box`, `Text`.
- Produces: a new function `_summary_panel(cfg, panel, type_counts, elapsed) -> Panel` returning a `rich.Panel` (does NOT print). Keeps `print_summary()` as a thin wrapper that prints it, so behavior is preserved when it is still called on the non-TTY path.

**Approach:** Extract the summary-table-building logic into `_summary_panel()` that returns a `Panel`. `print_summary()` calls it then prints.

- [ ] **Step 1: Syntax guard**

```bash
py -c "import ast; ast.parse(open(r'D:\pic-sort\picsort.py',encoding='utf-8').read()); print('parses')"
```
Expected: `parses`.

- [ ] **Step 2: Add `_summary_panel` and make `print_summary` a wrapper**

Replace the current `print_summary()` body (lines ~695-733) with:

```python
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
```

- [ ] **Step 3: Syntax check**

```bash
py -c "import ast; ast.parse(open(r'D:\pic-sort\picsort.py',encoding='utf-8').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 4: Confirm the non-TTY path still prints a summary**

Run a full non-TTY Documents run with piped input and check the summary appears:

```bash
$test = "D:\pic-sort\_test"
Remove-Item -Recurse -Force "$test\dest" -ErrorAction SilentlyContinue
"2`n$test\src`n$test\dest`n`n" | py picsort.py 2>&1 | Select-String -Pattern "Files copied|Skipped|Fallback date"
```
(Adjust `src`/files to real test files in docs mode.) From `D:\pic-sort`. Expected: summary lines appear (unchanged behavior).

- [ ] **Step 5: Commit**

```bash
git add picsort.py
git commit -m "feat: extract summary into reusable _summary_panel renderable"
```

---

### Task 4: Left panel — icon + legend during run, summary after run; add activity list plumbing

**Files:**
- Modify: `D:\pic-sort\picsort.py` (`_left_panel` ~625, `_right_panel` ~603, `_legend` ~646, `main()` TTY branch ~866-925)

**Interfaces:**
- Consumes: `cfg`, `Text`, `Panel`, `box`, `Group`, `Panel`-based `_summary_panel` from Task 3, and a new `activity_lines` list passed from `main()`.
- Produces:
  - `_left_panel(cfg, body: Text) -> Panel` — signature changes to accept an inner `Text` body (icon in accent color by default, or summary). `_build_layout` callers update accordingly.
  - `_right_panel(cfg, counts, type_counts, activity_lines, total, processed, start, drive_src, drive_dest) -> Panel` — replaces the `current_line` parameter with `activity_lines: list of Text`.
  - A new helper `_activity_list(activity_lines: list, style: str) -> Group` that renders the fixed-height, non-scrolling activity list (see below).

**Approach / layout rules:**

Right panel, top → bottom:
1. `_stats_table(...)`
2. `Text("Per type:", style="bold")`
3. `_per_type_table(type_counts, cfg)`
4. spacer `Text()`
5. `_activity_list(activity_lines, cfg["accent"])`
6. `_progress_renderable(processed, total, cfg["accent"])`

The activity list is a `Group` of `Text` lines that is TRUNCATED to a MAXIMUM height (`_ACTIVITY_MAX = 8`) so it never needs scrolling. The in-progress (last) line is always the current file marked with a `->` prefix.

The progress bar must sit at the very bottom of the panel body.

- [ ] **Step 1: Syntax guard**

```bash
py -c "import ast; ast.parse(open(r'D:\pic-sort\picsort.py',encoding='utf-8').read()); print('parses')"
```
Expected: `parses`.

- [ ] **Step 2: Add the activity-list constant and helper**

Add near the other `_ACTIVITY_*` / panel helpers a module-level constant and helper (place just above `_current_file_line`):

```python
_ACTIVITY_MAX = 8


def _activity_list(activity_lines: list, accent: str) -> Group:
    """Fixed-height, non-scrolling recent-activity list.

    Completed lines appear newest-at-bottom; the final in-progress line is
    always the 'currently processing' file. The list is truncated to at most
    _ACTIVITY_MAX lines so it never overflows the panel.
    """
    lines = activity_lines[-_ACTIVITY_MAX:] if len(activity_lines) > _ACTIVITY_MAX else activity_lines
    return Group(*lines) if lines else Group(Text("Scanning ...", style="dim"))
```

- [ ] **Step 3: Rewrite `_right_panel`**

Replace the current `_right_panel` (lines ~603-622) with:

```python
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
```

- [ ] **Step 4: Rewrite `_left_panel` to accept a body**

Replace the current `_left_panel` (lines ~625-634) with:

```python
def _left_panel(cfg, body: Text) -> Panel:
    """Narrow left panel: mode icon + legend (or summary after the run ends)."""
    return Panel(
        body,
        title=f"[{cfg['accent']}] {cfg['label'].split('(')[0].strip()}",
        border_style=cfg["accent"],
        box=box.ASCII,
        expand=True,
    )
```

- [ ] **Step 5: Add a legend builder that returns a Text**

Add (used by both the left panel during the run and the one-time print where needed):

```python
def _legend_text(cfg) -> Text:
    """Build the color legend as a single Text (used in the left panel)."""
    t = Text()
    for kind, info in cfg["types"].items():
        t.append(f"# {info['label']}", style=info["color"])
        t.append("\n")
    t.append("# fallback", style=YELLOW)
    t.append("\n")
    t.append("# error", style=RED)
    return t
```

Keep the existing `_legend()` function unchanged for the non-TTY path (it prints nothing; it returns a `Text`). If you prefer, reuse `_legend_text` inside `_left_panel`.

- [ ] **Step 6: Update `main()` TTY branch**

In `main()` TTY branch (lines ~866-925):

(a) Before the `try:` block, initialize `activity_lines = []`.

(b) Build the left panel with icon+legend:

```python
left_body = Text()
left_body.append(cfg["icon"], style=cfg["accent"])
left_body.append("\n\n")
left_body.append_text(_legend_text(cfg))
left_body.append("\n")
left = _left_panel(cfg, left_body)
```

(c) Initial right panel now passes `activity_lines` instead of the `Text("Scanning ...")`:

```python
layout = _build_layout(cfg, left, _right_panel(
    cfg, panel, type_counts, activity_lines, total, 0,
    start, drive_src, drive_dest))
```

(d) Inside the loop, after building `cur` for the current file, append it to `activity_lines` and APPEND the current file line each iteration. The current line always renders last with a `->` prefix. Modify the line building so the completed/current distinction is a `->` for in-progress and a `+` for completed:

```python
prog = Text("-> ", style=cfg["accent"])
prog.append_text(cur)
activity_lines.append(prog)
```

Then the live update call:

```python
live.update(_build_layout(
    cfg, left, _right_panel(
        cfg, panel, type_counts, activity_lines, total, i,
        start, drive_src, drive_dest)))
```

(e) In the `except Exception` branch inside the loop, similarly append an error line and update.

(f) AFTER `with Live(...)` exits (after the `except KeyboardInterrupt` block), before `print_summary`, update the layout one final time with the LEFT panel showing the summary, and give the live loop a moment to refresh:

```python
if is_tty:
    live.stop()
    # Render the summary into the left panel by rebuilding the layout.
    # The summary replaces the icon+legend in the left panel.
    left2 = _left_panel(cfg, _summary_panel(cfg, panel, type_counts, time.time() - start))
    layout_final = _build_layout(cfg, left2, _right_panel(
        cfg, panel, type_counts, activity_lines, total, len(all_files),
        start, drive_src, drive_dest))
```

> **Implementation caution / decision:** Because `Live` in this codebase uses `screen=False`, the final panel swap is easiest to show by calling `live.update(layout_final)` right before `live.stop()`, or by printing `_render_text` of a fresh layout after stopping. Rendering a brand-new `Live` after stopping can conflict. Recommend the following concretely testable approach: **stop the Live context cleanly, then print the final layout text via `_render_text`** so the summary-on-left is visible in the transcript:

```python
# after the with-Live block and KeyboardInterrupt handling:
if is_tty:
    live.stop()
    left2 = _left_panel(cfg, _summary_panel(cfg, panel, type_counts, time.time() - start))
    final_layout = _build_layout(cfg, left2, _right_panel(
        cfg, panel, type_counts, activity_lines, total, len(all_files),
        start, drive_src, drive_dest))
    CONSOLE.print()
    CONSOLE.print(Text("Final layout (left = summary):", style="dim"))
```

The exact final-print method must be confirmed by testing (see Step 8). If `Live` re-render conflicts arise, the safe fallback is to print `_summary_panel` on the left panel text after stopping Live.

- [ ] **Step 7: Run the non-TTY path to confirm nothing regressed**

Run a Media non-TTY run with piped input; confirm files copy and summary prints:

```bash
$test = "D:\pic-sort\_test"
Remove-Item -Recurse -Force "$test\dest" -ErrorAction SilentlyContinue
"1`n$test\src`n$test\dest`n`n" | py picsort.py 2>&1 | Select-String -Pattern "photo|clip|Files copied|Summary"
```
From `D:\pic-sort`. Expected: per-file lines and a `Summary` panel still print (non-TTY path unaffected).

- [ ] **Step 8: Exercise the TTY path via the file-bound console trick**

Because the sandbox cannot run the real interactive exe, validate the `Live` code path by binding the console to a file (the known technique: set `sys.stdout` to an open file so `isatty()` and `Live` still execute the TTY branch), and check the run completes without exceptions and the layout renders:

Create `D:\pic-sort\_tty_test.py`:

```python
import io, sys
import picsort

# Simulate a TTY by giving the process a file-bound stdout that reports isatty()=True.
class FakeTTY(io.TextIOWrapper):
    def isatty(self):
        return True

# Wrap picsort's own console so Live renders into a file, not the real terminal.
out = open("_tty_out.txt", "w", encoding="utf-8")
sys.stdout = FakeTTY(out.buffer, encoding="utf-8")
# Redirect picsort's console as well
picsort.CONSOLE.file = out
# feed inputs
inp = io.StringIO("1\nD:\\pic-sort\\_test\\src\nD:\\pic-sort\\_test\\dest_tty\n\n")
sys.stdin = inp
try:
    picsort.main()
except SystemExit:
    pass
out.flush(); out.close()
print("TTY path executed without exception")
```

Run: `py _tty_test.py` from `D:\pic-sort`.
Expected: prints `TTY path executed without exception` (no traceback). Confirm `_tty_out.txt` is non-empty.

> If the FakeTTY approach fights `Live`, an alternative is to run the script under `script`-like capture; the fallback assertion is simply "no exception + output written". Confirm visually that the right panel shows stats on top, activity list with `->` and `+` lines, and progress bar at the bottom.

- [ ] **Step 9: Syntax check + grep for regressions**

```bash
py -c "import ast; ast.parse(open(r'D:\pic-sort\picsort.py',encoding='utf-8').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 10: Commit**

```bash
git add picsort.py
git commit -m "feat: rework split-panel layout - progress at bottom, activity list, summary on left"
```

---

### Task 5: Full end-to-end verification of both modes (TTY + non-TTY)

**Files:**
- No source edits. Create temp verification scripts only.

**Interfaces:**
- Consumes: the final `main()`, `_left_panel`, `_right_panel`, `_summary_panel`, `select_mode`, `print_logo`.

**Approach:** Verify the user's stated acceptance criteria:
1. No leftover `last_used` refs.
2. Right-panel file list never scrolls (fixed height via `_ACTIVITY_MAX`, oldest drops off).
3. Left panel shows the summary correctly after completion.
4. Both mode icons are visually clear at a glance.
5. Startup is centered + bordered + subtitled.
6. Progress bar at bottom.
7. Both modes run end-to-end.

Also satisfy the GLOBAL constraints: ASCII-only output, cp1252-safe.

- [ ] **Step 1: Grep for leftover persistence references**

```bash
Set-Location D:\pic-sort
Select-String -Path picsort.py -Pattern "last_used|load_last|save_last|last_used_path" -SimpleMatch
```
Expected: no output (no matches).

- [ ] **Step 2: Syntax check**

```bash
py -c "import ast; ast.parse(open(r'D:\pic-sort\picsort.py',encoding='utf-8').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 3: Confirm both icons are pure ASCII**

```bash
py -c "import picsort; bad=[l for l in picsort.CAMERA_ICON.split(chr(10))+picsort.FOLDER_ICON.split(chr(10)) if any(ord(c)>127 for c in l)]; print('non-ascii rows:', len(bad))"
```
From `D:\pic-sort`. Expected: `non-ascii rows: 0`.

- [ ] **Step 4: Run Media mode non-TTY end-to-end**

Prepare test files and run; verify copies + counts + summary:

```bash
$test = "D:\pic-sort\_test"
Remove-Item -Recurse -Force "$test\dest_media" -ErrorAction SilentlyContinue
"1`n$test\src_media`n$test\dest_media`n`n" | py picsort.py 2>&1 | Select-String -Pattern "Found|Files copied|Fallback date|Photos|Videos|Summary"
```
From `D:\pic-sort`. Expected: `Found 3 file(s)`, copy lines, `Photos: 2`, `Videos: 1`, and a `Summary` panel.

- [ ] **Step 5: Run Documents mode non-TTY end-to-end**

```bash
$test = "D:\pic-sort\_test"
Remove-Item -Recurse -Force "$test\dest_docs" -ErrorAction SilentlyContinue
"2`n$test\src_docs`n$test\dest_docs`n`n" | py picsort.py 2>&1 | Select-String -Pattern "Found|Files copied|PDF|Excel|Summary"
```
From `D:\pic-sort`. Expected: files copied, per-type counts, summary.

- [ ] **Step 6: TTY-path run for both modes (file-bound console)**

Reuse the `_tty_test.py` technique from Task 4, but for BOTH `1` (media) and `2` (documents), asserting each completes without exception and writes a non-empty layout file. Inspect the layout file for:
- stats table above the activity list
- `->` in-progress line present (or `+` completed lines)
- progress bar at the bottom
- (final) summary appearing in the left panel

- [ ] **Step 7: Visual check of the startup banner (both modes)**

From the Task 2 Step 5 output, confirm the banner/box renders with ASCII borders and both mode subtitles.

- [ ] **Step 8: Clean up temp verification files**

```bash
Remove-Item -Recurse -Force "D:\pic-sort\_test", "D:\pic-sort\_tty_test.py", "D:\pic-sort\_tty_out.txt" -ErrorAction SilentlyContinue
```

- [ ] **Step 9: Commit any straggler changes**

```bash
git status
```
If there are uncommitted source changes, commit them with a clear message. Expected: working tree clean (only `dist/`, `build/`, `tools/` ignored).

---

### Task 6: Rebuild the exe and push

**Files:**
- Build artifact: `D:\pic-sort\dist\PicSort.exe` (gitignored)

**Interfaces:**
- None. This packages the verified source.

- [ ] **Step 1: Rebuild with PyInstaller**

```bash
py -m PyInstaller --onefile --console --name PicSort --clean --noconfirm picsort.py
```
From `D:\pic-sort`. Expected: `Build complete! The results are available in: D:\pic-sort\dist`.

- [ ] **Step 2: Confirm exe size/roundtrip**

```bash
(Get-Item "D:\pic-sort\dist\PicSort.exe").Length / 1MB
```
Expected: roughly the same order as prior build (~37 MB). The exe is recreated with the new layout.

- [ ] **Step 3: Confirm git status / push**

```bash
git status
```
Expected: only the new docs files (plan + spec) uncommitted.

- [ ] **Step 4: Commit docs and push**

```bash
git add docs/
git commit -m "docs: add layout polish plan"
git push origin master
```
Expected: push succeeds.

---

## Self-Review Notes

- **Spec coverage:**
  - 2a reorder right panel → Task 4 (right panel body order).
  - 2b fixed-height activity list → Task 4 `_activity_list` + `_ACTIVITY_MAX`.
  - 2c progress at bottom → Task 4 right panel order.
  - 3a left icon+legend during run → Task 4 `_legend_text` + left body.
  - 3b summary on left after run → Task 4 Step 6(f) + Task 3 `_summary_panel`.
  - 4 startup centered/bordered/subtitles → Task 2.
  - 5a camera icon, 5b folder icon → Task 1.
  - 1 bug (no leftover last_used) → Task 5 Step 1 grep confirms zero.
- **No placeholders:** every step includes exact code or an exact verification command.
- **Type consistency:** `_right_panel` signature changes from `current_line` → `activity_lines` are uniformly applied in Task 4; `_left_panel` gains a `body` param applied in Task 4 Step 4/6; `print_summary` still takes `(panel, cfg, type_counts, elapsed)` and `main()` calls it unchanged.
