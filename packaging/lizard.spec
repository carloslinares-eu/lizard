# PyInstaller recipe for a single-file Lizard binary for Linux.
#
#   pip install -r requirements-dev.txt
#   pyinstaller packaging/lizard.spec
#
# The result is dist/lizard. Build on the oldest distribution you want to run it
# on: the binary needs a glibc at least as new as the one it was built with.

from pathlib import Path

ROOT = Path(SPECPATH).parent
ASSETS = ROOT / "lizard" / "assets"

a = Analysis(
    [str(ROOT / "lizard" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=[(str(ASSETS), "lizard/assets")],
    excludes=["pytest", "PIL"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="lizard",
    console=False,
    upx=False,
)
