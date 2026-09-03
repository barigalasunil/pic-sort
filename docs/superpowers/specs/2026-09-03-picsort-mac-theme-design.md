# PicSort — macOS Terminal-Inspired UI Re-skin (Design)

## Purpose

Re-skin the PicSort terminal UI from its current single-tone green scheme to a
**macOS Terminal-inspired** look, layering a Mac "window" aesthetic on top of the
existing panel structure. This is a **visual re-skin only** — a deliberate
departure from the prior "single green wash" — with no structural or behavioral
changes to layout, prompts, or any core logic.

This builds on (and lives in the same PR as) the PyPI / `picsort-cli` packaging
restructure, on branch `picsort-cli-pypi`. All the packaging work (core logic,
exiftool retarget, update-check, workflows, README install docs) is **unchanged**
by this re-skin.

---

## Naming & scope

- **Files touched:** `src/picsort/core.py`, `src/picsort/ui.py`,
  `src/picsort/cli.py`, `README.md`.
- **Non-goals (must stay unchanged):**
  - All panel **content** and **layout structure**: left/right split, bottom
    progress bar, non-scrolling fixed-height activity list, summary on the left
    panel, logo/icon art bytes.
  - Mode selection flow, prompts, `-V/--version`, non-TTY sequential path.
  - **Every piece of core logic**: scanning, hashing/dedup, date-reading,
    exiftool, copy behavior, PyPI packaging/publishing/update-check.
  - `pyproject.toml`, `.github/workflows/*`, `LICENSE`, `.gitignore`.
  - Panel titles / legend wording (wording unchanged; only colors change).

- **Verified non-issue (read, not assumed):** the UI tests
  (`tests/test_ui.py`) assert only renderable **types** and pure formatting
  (`isinstance(p, Panel)`, `isinstance(t, Table)`, `_center_block` padding,
  `_human_bytes` output) — never color values. They keep passing unchanged.

---

## 1. Theme palette & architecture

### 1.1 Semantic palette (One-Dark / Mac "Pro" inspired)

Every semantic meaning maps to exactly one hex — consistent throughout, this is
the point of the multi-color redesign.

| Role | Hex | Used for |
|------|-----|----------|
| `header` | `#61AFEF` | Headers, section titles, logo, window chrome text |
| `success` | `#98C379` | Copied / success |
| `warning` | `#E5C07B` | Duplicates / skipped |
| `fallback` | `#D19A66` | Fallback-date-used |
| `error` | `#E06C75` | Errors |
| `dim` | `#5C6370` | Secondary text (elapsed, drive free space) |
| `panel_bg` | `#282828` | Subtle panel-fill accent (warm dark gray) |
| `teal` | `#56B6C2` | Media/camera icon accent |
| `purple` | `#C678DD` | PowerPoint type color |

### 1.2 Per-type colors (from the cohesive palette)

Replaces the old ad hoc `bright_green` / `orange1` / etc. values in
`MODE_CONFIGS["types"]`:

| type | color |
|------|-------|
| Photos  | `#98C379` (success green) |
| Videos  | `#61AFEF` (header blue) |
| PDF     | `#E06C75` (error red) |
| Word    | `#61AFEF` (header blue) |
| Excel   | `#98C379` (success green) |
| PowerPoint | `#C678DD` (purple) |

### 1.3 Mode accents

Per-mode accent, both pulled from the same theme:

- **Media** → `#56B6C2` (teal) — distinct from the green `success` status color.
- **Documents** → `#61AFEF` (blue).

### 1.4 Architecture

- **`core.py`:** add a `THEME` dict mapping the semantic roles above to hex
  strings. Update `MODE_CONFIGS` per-type `color` and per-mode `accent` to the
  theme hexes. Replace the old `GREEN/YELLOW/RED/CYAN/DIM` string constants with
  references into `THEME` (single source of truth). `LOGO_ART`/`CAMERA_ICON`/
  `FOLDER_ICON` art bytes unchanged — only the color applied by consumers
  changes.
- **`ui.py`:** every renderable consumes `THEME` tokens; `box.ASCII` →
  `box.ROUNDED`; add the title-bar chrome and stacked layout (see §2).
- **`cli.py`:** `print_logo` (logo in `header` blue), mode menu, and status/progress
  lines use the theme tokens; mode-menu panel gets `box.ROUNDED`; mode icons
  colored with the per-mode accent.

**Rule:** semantic meaning stays fixed — success is always green, dup always
amber, fallback always orange, error always red. The whole UI reads as one
coherent theme, never a single green wash.

---

## 2. Window chrome (traffic-light title bar + rounded borders)

