# PicSort → PyPI-Published Global CLI Tool ("picsort-cli") — Design

## Purpose

Restructure PicSort into a properly packaged, PyPI-published Python CLI tool,
installable globally with a single short command:

```
pipx install picsort-cli
```

and runnable from any folder as just:

```
picsort
```

This replaces the prior PyInstaller single-EXE distribution entirely.

**Naming rule (applied consistently everywhere):**
- **Distribution / package name** (PyPI project, `pip`/`pipx`/`pyproject.toml`
  `name`) = `picsort-cli`. Used only in **install / upgrade / uninstall**
  commands.
- **Command name** (what the user types) = `picsort`. Used everywhere else
  (running it, examples, screenshots, importing, the module folder name).

The Python module internally stays named `picsort`.

---

## 1. Project structure

```
pic-sort/
├── src/
│   └── picsort/
│       ├── __init__.py          (contains __version__ = "0.1.0")
│       ├── cli.py               (entry point + prompts)
│       ├── core.py              (scanning, hashing, date-reading, copy logic)
│       ├── ui.py                (rich Layout/Live UI, panels, logos, icons)
│       └── update_check.py      (PyPI version check)
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
└── .github/
    └── workflows/
        ├── ci.yml                (test install/import on push/PR)
        └── publish.yml           (publish to PyPI on version tag push)
```

### 1.1 Module responsibilities (map from existing `picsort.py`)

The existing single-file `picsort.py` (1027 lines) splits cleanly by concern,
with no behavioral change:

- **`__init__.py`** — only `__version__ = "0.1.0"`. Single source of truth for
  the version, referenced dynamically by `pyproject.toml`.
- **`core.py`** — non-UI logic moved mostly verbatim:
  - Extension sets: `IMAGE_EXTS`, `VIDEO_EXTS`, `DOCUMENT_EXTS`.
  - Mode configs: `MODE_CONFIGS`, `MEDIA_DATE_TAGS`, `DOCS_DATE_TAGS`,
    `_TYPE_BY_EXT`, `_bump_type_counts`.
  - Hashing / dedup: `file_identity`, `unique_copy_path`, `_candidate_names`,
    `_probe`, `_IDENTITY_CACHE`, `cache_put`, `PARTIAL_HASH_THRESHOLD`,
    `PARTIAL_HASH_CHUNK`.
  - Destination: `destination_for`.
  - Scanning: `scan_sources`.
  - ExifTool: `ensure_exiftool`, `_discover_exiftool_url`, `_manual_fallback`,
    `EXIFTOOL_PAGE_URL`, `tools_exiftool`, `app_dir` (retargeted — see §5),
    `fallback_log_path`, `log_fallback`.
  - Date reading: `read_capture_date`, `_parse_exif_datetime`.
- **`ui.py`** — all Rich renderables and presentation helpers:
  - Logos/icons: `LOGO_ART`, `CAMERA_ICON`, `FOLDER_ICON`, `TAGLINE`.
  - Panels: `_left_panel`, `_right_panel`, `_summary_panel`, `_build_layout`,
    `_stats_table`, `_per_type_table`, `_legend`, `_legend_text`,
    `_activity_list`, `_current_file_line`, `_progress_renderable`.
  - Formatting: `_human_bytes`, `_fmt_elapsed`, `_drive_free`, `_type_lookup`,
    `_center_block`.
  - A `console`/`CONSOLE` instance and `console_print` helper (moved here so
    both `cli.py` and `update_check.py` can reuse it).
- **`cli.py`** — the interactive flow + argument/flag parsing:
  - `main()`, `select_mode`, `print_logo`, `prompt_input`, source/destination
    prompts, the `Live` split-panel interactive loop, the non-TTY sequential
    loop, `_exit_prompt`, `_MODE_SUBTITLES`.
  - New: `-V`/`--version` flag handling (see §8).
  - Wires in `update_check` once at startup (see §6).
