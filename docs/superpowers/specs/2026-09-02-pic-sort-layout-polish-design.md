# PicSort Layout Polish — Design Spec

**Date:** 2026-09-02
**Status:** Approved
**Scope:** UI layout overhaul for the `rich` split-panel live interface

---

## 1. Bug Status

No `load_last_used` references remain in `picsort.py`. The persistence removal is complete. Both modes will be tested end-to-end to confirm no other crash sources exist.

---

## 2. Right Panel Changes

### 2a. Reorder Components

**Current order (top → bottom):**
1. Progress bar
2. Current file line
3. Stats table
4. Per-type table

**New order:**
1. Stats table (Processed/Copied/Duplicates/Fallback/Errors/Elapsed/Drive free)
2. Per-type table
3. Activity list (fixed-height, see 2b)
4. Progress bar (at very bottom)

### 2b. Fixed-Height Activity List

Replace the single-current-file display with a fixed-height "recent activity" list:

- **Height:** 5-8 lines, dynamically sized to fill available vertical space in the right panel
- **Content:** Completed files listed above, current file always at bottom
- **Current file indicator:** `→ Processing: filename.ext` with accent color
- **Completed files:** `✓ filename.ext → YYYY/Month/DD` with dim style
- **Scroll behavior:** As new files complete, oldest line drops off top; list never grows past available space
- **Initial state:** When no files processed yet, show `Scanning ...` in dim style

### 2c. Progress Bar at Bottom

Move `_progress_renderable()` to the bottom of the right panel Group, below the activity list.

---

## 3. Left Panel Changes

### 3a. During Run — Icon + Legend

The left panel shows the mode icon (camera or folder) at top, with the color legend below:

```
┌─ Media ─────────────┐
│                     │
│   [camera icon]     │
│                     │
│ Legend:             │
│  # Photos           │
│  # Videos           │
│  # fallback         │
│  # error            │
│                     │
└─────────────────────┘
```

The legend is the same `_legend()` output currently printed once at run start. Move it into the left panel.

### 3b. After Run — Summary Replaces Icon

When the live loop completes, the left panel transitions from icon+legend to the summary report:

- **Trigger:** After `live.stop()` in main()
- **Content:** The same `print_summary()` output (Mode, Copied, Duplicates, Fallback, Errors, Elapsed, per-type totals) rendered as a `Panel` with `box.ASCII`
- **Behavior:** The summary replaces the entire left panel content; the right panel remains as-is (frozen at final state)
- **Rendering:** Update the layout one final time with the summary panel as the left component

---

## 4. Startup Screen Polish

### 4a. Centered Logo + Tagline

- Center the `LOGO_ART` ASCII art horizontally in the terminal
- Center the tagline below it
- Add a blank line before and after

### 4b. Bordered Mode Selection Box

Wrap the mode menu in a `rich.Panel` with `box.ASCII` and green accent:

```
  ┌─────────────────────────────────────────────────┐
  │  Select mode:                                   │
  │                                                 │
  │  [1] Media                                      │
  │      Sort photos & videos by capture date       │
  │                                                 │
  │  [2] Documents                                  │
  │      Sort PDF, Word, Excel & PowerPoint          │
  │      by creation date                           │
  └─────────────────────────────────────────────────┘
```

### 4c. Mode Subtitles

Each mode option gets a short subtitle line:
- Media: `Sort photos & videos by capture date`
- Documents: `Sort PDF, Word, Excel & PowerPoint by creation date`

---

## 5. Icon Redesign

### 5a. Camera Icon

Redesign as a clearer camera silhouette:
- Body: solid rectangle (~18 chars wide)
- Lens: circle in center (`()` or `(o)`)
- Top: small viewfinder bump
- Total height: ~8 lines, width: ~22 chars
- Rendered in `bright_green` accent

### 5b. Folder Icon

Redesign as a clearer folder shape:
- Tab at top-left
- Body: rectangular with slight depth
- Total height: ~6 lines, width: ~22 chars
- Rendered in `bright_cyan` accent

---

## 6. Implementation Notes

### Key Functions to Modify

| Function | Change |
|----------|--------|
| `_right_panel()` | Reorder components, add activity list parameter, move progress to bottom |
| `_left_panel()` | Add legend during run; accept optional summary content for post-run |
| `_build_layout()` | No structural change (still split_row left:right) |
| `select_mode()` | Wrap in Panel, add subtitles, center logo |
| `print_logo()` | Center logo and tagline |
| `print_summary()` | Return renderable instead of printing; used by left panel |
| `main()` | Update live loop to pass activity list; update left panel after loop |

### Activity List Data Structure

Maintain a `deque(maxlen=activity_height)` in main():
- On each file completion: append `✓ filename → date`
- Current file: `→ Processing: filename` (always last line)
- Pass to `_right_panel()` as a list of `Text` objects

### Terminal Size Awareness

Activity list height = `terminal_height - fixed_components_height`. Minimum 3 lines, maximum 12 lines. Use `Console().size` to determine at runtime.

---

## 7. Verification

After implementation, run both modes end-to-end and confirm:

1. No crashes or errors
2. Right-panel activity list never scrolls (fixed height, oldest drops off)
3. Left-panel shows summary correctly after completion (replaces icon)
4. Both mode icons are visually clear at a glance
5. Startup screen is centered, bordered, with subtitles
6. Progress bar is at bottom of right panel
7. `last_used` references: zero (grep confirms)
