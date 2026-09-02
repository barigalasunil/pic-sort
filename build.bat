@echo off
setlocal

REM ===========================================================================
REM  build.bat - build PicSort.exe (single portable .exe) with PyInstaller
REM
REM  One-time setup on a machine WITH Python installed:
REM    1. pip install pyinstaller rich requests
REM    2. run this script
REM
REM  Output: dist\PicSort.exe  (a self-contained, portable exe - no Python
REM  needed on the machine that runs it).
REM ===========================================================================

echo.
echo  Building PicSort.exe with PyInstaller ...
echo.

REM --onefile       : single exe (no folder of python dlls)
REM --console       : keep a visible terminal window with live progress
REM --name PicSort  : exe is named PicSort.exe

REM Prefer the plain 'pyinstaller' command (installed on PATH by pip). If it's
REM not on PATH but python/py is, fall back to `python -m PyInstaller`.
where pyinstaller >nul 2>nul
if %errorlevel%==0 (
    pyinstaller --onefile --console --name PicSort picsort.py
) else (
    python -m PyInstaller --onefile --console --name PicSort picsort.py 2>nul
    if errorlevel 1 py -m PyInstaller --onefile --console --name PicSort picsort.py
)

if errorlevel 1 (
    echo.
    echo  BUILD FAILED. Make sure you have run:  pip install pyinstaller rich requests
    pause
    exit /b 1
)

echo.
echo  Done. Your portable exe is at:
echo    dist\PicSort.exe
echo.
echo  To distribute: copy PicSort.exe to any folder on a Windows PC.
echo  A "tools" subfolder is created next to it on first run (ExifTool).
echo.
pause
