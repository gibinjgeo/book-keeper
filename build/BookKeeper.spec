# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

# Collect everything streamlit needs (static files, templates, hidden imports)
st_datas, st_binaries, st_hiddenimports = collect_all("streamlit")
pd_datas, pd_binaries, pd_hiddenimports = collect_all("pandas")

datas = (
    st_datas + pd_datas
    + collect_data_files("altair")
    + collect_data_files("pyarrow")
    + [
        (os.path.join(ROOT, "main.py"),       "."),
        (os.path.join(ROOT, "data"),          "data"),
        (os.path.join(ROOT, "backend"),       "backend"),
        (os.path.join(ROOT, "services"),      "services"),
        (os.path.join(ROOT, "ui"),            "ui"),
    ]
)

binaries = st_binaries + pd_binaries

hiddenimports = st_hiddenimports + pd_hiddenimports + [
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.web.cli",
    "sqlite3",
    "decimal",
    "csv",
    "shutil",
    "pathlib",
    "pandas",
    "altair",
    "pyarrow",
]

a = Analysis(
    [os.path.join(ROOT, "build", "launcher.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "PIL", "tkinter", "IPython", "jupyter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BookKeeper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No black console window
    icon=None,              # Replace with: icon="build/icon.ico" if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BookKeeper",
)