- **`update_check.py`** — new module, no prior equivalent (see §6).

`ui.py` owns the console/printing primitives; `core.py` imports nothing from
`ui` (keeps the UI/storage split hermetic). `cli.py` imports from both
`core`, `ui`, and `update_check`.

---

## 2. `pyproject.toml`

- `name = "picsort-cli"` — the PyPI-facing distribution name.
- `version` **sourced from `picsort/__init__.py`** via
  `[tool.setuptools.dynamic]` → `version = {attr = "picsort.__version__"}`.
  This guarantees `pyproject` and running code can never disagree (the exact
  single-source-of-truth property requested).
- `description`, `readme = "README.md"`, `license = {text = "MIT"}`,
  `requires-python = ">=3.9"` (matches existing README badge).
- Build backend: `setuptools`.
- Dependencies: `rich`, `requests`.
- `[project.scripts]`:
  ```
  picsort = "picsort.cli:main"
  ```
  This is what makes the installed command be `picsort` even though the
  package installs as `picsort-cli`.

---

## 3. `.github/workflows/publish.yml`

Publish to PyPI via **Trusted Publisher (OIDC)** — no API token stored.

```yaml
on:
  push:
    tags: ["v*"]
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write          # required for OIDC trusted publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1   # no password/token input
```

- Runs on `ubuntu-latest` (pure Python package — OS does not matter).
- Steps: checkout → setup Python → `pip install build` → `python -m build` →
  publish via `pypa/gh-action-pypi-publish@release/v1`, which supports Trusted
  Publishing natively (no `password` needed).
- `permissions: id-token: write` set at the job level — required for OIDC.
- The registered PyPI Trusted Publisher project name is **`picsort-cli`**.
- Workflow filename is exactly **`publish.yml`** to match the name registered
  on PyPI's trusted-publisher settings page.

---

## 4. `.github/workflows/ci.yml`

On every push/PR, `ubuntu-latest`:
1. checkout
2. setup Python
3. `pip install .`   (installs the package from source, resolving the
   `picsort` script entry point)
4. `python -c "import picsort"`   (confirms the import name resolves)
5. `picsort --version`   (confirms the entry point resolves and short-circuits)

Fast sanity check only — no publishing involved.

---

## 5. Exiftool storage location (retarget)

No fixed "next to exe" folder. Auto-download to a per-user app-data directory:

- `tools_exiftool()` resolves to
  `%LOCALAPPDATA%\picsort\tools\exiftool.exe` on Windows.
- Fallback when `LOCALAPPDATA` is unset: `Path.home() / ".picsort" / "tools"`.
- The app-data base directory also hosts `fallback_used.log` and (for
  `update_check`) `update_check.json`, all under the same `picsort` data dir.

Keep the existing first-run auto-download + graceful manual-fallback
instructions logic in `ensure_exiftool`; only retarget the destination path.

---

## 6. Automatic update check on startup

New module `update_check.py`. Checks the **PyPI JSON API** for the package
`picsort-cli` (the actual published name):

```
https://pypi.org/pypi/picsort-cli/json
```

Behavior:
- Short timeout (2–3 s); must **never** block startup on failure.
- Compare latest PyPI version against installed `__version__`.
- If newer, show a small non-blocking notice styled consistently with the app,
  e.g.:
  ```
  ⚙ Update available: v0.2.0 (you have v0.1.0) — run: pipx upgrade picsort-cli
  ```
  The upgrade command references `picsort-cli` (the installed package name),
  even though the app itself runs as `picsort`.
- Cache the check once per 24 h in `<app-data>/update_check.json` to avoid
  hitting PyPI on every launch.
- Fail silently on any network, parse, or cache error.

Runs once, early in `main()`, after the logo/version prints but **before**
mode selection and before any exiftool work.

---

## 7. README.md — rewritten setup instructions

