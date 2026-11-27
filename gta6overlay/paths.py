import os
import sys
from pathlib import Path

from .config import APP_DIR_NAME


def _root():
    override = os.environ.get("GTA6_OVERLAY_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME


ROOT = _root()
DATA_DIR = ROOT / "data"
MEDIA_DIR = DATA_DIR / "card_media"
SETTINGS_FILE = ROOT / "settings.json"
FOUND_FILE = ROOT / "found.json"
LOG_FILE = ROOT / "overlay.log"
LOCK_FILE = ROOT / "overlay.lock"
DATA_VERSION_FILE = ROOT / "data_version.txt"


def resource_path(relative):
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent
    return Path(base) / relative


def ensure_dirs():
    ROOT.mkdir(parents=True, exist_ok=True)
