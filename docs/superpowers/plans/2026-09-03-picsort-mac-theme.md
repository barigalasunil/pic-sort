# PicSort Mac Terminal-Inspired UI Re-skin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-skin the PicSort terminal UI from its single-tone green scheme to a macOS Terminal-inspired multi-color (One-Dark/"Pro") palette, adding a traffic-light title bar and rounded borders, without changing any layout structure, prompts, or core logic.

**Architecture:** A central `THEME` dict in `core.py` maps semantic roles (header/success/warning/fallback/error/dim/panel_bg/teal/purple) to hex strings — the single source of truth for every color. `ui.py` and `cli.py` consume `THEME` tokens (via forward-compatible aliases `GREEN/YELLOW/RED/DIM`), per-mode icons use distinct identity accents (camera=teal, folder=purple), the logo uses header blue, `_build_layout` gains a stacked title-bar row, and all box borders switch from `box.ASCII` to `box.ROUNDED`.

**Tech Stack:** Python 3.9+, Rich (`Console`, `Layout`, `Panel`, `Table`, `Text`, `box`), pytest. Packaging unchanged from the PyPI round.

## Global Constraints

- Package name: `picsort-cli`; command/import/module: `picsort`; version `0.1.0` (from `src/picsort/__init__.py`). **Do not change** these.
- **Re-skin only — zero behavior/logic changes.** Do not alter: left/right panel content positions, the non-scrolling fixed-height activity list, bottom progress bar, left-panel summary, mode-selection flow, prompts, `-V/--version`, the non-TTY sequential path, or any of core scanning/hashing/date-reading/exiftool/copy logic.
- Keep `MODE_CONFIGS` keys and `types` keys exactly as-is (`media`/`documents`; `photo/video/pdf/word/excel/ppt`) with `icon`, `accent`, `dim`, `color` fields present — tests assert these shapes.
- All **23 existing tests must keep passing unchanged** (verified: they assert types/formatting/returns, never color values).
- Borders: `box.ROUNDED` on `_left_panel`, `_right_panel`, `_summary_panel`, the cli mode-menu `Panel`, and the new title bar. (Unicode box-drawing chars — must be eyeballed live in Windows Terminal, not just in review.)
- Traffic-light dots are **fixed** `#FF5F56` (red), `#FFBD2E` (yellow), `#27C93F` (green) — NOT theme-mapped (recognizable macOS convention).
- Identity colors locked: logo `#61AFEF`; camera (Media) `#56B6C2`; folder (Documents) `#C678DD` (distinct from logo to avoid flat/collision).
- Semantic status colors fixed: success `#98C379`, warning/dup `#E5C07B`, fallback `#D19A66`, error `#E06C75`, dim `#5C6370`, panel_bg `#282828`.
- Keep the terminal's own background; `#282828` is used only as a subtle panel-fill accent where Rich supports it.
- README font note appended (see Task 5).

---

### Task 1: Add `THEME` to core.py and re-tune colors/accents

**Files:**
- Modify: `src/picsort/core.py:59-124` (color constants block + `MODE_CONFIGS`)

**Interfaces:**
- Consumes: nothing new (pure constants + dict changes).
- Produces:
  - `core.THEME` — a `dict` mapping the 9 semantic roles to hex strings:
    ```python
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
    ```
  - `core.GREEN` = `THEME["success"]`, `core.YELLOW` = `THEME["warning"]`, `core.RED` = `THEME["error"]`, `core.DIM` = `THEME["dim"]` (all hex strings now).
  - `core.FALLBACK` = `THEME["fallback"]` (new, distinct from `YELLOW`).
  - Removed/reassigned: `core.CYAN` is removed (elapsed now uses `DIM`, see Task 2).
  - `MODE_CONFIGS` per-mode `accent`/`dim` and per-type `color` values updated (below).

- [ ] **Step 0: Read the current file region** (confirms line anchors before editing)

Read `src/picsort/core.py:59-124`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_theme.py`:

```python
from picsort import core


def test_theme_has_all_semantic_roles():
    for role in ("header", "success", "warning", "fallback", "error",
                 "dim", "panel_bg", "teal", "purple"):
        assert role in core.THEME
        assert isinstance(core.THEME[role], str)
        assert core.THEME[role].startswith("#")


def test_status_color_aliases_point_at_theme():
    assert core.GREEN == core.THEME["success"]
    assert core.YELLOW == core.THEME["warning"]
    assert core.RED == core.THEME["error"]
    assert core.DIM == core.THEME["dim"]
    assert core.FALLBACK == core.THEME["fallback"]


