@echo off
setlocal
cd /d "%~dp0\.."

echo [1/4] Installing build dependencies...
pip install pyinstaller streamlit pandas altair pyarrow --quiet
if errorlevel 1 ( echo FAILED: pip install & exit /b 1 )

echo [2/4] Running PyInstaller...
pyinstaller build\BookKeeper.spec --noconfirm --clean
if errorlevel 1 ( echo FAILED: PyInstaller & exit /b 1 )

echo [3/4] Running Inno Setup...
set INNO="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %INNO% set INNO="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %INNO% (
    echo Inno Setup not found. Download from https://jrsoftware.org/isinfo.php
    echo PyInstaller output is at dist\BookKeeper\BookKeeper.exe
    exit /b 0
)
%INNO% build\installer.iss
if errorlevel 1 ( echo FAILED: Inno Setup & exit /b 1 )

echo [4/4] Done!
echo Installer: dist\BookKeeper_Setup.exe
endlocal
