<div align="center">

# 📸 PicSort

**sort your entire photo & video library by date, automatically**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078d6)]()

*A single portable .exe that merges photos & videos from any folders into a clean `YYYY/Month/DD` structure — safe to re-run, dedupe-aware, and needs no Python installed on the machine that runs it.*

</div>

---

## ✨ Features

- 📅 **Metadata-based sorting** — reads the real capture date from EXIF / MOV metadata via ExifTool (`DateTimeOriginal`, `CreateDate`, `MediaCreateDate`, `TrackCreateDate`, `CreationDate`), falling back to the file's modified date only when no metadata exists.
- 🔁 **Safe to re-run** — **copy** only, never move or rename originals. Repeated runs merge into existing folders with no data loss.
- 🧬 **Hash deduplication** — every file is hashed and compared against what's already in the destination day-folder; content-identical files are skipped (no duplicate copies). Large files (>100 MB) use a fast size + partial-hash fingerprint.
- 📦 **Single portable exe** — one file you can drop on any Windows PC. No Python, no pip, no installers.
- 🖥️ **Zero Python install needed to run** — the `.exe` bundles everything.
- ⚡ **Auto-fetches ExifTool on first run** — downloads ExifTool into a `tools/` folder next to the exe automatically, then skips setup on later runs.
- 🎨 **Matrix-style terminal UI** — bright-green banner, live per-file progress, and a boxed summary panel.

---

## 📁 How it works

Every image/video in your source folder(s) is read for its capture date, then **copied** into the destination, always merged into:

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

**Project layout (source, before building):**

```
pic-sort/
├── picsort.py        # the full tool (single file)
├── build.bat         # one-time: produces PicSort.exe via PyInstaller
├── .gitignore
└── README.md
```

**Runtable layout (what end users actually get):**

```
PicSort/               ← any folder you drop the exe into
├── PicSort.exe
└── tools/             ← created automatically on first run
    └── exiftool.exe   ← auto-downloaded here
```

---

## 🚀 Quick Start — For Users

You don't need Python. You just need the exe.

1. Put `PicSort.exe` in any folder on your Windows PC.
2. Double-click it — a terminal window opens with the PicSort banner.
3. First run downloads ExifTool automatically (needs internet once; a `tools/` folder appears next to the exe).
4. Enter your **source folder(s)** (comma-separated for multiple) and a **destination folder**.
5. Watch it copy everything into `Destination/YYYY/MonthName/DD`.
6. Re-run anytime — it's safe, and it remembers your last-used folders.

> 💡 First run may trigger a **Windows SmartScreen** warning (it's an unsigned exe). Click **More info → Run anyway**. See [Troubleshooting](#🛠-troubleshooting) below.

---

## 🔧 Building from Source

Only for developers who want to build the exe themselves. You need a machine **with Python installed**.

```bat
:: 1. Clone this repo
git clone https://github.com/you/pic-sort.git
cd pic-sort

:: 2. Install build dependencies
pip install pyinstaller colorama requests

:: 3. Build the exe
build.bat
```

That produces `dist\PicSort.exe` — a single, portable exe. Distribute just that file.

---

## 🚀 Releases (automated with GitHub Actions)

A GitHub Actions workflow (`.github/workflows/build-release.yml`) builds and publishes `PicSort.exe` automatically whenever you tag a commit — so users (and future-you) can grab a fresh Windows exe straight from the repo's **Releases** page, no build or Python needed.

**To ship a new release:**

```bat
git tag v1.0.0
git push origin v1.0.0
```

That's it. GitHub Actions spins up a `windows-latest` runner, installs the build deps, runs the same PyInstaller command as `build.bat`, then creates a Release for that tag and attaches `PicSort.exe` as a downloadable asset (with auto-generated release notes). The Actions run is visible under the repo's **Actions** tab while it builds.

**Notes:**
- The build runs on **Windows** so the exe is a proper Windows binary — building on Linux/macOS would not produce a working `.exe`.
- The **manual trigger** (`workflow_dispatch`) on the Actions tab lets you build & upload the exe as an artifact *without* publishing a Release — handy for testing.
- Local development can keep using `build.bat` normally; the workflow is just the automated/CI path.

---

## 🔄 Notes on merge & dedup behavior

- **Never deletes or recreates** existing `Year/Month/Day` folders — it always **merges** into them.
- **Repeated runs are safe**: run the same sources against the same destination a hundred times; files already copied are skipped via hashing, so nothing is duplicated.
- **Multiple source folders** can feed the same destination over time. Files with identical content are skipped; different files that happen to share a filename get a `_1`, `_2`, … suffix **before the extension only** (e.g. `IMG_2024.jpg`, `IMG_2024_1.jpg`).
- **Never renames or moves** the original source files. PicSort only ever **copies** (`copy2`, preserving timestamps).
- **Metadata-first**: dates come from ExifTool metadata; only files with no readable metadata fall back to the file's modified date. Any fallback use is logged to `fallback_used.log` next to the exe.

---

## 🛠 Troubleshooting

### 🔒 Windows SmartScreen / Defender warning on first run
`PicSort.exe` is **unsigned**, so Windows shows a blue "Windows protected your PC" screen the first time.

**Fix:** click **More info** (blue link) → **Run anyway**. This is a normal warning for any independently-built exe; scan it with VirusTotal if you're cautious, then continue.

### 🌐 Internet required on first run
The first run downloads ExifTool automatically and places it in `tools\` next to `PicSort.exe`. To find the **current** version (versions rotate, old links stop working), PicSort scrapes the exiftool.org homepage for the latest Windows 64-bit download link instead of hardcoding a version. If you're offline or the site is unreachable, PicSort prints manual instructions:

1. Download the **Windows Executable** zip (64-bit) from https://exiftool.org
2. Extract the whole ZIP — **keep the `exiftool_files` folder**; the small `exiftool(-k).exe` is a launcher that needs it alongside
3. Copy the exe **and** the `exiftool_files` folder into `tools\` next to `PicSort.exe`, renaming `exiftool(-k).exe` → `exiftool.exe`:
   ```
   tools\
   ├── exiftool.exe
   └── exiftool_files\     ← must sit right beside exiftool.exe
   ```
4. Re-run PicSort.

### ❓ Files sorted by the wrong date
Some files (esp. screen recordings, edited exports, or files stripped of metadata) have no readable capture date. PicSort falls back to the file's **modified date** and logs it in `fallback_used.log`. If that's wrong, correct the file's modified timestamp and re-run — already-copied files are skipped, so use a fresh destination folder to re-sort.

### 🛑 Exe won't start at all
Make sure you copied the whole exe (it's a single file — nothing else is needed). Re-download if the file looks truncated.

---

## 📸 Screenshot / Demo

*(Add a screenshot or animated GIF of the Matrix-style terminal output here.)*

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.