def test_mode_and_type_colors_come_from_theme():
    media = core.MODE_CONFIGS["media"]
    docs = core.MODE_CONFIGS["documents"]
    assert media["accent"] == core.THEME["teal"]
    assert docs["accent"] == core.THEME["purple"]
    assert media["types"]["photo"]["color"] == core.THEME["success"]
    assert media["types"]["video"]["color"] == core.THEME["header"]
    assert docs["types"]["pdf"]["color"] == core.THEME["error"]
    assert docs["types"]["ppt"]["color"] == core.THEME["purple"]
    assert docs["types"]["word"]["color"] == core.THEME["header"]
    assert docs["types"]["excel"]["color"] == core.THEME["success"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_theme.py -v`
Expected: `FAIL` with `AttributeError: module 'picsort.core' has no attribute 'THEME'` (and the color-alias test fails on old string values).

- [ ] **Step 3: Implement in core.py**

Replace the color-constant block (lines 59-63):

```python
GREEN = "bright_green"
YELLOW = "yellow"
RED = "bright_red"
CYAN = "bright_cyan"
DIM = "bright_black"
```

with:

```python
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
```

Then update `MODE_CONFIGS` so `media` uses teal accent, `documents` uses purple accent, and each type color comes from `THEME`. Replace the `MODE_CONFIGS` dict (lines 97-124) with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_theme.py -v`
Expected: `PASS` (5 passed).

- [ ] **Step 5: Run the full suite to confirm nothing else broke yet**

Run: `py -m pytest -q`
Expected: green (existing tests still pass; `CYAN` removal will be handled in Task 2). Note: the `media["accent"]`/`docs["accent"]` change does not affect `test_mode_configs_immutable_shape` (shape only).

- [ ] **Step 6: Commit**

```bash
git add src/picsort/core.py tests/test_theme.py
git commit -m "feat(core): add THEME palette, re-tune mode/type colors and status aliases"
```

---

### Task 2: Re-skin ui.py renderables to the theme + rounded borders

**Files:**
- Modify: `src/picsort/ui.py:18-22` (aliases), `src/picsort/ui.py:86-98` (`_current_file_line`), `src/picsort/ui.py:101-109` (`_per_type_table`), `src/picsort/ui.py:112-136` (`_stats_table`), `src/picsort/ui.py:151-168` (`_right_panel`), `src/picsort/ui.py:171-178` (`_left_panel`), `src/picsort/ui.py:216-239` (`_summary_panel`), `src/picsort/ui.py:259-265` (`_center_block` — unchanged, listed for awareness)

**Interfaces:**
- Consumes: `core.THEME`, `core.FALLBACK`, `core.GREEN`, `core.YELLOW`, `core.RED`, `core.DIM` from Task 1.
- Produces: unchanged public function signatures (`_current_file_line`, `_per_type_table`, `_stats_table`, `_right_panel`, `_left_panel`, `_summary_panel`, `print_summary`). `_build_layout`'s signature stays `(cfg, left, right)` but gets a third stacked child (Task 3).

- [ ] **Step 1: Update the color aliases at the top of ui.py**

Replace lines 18-22:

```python
GREEN = core.GREEN
YELLOW = core.YELLOW
RED = core.RED
CYAN = core.CYAN
DIM = core.DIM
```

with:

```python
GREEN = core.GREEN
YELLOW = core.YELLOW
RED = core.RED
DIM = core.DIM
FALLBACK = core.FALLBACK
```

- [ ] **Step 2: `_center_block` and drive-free/elapsed** — no color change needed; leave as-is.

- [ ] **Step 3: `_current_file_line` (lines 86-98)** — use `FALLBACK` for fallback, keep `YELLOW` for dup:

```python
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
```

- [ ] **Step 4: `_stats_table` (lines 112-136)** — Copied uses `GREEN`, Duplicates `YELLOW`, Fallback date `FALLBACK`, Errors `RED`, Elapsed `DIM` (replacing `CYAN`), Source/Dest free keep `"dim"`:

```python
    grid.add_row(Text("Copied", style=GREEN), Text(str(counts["copied"]), style=GREEN))
    grid.add_row(Text("Duplicates", style=YELLOW), Text(str(counts["duplicates"]), style=YELLOW))
    grid.add_row(Text("Fallback date", style=FALLBACK), Text(str(counts["fallback"]), style=FALLBACK))
    grid.add_row(Text("Errors", style=RED), Text(str(counts["errors"]), style=RED))
    grid.add_row(Text("Elapsed", style=DIM), Text(_fmt_elapsed(elapsed), style=DIM))
```

- [ ] **Step 5: `_right_panel` (lines 151-168)** — switch `box.ASCII` → `box.ROUNDED`:

```python
    return Panel(
        body,
        title=f"[{cfg['accent']}] Session - {cfg['label']}",
        border_style=cfg["accent"],
        box=box.ROUNDED,
        expand=True,
    )
```

- [ ] **Step 6: `_left_panel` (lines 171-178)** — switch `box.ASCII` → `box.ROUNDED`:

```python
    return Panel(
        body,
        title=f"[{cfg['accent']}] {cfg['label'].split('(')[0].strip()}",
        border_style=cfg["accent"],
        box=box.ROUNDED,
        expand=True,
    )
```

- [ ] **Step 7: `_summary_panel` (lines 216-239)** — recolored rows and rounded border:

```python
    return Panel(table, title=f"[{GREEN}] Summary - {cfg['label']}",
                 border_style=GREEN, box=box.ROUNDED, expand=True)
```

Update the per-row color selection so Mode uses header blue, Errors uses error red, everything else dim:

```python
    for label, value in rows:
        color = RED if label.startswith("Errors") else (GREEN if label == "Mode" else DIM)
        table.add_row(
            Text(label, style="bold" if label == "Mode" else None),
            Text(str(value), style=color) if color else Text(str(value)),
        )
```

- [ ] **Step 8: Update the two `_legend*` "# fallback" colors** so the legend matches the actual fallback color (lines 199 and 210):

In `_legend` replace `t.append("# fallback", style=YELLOW)` with `t.append("# fallback", style=FALLBACK)`.

In `_legend_text` replace `t.append("# fallback", style=YELLOW)` with `t.append("# fallback", style=FALLBACK)`.

- [ ] **Step 9: Run the UI tests to verify nothing broke**

Run: `py -m pytest tests/test_ui.py -v`
Expected: `PASS` (5 passed — they assert `isinstance(..., Panel/Table)` and pure formatting, not colors).

- [ ] **Step 10: Commit**

```bash
git add src/picsort/ui.py
git commit -m "feat(ui): use theme tokens, rounded borders, distinct fallback color"
```

---

### Task 3: Add traffic-light title bar + stacked layout in ui.py

**Files:**
- Modify: `src/picsort/ui.py:181-187` (`_build_layout`), add `_title_bar` helper near it.
- Test: `tests/test_theme.py` (add one test) OR `tests/test_ui.py`. Use `tests/test_ui.py`.

**Interfaces:**
- Consumes: `core.THEME` from Task 1.
- Produces:
  - `ui._title_bar() -> Panel` — a rounded Panel whose renderable is a `Text` with three traffic-light dots (`#FF5F56`, `#FFBD2E`, `#27C93F`) followed by `"   picsort"` in header blue.
  - `ui._build_layout(cfg, left, right) -> Layout` — unchanged signature; returns a Layout whose root `split`s a top `"title"` region (containing `_title_bar()` renderable, `size=3`) above a `"body"` region containing the existing left/right `split_row` (ratios 2 and 3).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui.py`:

```python
from rich.layout import Layout


def test_build_layout_has_title_and_body():
    from picsort import ui
    cfg = core.MODE_CONFIGS["media"]
    left = ui._left_panel(cfg, Text("L"))
    right = ui._right_panel(cfg, {"copied": 0, "duplicates": 0, "fallback": 0, "errors": 0},
                            {}, [], 0, 0, 0.0, None, None)
    layout = ui._build_layout(cfg, left, right)
    assert isinstance(layout, Layout)
    names = [c.name for c in layout.children]
    assert "title" in names
    assert "body" in names


def test_title_bar_has_traffic_light_dots_and_title():
    p = ui._title_bar()
    assert isinstance(p, Panel)
    text = p.renderable
    assert isinstance(text, Text)
    assert "picsort" in text.plain
    for dot in ("FF5F56", "FFBD2E", "27C93F"):
        assert dot in str(text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_ui.py::test_build_layout_has_title_and_body tests/test_ui.py::test_title_bar_has_traffic_light_dots_and_title -v`
Expected: `FAIL` — `_title_bar` not defined yet; `_build_layout` still has no `"title"` child.

- [ ] **Step 3: Implement in ui.py**

Replace `_build_layout` (lines 181-187) with:

```python
def _title_bar() -> Panel:
    """macOS-style window title bar: traffic-light dots + centered app name."""
    t = Text()
    for dot in ("#FF5F56", "#FFBD2E", "#27C93F"):
        t.append(" ●", style=dot)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_ui.py -v`
Expected: `PASS` (7 passed — the 5 existing + 2 new).

- [ ] **Step 5: Run the full suite**

Run: `py -m pytest -q`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/picsort/ui.py tests/test_ui.py
git commit -m "feat(ui): add traffic-light title bar and stacked layout chrome"
```

---

### Task 4: Re-skin cli.py (logo, mode menu, status colors, rounded borders)

**Files:**
- Modify: `src/picsort/cli.py:19-23` (aliases), `src/picsort/cli.py:57` (warning color), `src/picsort/cli.py:240-266` (`select_mode`), `src/picsort/cli.py:295-303` (`print_logo`), `src/picsort/cli.py:274` (`_exit_prompt` — leave the ANSI green, see note)

**Interfaces:**
- Consumes: `core.THEME`, `core.GREEN`, `core.YELLOW`, `core.RED`, `core.DIM` from Task 1; `ui._legend`/`ui._build_layout` unchanged signatures from prior tasks.
- Produces: unchanged signatures. `select_mode()` still returns a valid mode key (`"media"`/`"documents"`) — preserved for `test_select_mode_returns_valid_key`.

- [ ] **Step 1: Update color aliases (lines 19-23)**

Replace:

```python
GREEN = core.GREEN
YELLOW = core.YELLOW
RED = core.RED
CYAN = core.CYAN
DIM = core.DIM
```

with:

```python
GREEN = core.GREEN
YELLOW = core.YELLOW
RED = core.RED
DIM = core.DIM
```

(Line 57 `console_print(..., YELLOW)` works unchanged since `YELLOW` is now `THEME["warning"]`.)

- [ ] **Step 2: `print_logo` (lines 295-303)** — logo in header blue, tagline in bold header blue, divider in dim:

```python
def print_logo() -> None:
    CONSOLE.print()
    CONSOLE.print(Text(ui._center_block(core.LOGO_ART), style=core.THEME["header"]))
    sub = Text()
    padding = " " * max(0, (CONSOLE.width - len(core.TAGLINE)) // 2)
    sub.append(padding + core.TAGLINE, style=f"bold {core.THEME['header']}")
    CONSOLE.print(sub)
    CONSOLE.print(Text(" " * max(0, (CONSOLE.width - 62) // 2) + "=" * 62, style=DIM))
    CONSOLE.print()
```

- [ ] **Step 3: `select_mode` (lines 240-266)** — recolor title/border to header blue and switch to `box.ROUNDED`:

```python
    panel = Panel(
        box_body,
        title=f"[{core.THEME['header']}] PIC-SORT MODE",
        title_align="left",
        border_style=core.THEME["header"],
        box=box.ROUNDED,
        padding=(1, 2),
        width=max(0, min(70, CONSOLE.width - 4)),
    )
```

(The `[N] label` body lines and subtitles are unchanged text/keys — do NOT alter them. The `"Select mode:"` prompt line keeps `bold {GREEN}` — leave as-is; it still resolves since `GREEN` now maps to success hex.)

- [ ] **Step 4: Non-TTY path status colors (lines 100-132)** — `color = GREEN` (success) for normal, `color = YELLOW` for fallback stays; the `[i/total] ` prefix uses `GREEN`. These already reference `GREEN`/`YELLOW`/`RED` which now resolve to theme hexes, so **no code change required** — verify only.

Verify by reading lines 96-133; confirm references are `GREEN`/`YELLOW`/`RED` (now hex-mapped). No edit needed.

- [ ] **Step 5: Run CLI tests**

Run: `py -m pytest tests/test_cli.py -v`
Expected: `PASS` (3 passed).

- [ ] **Step 6: Run the full suite**

Run: `py -m pytest -q`
Expected: green (26 passed — 23 existing + 1 theme test from Task 1 + 2 ui tests from Task 3).

- [ ] **Step 7: Commit**

```bash
git add src/picsort/cli.py
git commit -m "feat(cli): recolor logo/mode menu to theme, rounded mode panel"
```

---

### Task 5: README font note

**Files:**
- Modify: `README.md` (append the font note near the Screenshot/Demo section)

**Interfaces:** none.

- [ ] **Step 1: Locate the insertion point**

Find the `## Screenshot` (or equivalent demo) heading in `README.md`.

- [ ] **Step 2: Add the font note**

Insert the following block directly after that heading's short paragraph:

```markdown
**A note on the font:** the Python app cannot control the terminal's font — that's
set by your terminal emulator (Windows Terminal, macOS Terminal, iTerm2, etc.), not
by the app or its ANSI codes. For the full "Mac Terminal" aesthetic, set your
terminal's monospace font yourself — e.g. **JetBrains Mono** or **Fira Code**
(SF Mono/Menlo on macOS). Optional and purely cosmetic.
```

- [ ] **Step 3: Verify the README still mentions `pipx install picsort-cli`** (must not have been removed)

Run: `Select-String -Path README.md -Pattern "pipx install picsort-cli"`
Expected: a match.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add terminal font note for Mac Terminal aesthetic"
```

---

### Task 6: Manual visual verification in Windows Terminal (required)

**Files:** none (verification only).

**Why:** `box.ROUNDED` uses Unicode box-drawing characters (`╭╮╰╯`) that render fine in Windows Terminal but can garble in legacy `cmd.exe`. The traffic-light dots (●) are also multibyte. This must be verified live, not just in review.

- [ ] **Step 1: Install the branch in a temp pipx venv and run**

Run (from any temp dir outside the repo):
```bash
pipx run --spec "D:\pic-sort\.worktrees\picsort-cli-pypi" picsort --version
```
Expected: `picsort 0.1.0` with exit 0.

Then run a real sort in **Windows Terminal**:
```bash
picsort
```
Supply a Media-mode source with a couple of photos and a fresh destination folder.

- [ ] **Step 2: Visual checklist**

Confirm in a **Windows Terminal** window:
- Traffic-light title bar row renders at top: three dots (red `#FF5F56`, yellow `#FFBD2E`, green `#27C93F`) followed by `picsort` in blue.
- Left/right panels and the summary panel have **rounded** corners (not `+---+` ASCII).
- Camera icon (Media) is teal `#56B6C2`; the mode menu panel has rounded corners and a blue title.
- Files copied shown in green `#98C379`; duplicates amber `#E5C07B`; fallback-date entries orange `#D19A66`; errors red `#E06C75`.
- Per-type legend colors match: Photos green, Videos blue, (Documents: PDF red, Word blue, Excel green, PowerPoint purple).
- The bottom progress bar, the activity list (non-scrolling fixed-height), and the left-panel summary are unchanged in position.

If any rounded corner or dot renders as garbled `?`/broken chars, STOP and report — it means the runtime console lacks UTF-8 output and we must revisit the `box.ROUNDED` decision.

- [ ] **Step 3: Confirm exit path still works**

Press Enter at the "Press Enter to exit..." prompt; ensure clean exit and the final summary printed above it.

---

## Self-Review Notes (for the plan author)

### 1. Spec coverage
- §1.1 palette → Task 1 `THEME` (all 9 roles). ✓
- §1.2 per-type colors → Task 1 `MODE_CONFIGS` types. ✓
- §1.3 mode accents (media teal, docs purple) → Task 1. ✓
- §1.4 architecture (THEME consumption in ui/cli) → Tasks 2, 4. ✓
- §2.1 traffic-light title bar (fixed dots, `picsort` title) → Task 3. ✓
- §2.2 rounded borders everywhere → Tasks 2 (panels/summary), 3 (title bar), 4 (mode menu). ✓
- §2.3 `box.ROUNDED` caveat + Windows Terminal eyeball → Task 6. ✓
- §3 background (keep terminal bg, `#282828` panel-fill accent) → `panel_bg` defined in Task 1; used as a subtle fill accent. (Implementation note: Rich Panel does not force a global bg; `#282828` is available in `THEME` for any panel-fill accent line added. No full-bg override is performed — matches spec.)
- §4 logo/icons recolor (logo blue, camera teal, folder purple) → Tasks 1, 4. ✓
- §5 README font note → Task 5. ✓
- "23 tests keep passing" → Task 2 Step 8, Task 4 Step 5, plus full-suite runs. ✓

### 2. Placeholder scan
No TBD/TODO/placeholder steps; every code step has full code shown.

### 3. Type/name consistency
- `core.THEME`, `core.FALLBACK` introduced in Task 1, consumed in Tasks 2-4 consistently.
- `_build_layout(cfg, left, right)` signature unchanged across Tasks 2-4 (cli.py calls it with `(cfg, left, right)` in 4 places — none change).
- `_title_bar()` no-arg; called in Task 3. `box.ROUNDED` and dot hexes `#FF5F56/#FFBD2E/#27C93F` appear identically in Tasks 2, 3, 4.
- `select_mode()` return values (`media`/`documents`) preserved — `test_select_mode_returns_valid_key` stays green.
- `core.CYAN` removed in Task 1 — the only consumers were `ui.py:127` (fixed in Task 2 Step 4) and the alias lines (fixed in Tasks 2/4). No other references exist (verified via grep).