### 2.1 Traffic-light title bar

A single row at the very top of the layout, above the left/right split:

```
● ● ●   picsort
```

- Three traffic-light dots in **fixed** colors (deliberately **not** theme-mapped —
  recognizable macOS conventions): red `#FF5F56`, yellow `#FFBD2E`, green
  `#27C93F`.
- **Default title is `picsort`** (not `picsort — zsh`). This app actually runs on
  Windows PowerShell/CMD, so a `zsh` suffix would be misleading rather than
  authentic.
- Title text color: `header` blue (`#61AFEF`).
- Sits on the terminal background (no forced fill), consistent with §3
  background decision.

### 2.2 Rounded borders

- `box.ROUNDED` on: `_left_panel`, `_right_panel`, `_summary_panel`, the
  mode-menu `Panel` in `cli.py`, and the new title bar.
- `_build_layout` grows from a single `split_row(left, right)` into a vertical
  stack:
  ```
  root
  ├── title_bar   (top, fixed 1 row)
  └── body
      ├── left     (ratio 2)
      └── right    (ratio 3)
  ```
  This is a **structural addition to `_build_layout` only** — the left/right
  panels keep their exact content; bottom progress bar, activity list, and
  summary positions are preserved inside the panels.
- The app has no outer frame today (panels carry their own borders), so the
  "outer frame" request maps to the two panel borders + title bar, all rounded.

### 2.3 `box.ROUNDED` caveat (flag, verify at runtime)

`box.ROUNDED` uses Unicode box-drawing characters (`╭╮╰╯`). These render fine in
**Windows Terminal** (which the user uses) but can garble as `?` in legacy
`cmd.exe`/old console hosts without UTF-8 output. **This must be eyeballed in a
live Windows Terminal run**, not just checked in code review — box-drawing
rendering is exactly the kind of thing that looks right in theory and breaks
silently in one specific terminal. If it breaks in the user's environment, this
is the documented fallback: keep `box.ROUNDED` (approved), and note Windows
Terminal is the supported console.

---

## 3. Background (kept simple)

Keep the **terminal's own background** — a Rich TUI cannot reliably paint the
whole terminal background and it fights the user's theme. Instead:

- Use `#282828` (warm dark gray) as a **subtle panel-fill accent** inside the
  panels where Rich supports it, so it reads warmer without breaking in any
  terminal.
- Add a README note so users can set their own terminal theme/background if they
  want the full "Pro"/"Homebrew" look (§5).

---

## 4. Logo & mode icons recolor

- **Logo** (`LOGO_ART`, "PIC-SORT" wordmark): recolored to **`#61AFEF`** (header
  blue) in `print_logo`. Art bytes unchanged.
- **Mode icons**:
  - Camera (Media) → **`#56B6C2`** (teal, locked — not "warm/teal both"; one
    exact hex). Distinct from the `success` green so iconography reads separately
    from status.
  - Folder (Documents) → **`#61AFEF`** (blue).
- Icons keep a **fixed identity color**, distinct from status-meaning colors, so
  semantics stay scannable.

---

## 5. README changes

Add a short note (near the Screenshot/Demo section) on the font:

> The Python app cannot control the terminal's font — that's set by your
> terminal emulator (macOS Terminal, iTerm2, Windows Terminal, etc.), not by the
> app or its ANSI codes. For the full "Mac Terminal" aesthetic, set your
> terminal's monospace font yourself — e.g. **JetBrains Mono** or **Fira Code**
> (SF Mono/Menlo on macOS). Optional and purely cosmetic.

The rest of the README (pipx install/run/upgrade/uninstall/release docs from the
packaging round) is unchanged.

---

## Error handling & edge cases

- Rendering failures must never break a run: colors are static strings, not
  computed from untrusted input. No new error paths.
- `box.ROUNDED` in a non-UTF-8 console may render oddly but will not crash; the
  non-TTY sequential path is unaffected by styling.
- The vertical-stack layout change to `_build_layout` must keep working for both
  TTY (Live) and non-TTY (final `_render_text`) rendering paths.

## Testing approach

- All **23 existing tests** keep passing unchanged (verified: UI tests assert
  types/formatting, not colors).
- Optionally add one smoke test asserting `_build_layout` still returns a
  `Layout` and contains a title-bar child (guards the structural change) —
  counted as part of the 23+ if added.
- **Manual visual check (required):** run `picsort` in **Windows Terminal** and
  confirm:
  - traffic-light dots render correctly,
  - rounded borders are intact,
  - logo/icon/per-type/status colors match the palette,
  - bottom progress bar, activity list, and left-panel summary are unchanged in
    position.
