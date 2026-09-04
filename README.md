<div align="center">

# 📸 PicSort

**sort your entire photo, video & document library by date, automatically**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/picsort-cli)](https://pypi.org/project/picsort-cli/)

*A global CLI tool that sorts **photos, videos and documents** from any folders into a clean `YYYY/Month/DD` structure — safe to re-run, dedupe-aware. Pick a **Media** or **Documents** mode at startup.*

</div>

---

## ✨ Features

- 🖥️ **Two modes at startup** — choose **Media** (photos & videos) or **Documents** (PDF, Word, Excel, PowerPoint).
- 📅 **Metadata-based sorting** — **Media** reads the real capture date from EXIF / MOV metadata; **Documents** reads the **creation** date per format. Both fall back to the file's modified date only when no metadata exists.
- 🔁 **Safe to re-run** — **copy** only, never move or rename originals. Repeated runs merge into existing folders with no data loss.
- 🧬 **Hash deduplication** — every file is hashed against what's already in the destination day-folder; content-identical files are skipped. Large files (>100 MB) use a fast size + partial-hash fingerprint.
- 🔮 **Global CLI** — install once with `pipx`, then run `picsort` from any folder, any terminal.
- ⚡ **Auto-fetches ExifTool on first run** — downloads ExifTool into your per-user app-data folder automatically, then skips setup on later runs.
- 🚀 **Auto-update notice** — checks PyPI silently and shows a one-line "update available" hint when a newer release exists.
- 🎨 **Live split-panel terminal UI** (built on `rich`) — a left panel shows the mode icon (camera / folder) while a right panel drives a live progress bar, per-file-type running totals, elapsed time, drive free space, and copied/dup/fallback/error counters, with a per-type color legend.
- 📊 **Boxed summary panel** at the end with per-mode totals (e.g. `Photos: 120  Videos: 8`).

---

## 📁 How it works

Every file in your source folder(s) is read for its date (capture date for **Media**, creation date for **Documents**), then **copied** into the destination, always merged into:

```
<Destination>/
└── 2026/
    └── August/
        └── 26/
            ├── IMG_20240826_143200.jpg
            ├── IMG_20240826_143355.jpg
            └── VID_20240826_150012.mp4
```

The structure is **always** `YYYY / MonthName / DD` — regardless of which source folder a file came from. Multiple source folders feed the same flat, date-based tree.

---

## 🚀 Installation

```
pipx install picsort-cli
```

*That's it — installs globally, works from any folder.*

<details>
<summary><b>Don't have pipx yet?</b></summary>

```
python -m pip install --user pipx
python -m pipx ensurepath
```

Then close and reopen your terminal before running the install command above.

</details>

## 💻 Usage

```
picsort
```

*Run it from anywhere — no need to be in a specific folder.*

1. Choose a mode: **`[1] Media`** (photos & videos) or **`[2] Documents`** (PDF, Word, Excel, PowerPoint).
2. First run downloads ExifTool automatically (needs internet once; stored in your per-user app-data folder).
3. Enter your **source folder(s)** (comma-separated for multiple) and a **destination folder**.
4. Watch it copy everything into `Destination/YYYY/MonthName/DD`.

### Upgrade

```
pipx upgrade picsort-cli
```

Keeps your install on the latest release.

### Uninstall

```
pipx uninstall picsort-cli
```

Removes the global install completely.

---

## 🔄 Notes on merge & dedup behavior

- **Never deletes or recreates** existing `Year/Month/Day` folders — it always **merges** into them.
- **Repeated runs are safe**: run the same sources against the same destination a hundred times; files already copied are skipped via hashing, so nothing is duplicated.
- **Multiple source folders** can feed the same destination over time. Files with identical content are skipped; different files that happen to share a filename get a `_1`, `_2`, … suffix **before the extension only** (e.g. `IMG_2024.jpg`, `IMG_2024_1.jpg`).
- **Never renames or moves** the original source files. PicSort only ever **copies** (`copy2`, preserving timestamps).
- **Metadata-first**: dates come from ExifTool metadata; only files with no readable metadata fall back to the file's modified date. Any fallback use is logged to `fallback_used.log` in your per-user app-data folder.

---

## 🚀 Releasing a New Version (maintainers)

1. Bump `__version__` in `src/picsort/__init__.py` (e.g. `0.1.0` → `0.2.0`).
2. Commit the change.
3. Tag and push:

```
git tag v0.2.0
git push origin v0.2.0
```

GitHub Actions builds the package and publishes to PyPI **automatically** via Trusted Publishing (OIDC) — no tokens required. The package name on PyPI is `picsort-cli`; the installed command stays `picsort`.

---

## 🛠 Troubleshooting

### `picsort: command not found` after install
Close and reopen your terminal, or re-run:

```
python -m pipx ensurepath
```

and restart the terminal.

### Internet required on first run
The first run downloads ExifTool automatically into your per-user app-data folder. To find the **current** version (versions rotate, old links stop working), PicSort scrapes exiftool.org for the latest Windows 64-bit download link instead of hardcoding a version. If you're offline or the site is unreachable, PicSort prints manual instructions:
1. Download the **Windows Executable** zip (64-bit) from https://exiftool.org
2. Extract the whole ZIP — **keep the `exiftool_files` folder** alongside it
3. Copy the exe **and** the `exiftool_files` folder into `<user-app-data>\picsort\tools\`, renaming `exiftool(-k).exe` → `exiftool.exe`
4. Re-run `picsort`.

### ❓ Files sorted by the wrong date
Some files (esp. screen recordings, edited exports, or files stripped of metadata) have no readable capture date. PicSort falls back to the file's **modified date** and logs it in `fallback_used.log`. If that's wrong, correct the file's modified timestamp and re-run — already-copied files are skipped, so use a fresh destination folder to re-sort.

---

## 📸 Screenshot / Demo

*(Add a screenshot or animated GIF of the terminal output here.)*

**A note on the font:** the Python app cannot control the terminal's font — that's
set by your terminal emulator (Windows Terminal, macOS Terminal, iTerm2, etc.), not
by the app or its ANSI codes. For the full "Mac Terminal" aesthetic, set your
terminal's monospace font yourself — e.g. **JetBrains Mono** or **Fira Code**
(SF Mono/Menlo on macOS). Optional and purely cosmetic.

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.
