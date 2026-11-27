import sys

hidden = []
if sys.platform == "win32":
    hidden += ["pynput.keyboard._win32", "pynput.mouse._win32"]

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=[("assets", "assets")],
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "PIL", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GTA6MapOverlay",
    icon="assets/icon.ico",
    console=False,
    upx=False,
    debug=False,
)
