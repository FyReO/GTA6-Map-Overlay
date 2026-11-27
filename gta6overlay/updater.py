import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from . import config as C
from . import paths
from .errors import UpdateError
from .version import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"{C.APP_DIR_NAME}/{__version__}"
APP_TAG = re.compile(r"^v(\d+(?:\.\d+)*)$")
DATA_TAG = re.compile(r"^data-(\d+)$")
SHA256 = re.compile(r"\b[0-9a-fA-F]{64}\b")
REQUIRED_DATA_FILES = ("ref_meta.json", "cards_latlng.json")
MAX_UNPACKED_BYTES = 4 * 1024 ** 3
TIMEOUT = 25


@dataclass
class Asset:
    name: str
    url: str
    size: int
    sha256: str


@dataclass
class UpdateInfo:
    app: Asset = None
    app_version: str = None
    data: Asset = None
    data_version: int = None
    release_url: str = ""

    @property
    def available(self):
        return self.app is not None or self.data is not None


def parse_version(text):
    m = APP_TAG.match(text or "") or re.match(r"^(\d+(?:\.\d+)*)$", text or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def _allowed(url):
    parts = urlparse(url)
    host = parts.hostname or ""
    return parts.scheme == "https" and any(host == h or host.endswith("." + h) for h in C.ALLOWED_HOSTS)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed(newurl):
            raise UpdateError(f"refusing redirect to {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url, accept=None):
    if not _allowed(url):
        raise UpdateError(f"refusing to contact {url}")
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    opener = urllib.request.build_opener(_SafeRedirect)
    try:
        return opener.open(urllib.request.Request(url, headers=headers), timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError(f"nothing was found at {C.GITHUB_REPO} (is the repository public and released?)") from exc
        if exc.code in (403, 429):
            raise UpdateError("GitHub refused the request (rate limit?). Try again in a while.") from exc
        raise UpdateError(f"GitHub answered {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateError(f"could not reach GitHub ({getattr(exc, 'reason', exc)})") from exc


def _fetch_json(url):
    with _open(url, "application/vnd.github+json") as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_text(url, limit=4096):
    with _open(url) as resp:
        return resp.read(limit).decode("utf-8", "replace")


def _make_asset(raw, by_name):
    digest = raw.get("digest") or ""
    sha = digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
    if not sha:
        side = by_name.get(raw["name"] + ".sha256")
        if side:
            m = SHA256.search(_fetch_text(side["browser_download_url"]))
            sha = m.group(0) if m else ""
    if not SHA256.fullmatch(sha or ""):
        raise UpdateError(f"{raw['name']} has no checksum in its release")
    return Asset(raw["name"], raw["browser_download_url"], int(raw.get("size") or 0), sha.lower())


def installed_data_version(data_dir=None, version_file=None):
    data_dir = data_dir or paths.DATA_DIR
    version_file = version_file or paths.DATA_VERSION_FILE
    if not (data_dir / "ref_meta.json").is_file():
        return 0
    try:
        return int(version_file.read_text().strip())
    except (OSError, ValueError):
        return 0


def check(current_version=__version__, installed_data=None):
    if installed_data is None:
        installed_data = installed_data_version()
    url = f"{C.API_BASE}/repos/{C.GITHUB_REPO}/releases?per_page=30"
    releases = _fetch_json(url)
    if not isinstance(releases, list):
        raise UpdateError("unexpected answer from GitHub")

    best_app, best_data = None, None
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        tag = rel.get("tag_name", "")
        m = APP_TAG.match(tag)
        if m:
            ver = parse_version(tag)
            if best_app is None or ver > best_app[0]:
                best_app = (ver, rel)
            continue
        m = DATA_TAG.match(tag)
        if m and (best_data is None or int(m.group(1)) > best_data[0]):
            best_data = (int(m.group(1)), rel)

    info = UpdateInfo()
    current = parse_version(current_version) or (0,)
    if best_app:
        info.app_version = ".".join(map(str, best_app[0]))
        info.release_url = best_app[1].get("html_url", "")
        if best_app[0] > current:
            by_name = {a["name"]: a for a in best_app[1].get("assets", [])}
            raw = by_name.get(C.EXE_NAME)
            if raw:
                info.app = _make_asset(raw, by_name)
    if best_data:
        info.data_version = best_data[0]
        if best_data[0] > installed_data:
            by_name = {a["name"]: a for a in best_data[1].get("assets", [])}
            raw = by_name.get(C.DATA_ASSET)
            if raw:
                info.data = _make_asset(raw, by_name)
    return info


def download(asset, dest, progress=None, cancelled=None):
    if not _allowed(asset.url):
        raise UpdateError(f"refusing to download from {asset.url}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    sha = hashlib.sha256()
    done = 0
    try:
        with _open(asset.url) as resp, open(part, "wb") as out:
            total = int(resp.headers.get("Content-Length") or asset.size or 0)
            while True:
                if cancelled and cancelled():
                    raise UpdateError("download cancelled")
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if sha.hexdigest() != asset.sha256:
            raise UpdateError(f"{asset.name} failed its integrity check")
        os.replace(part, dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return dest


def _safe_extract(zf, target):
    root = target.resolve()
    if sum(i.file_size for i in zf.infolist()) > MAX_UNPACKED_BYTES:
        raise UpdateError("data pack is unreasonably large")
    for info in zf.infolist():
        out = (target / info.filename).resolve()
        if root != out and root not in out.parents:
            raise UpdateError("data pack contains an unsafe path")
        if info.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)


def install_data(zip_path, version, data_dir=None, version_file=None):
    data_dir = Path(data_dir or paths.DATA_DIR)
    version_file = Path(version_file or paths.DATA_VERSION_FILE)
    staging = data_dir.with_name(data_dir.name + ".new")
    backup = data_dir.with_name(data_dir.name + ".old")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            _safe_extract(zf, staging)
    except zipfile.BadZipFile as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("the data pack is corrupt") from exc
    missing = [n for n in REQUIRED_DATA_FILES if not (staging / n).is_file()]
    if missing:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError(f"data pack is missing {', '.join(missing)}")
    had_old = data_dir.exists()
    try:
        if had_old:
            os.replace(data_dir, backup)
        os.replace(staging, data_dir)
    except OSError as exc:
        if had_old and backup.exists() and not data_dir.exists():
            os.replace(backup, data_dir)
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError(f"could not replace the map data ({exc})") from exc
    shutil.rmtree(backup, ignore_errors=True)
    version_file.write_text(str(int(version)))


def exe_path():
    return Path(sys.executable)


def pending_exe_path():
    exe = exe_path()
    return exe.with_name(exe.name + ".new")


def install_app(new_file, exe=None):
    exe = Path(exe or exe_path())
    new_file = Path(new_file)
    old = exe.with_name(exe.name + ".old")
    old.unlink(missing_ok=True)
    try:
        os.replace(exe, old)
    except OSError as exc:
        raise UpdateError(f"cannot replace {exe.name}; move it out of a protected folder ({exc})") from exc
    try:
        os.replace(new_file, exe)
    except OSError as exc:
        os.replace(old, exe)
        raise UpdateError(f"could not install the new version ({exc})") from exc


def cleanup_leftovers(exe=None):
    exe = Path(exe or exe_path())
    for suffix in (".old", ".new", ".new.part"):
        try:
            exe.with_name(exe.name + suffix).unlink(missing_ok=True)
        except OSError:
            pass


def relaunch_command():
    if is_frozen():
        return [str(exe_path())]
    return [sys.executable, "-m", "gta6overlay"]


def relaunch():
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    subprocess.Popen(relaunch_command(), env=env, close_fds=True, **kwargs)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