Fully rewritten. Remove all exe / GitHub Releases / `build.bat` references
entirely. Contents:

- **Install:**
  ```
  pipx install picsort-cli
  ```
  Mention prerequisites if pipx isn't already installed:
  `python -m pip install --user pipx` and `python -m pipx ensurepath`.
- **Run:** `picsort` from any folder, any terminal.
- **Upgrade:** `pipx upgrade picsort-cli`.
- **Uninstall:** `pipx uninstall picsort-cli`.
- **Releasing a new version (maintainer):** bump `__version__` in
  `picsort/__init__.py`, commit, then:
  ```
  git tag vX.Y.Z
  git push origin vX.Y.Z
  ```
  GitHub Actions builds and publishes to PyPI automatically via Trusted
  Publishing.
- **Troubleshooting:** `picsort: command not found` after install → close and
  reopen the terminal, or re-run `python -m pipx ensurepath` and restart the
  terminal.
- Keep the core "How it works" / features / merge-dedup-notes sections, minus
  any `.exe` or `tools\`-next-to-exe language.

Consistency throughout: the **package name** `picsort-cli` appears only in
install/upgrade/uninstall/release commands; the **command name** `picsort`
appears everywhere else (running it, examples, screenshots).

---

## 8. CLI argument handling (`-V` / `--version`)

`main()` in `cli.py` parses argv before any other work:
- `-V` / `--version` → print `picsort <__version__>` and exit `0`
  immediately.
- **Must short-circuit before** the update check, exiftool check, mode menu,
  or any prompt. A `--version` call is instant and never performs a PyPI
  network check.
- No other flags required; the interactive flow is the default when no
  arguments are given.
- This flag is what lets CI's `picsort --version` sanity check pass, and is a
  standard expectation for any real CLI tool.

---

## 9. Cleanup (chosen: remove all EXE cruft)

Delete / untrack:
- `build.bat`
- `PicSort.spec`
- `.github/workflows/build-release.yml`
- `tools/`, `dist/`, `build/`, `fallback_used.log` (remove from git tracking;
  `dist/`/`build/`/`tools/` already gitignored).

Keep unchanged:
- Mode selection (Media / Documents).
- Rich split-panel UI: bottom-anchored progress bar, non-scrolling fixed-height
  recent-activity list, summary on the left panel below the logo/icon, camera
  and folder icons, bordered startup screen.
- Media extensions + EXIF date-tag priority chain.
- Documents extensions + creation-date-first logic.
- Hash-based dedup (SHA-256 full ≤100 MB; size + first/last-1MB partial hash
  >100 MB).
- Multi-source comma-separated input, single destination.
- Copy-only, never-rename, never-move behavior with `shutil.copy2`.
- `Destination/YYYY/MonthName/DD/` structure, merge-safe across runs.

---

## 10. Local verification before tagging a release

Before tagging the first real version (`v0.1.0`):

```
pip install -e .
picsort --version          # instant, no network
```

Then run `picsort` from a **completely different folder** than the repo to
confirm:
- the entry point resolves globally, and
- exiftool downloads correctly to the new per-user app-data location.

Only after this passes, tag and push `v0.1.0` to trigger the PyPI publish
workflow.

---

## Error handling & edge cases

- **Update check:** any network/parse/cache failure is swallowed; never blocks
  startup or aborts the run.
- **Exiftool missing:** unchanged graceful first-run download + manual-fallback
  exit with clear instructions (now pointing at the per-user app-data dir).
- **`--version`:** exits immediately; cannot be delayed by network or prompts.
- **Non-TTY / piped output:** existing sequential-progress path preserved
  (important for CI and redirected consoles).

## Testing approach

- CI: `pip install .` → `import picsort` → `picsort --version` on every push/PR
  (green path + entry-point + version-flag verification).
- Local pre-release: editable install + run from an alternate working
  directory (entry point + exiftool app-data retarget check).
