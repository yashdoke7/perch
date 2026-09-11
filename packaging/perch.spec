# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller build for PERCH: a one-folder, windowed app (dist/PERCH/PERCH.exe).
#
#   python -m PyInstaller packaging/perch.spec --noconfirm --clean
#
# One-folder rather than one-file on purpose: a one-file build unpacks itself
# to a temp directory on EVERY launch, which is slow for an app that starts at
# sign-in and trips antivirus heuristics far more often.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "app" / "ui" / "web"), "app/ui/web"),            # the whole UI
    (str(ROOT / "app" / "eval" / "probes"), "app/eval/probes"),  # E1/E3 data
]
binaries = []
hiddenimports = []

# Packages that load parts of themselves dynamically: pywebview picks its
# WebView2 backend at runtime, winrt resolves each Windows namespace by name,
# uiautomation ships its own DLLs, pystray selects a platform module.
for pkg in ("webview", "winrt", "uiautomation", "pystray", "clr_loader", "pythonnet"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

# Optional document tools, imported lazily by app/tools -- invisible to the
# import scanner, so listed. Missing ones are simply skipped.
for mod in ("pypdf", "docx", "pptx", "win32timezone"):
    try:
        __import__(mod)
        hiddenimports.append(mod)
    except ImportError:
        pass

a = Analysis(
    [str(ROOT / "packaging" / "perch_app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pytest", "IPython", "notebook"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PERCH",
    icon=str(ROOT / "packaging" / "perch.ico"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PERCH", upx=False)
