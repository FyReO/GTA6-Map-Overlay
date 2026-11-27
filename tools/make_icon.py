import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt5 import QtGui

from gta6overlay.icon import render_icon


def main():
    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(exist_ok=True)
    render_icon(256).save(str(assets / "icon.png"))
    try:
        from PIL import Image
        Image.open(assets / "icon.png").save(
            assets / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    except ImportError:
        render_icon(256).save(str(assets / "icon.ico"))
    print("wrote", assets / "icon.png", "and", assets / "icon.ico")


if __name__ == "__main__":
    app = QtGui.QGuiApplication([])
    main()
