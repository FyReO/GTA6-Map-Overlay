import logging
import logging.handlers
import os
import signal
import sys
import threading
import time
from types import SimpleNamespace

from PyQt5 import QtCore, QtWidgets

from . import config as C
from . import paths, updater
from .catalog import load_catalog
from .engine import Engine, scan_cameras
from .errors import DataError, UpdateError
from .icon import app_icon
from .input import InputHooks
from .overlay import Overlay
from .store import FoundStore, Settings
from .tracking import load_levels
from .version import __version__
from .window import MainWindow, open_url

log = logging.getLogger("gta6overlay")


def setup_logging():
    paths.ensure_dirs()
    handlers = [logging.handlers.RotatingFileHandler(paths.LOG_FILE, maxBytes=512 * 1024, backupCount=1,
                                                      encoding="utf-8")]
    if not updater.is_frozen():
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    def hook(kind, value, tb):
        log.error("unhandled exception", exc_info=(kind, value, tb))

    sys.excepthook = hook
    threading.excepthook = lambda args: hook(args.exc_type, args.exc_value, args.exc_traceback)
    log.info("starting %s %s (frozen=%s)", C.APP_NAME, __version__, updater.is_frozen())


def _throttled(callback, interval=0.1):
    state = {"t": 0.0}

    def wrapper(done, total):
        now = time.monotonic()
        if done >= total or now - state["t"] >= interval:
            state["t"] = now
            callback(done, total)
    return wrapper


class Bridge(QtCore.QObject):
    engine_ready = QtCore.pyqtSignal(object)
    load_failed = QtCore.pyqtSignal(str)
    data_progress = QtCore.pyqtSignal(float, str)
    data_ready = QtCore.pyqtSignal()
    data_failed = QtCore.pyqtSignal(str)
    update_found = QtCore.pyqtSignal(object, bool)
    update_failed = QtCore.pyqtSignal(str, bool)
    apply_progress = QtCore.pyqtSignal(str, float)
    apply_done = QtCore.pyqtSignal(bool)
    cameras = QtCore.pyqtSignal(list)

class Controller(QtCore.QObject):
    def __init__(self, app, cfg, lock):
        super().__init__()
        self.app, self.cfg, self.lock = app, cfg, lock
        self.engine = None
        self.overlay = None
        self.pending = None
        self._tray_notified = False
        self.hooks = InputHooks()
        self.bridge = Bridge()
        self.window = MainWindow(self)
        self.save_timer = QtCore.QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(self.save_now)
        self._connect()
        self._build_tray()

    def _connect(self):
        b = self.bridge
        b.engine_ready.connect(self._on_engine_ready)
        b.load_failed.connect(self._on_load_failed)
        b.data_progress.connect(self.window.set_setup_progress)
        b.data_ready.connect(self.load_engine)
        b.data_failed.connect(self.window.show_setup_error)
        b.update_found.connect(self._on_update_found)
        b.update_failed.connect(self._on_update_failed)
        b.apply_progress.connect(lambda text, f: self.window.set_banner_progress(text, f if f >= 0 else None))
        b.apply_done.connect(self._on_apply_done)
        b.cameras.connect(self.window.set_cameras)
        self.hooks.hotkey.connect(self.on_hotkey)

    def _build_tray(self):
        self.tray = None
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QtWidgets.QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(C.APP_NAME)
        menu = QtWidgets.QMenu()
        menu.addAction("Open settings", self.show_window)
        self.tray_overlay = menu.addAction("Show overlay")
        self.tray_overlay.setCheckable(True)
        self.tray_overlay.triggered.connect(self._tray_overlay)
        menu.addAction("Check for updates", self.check_updates)
        menu.addSeparator()
        menu.addAction("Quit", self.quit)
        menu.aboutToShow.connect(lambda: self.tray_overlay.setChecked(self.cfg.overlay_visible))
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_clicked)
        self._menu = menu
        self.tray.show()

    def _tray_clicked(self, reason):
        if reason in (QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick):
            self.toggle_window()

    def _tray_overlay(self, on):
        self.cfg.overlay_visible = on
        self.settings_changed()

    def start(self):
        self.hooks.start()
        self.window.set_data_version(updater.installed_data_version())
        self.window.show()
        if updater.installed_data_version():
            self.load_engine()
        else:
            self.window.show_setup()
            self.download_data()
        QtCore.QTimer.singleShot(2500, lambda: self.check_updates(startup=True))

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def toggle_window(self):
        if self.window.isVisible():
            self.window.hide()
        else:
            self.show_window()

    def window_closing(self, event):
        if self.tray is not None and self.tray.isVisible():
            event.ignore()
            self.window.hide()
            if not self._tray_notified:
                self._tray_notified = True
                self.tray.showMessage(C.APP_NAME, "Still running in the tray. Right-click the icon to quit.",
                                      QtWidgets.QSystemTrayIcon.Information, 4000)
        else:
            event.accept()
            self.quit()

    def settings_changed(self):
        self.save_timer.start()

    def save_now(self):
        self.cfg.save(paths.SETTINGS_FILE)

    def quit(self):
        self.save_now()
        if self.engine is not None:
            self.engine.stop()
        self.hooks.stop()
        if self.tray is not None:
            self.tray.hide()
        self.lock.unlock()
        self.app.quit()

    def on_hotkey(self, name):
        cfg = self.cfg
        if name == "settings":
            self.toggle_window()
        elif name == "overlay":
            cfg.overlay_visible = not cfg.overlay_visible
        elif name == "click":
            cfg.click_enabled = not cfg.click_enabled
        elif name == "found":
            cfg.show_found = not cfg.show_found
        elif name == "undo" and self.engine is not None:
            self.engine.store.undo_last()
        self.settings_changed()

    def download_data(self):
        self.window.set_setup_progress(0.0, "Checking")
        threading.Thread(target=self._data_job, daemon=True).start()

    def _data_job(self):
        try:
            info = updater.check(installed_data=0)
            if info.data is None:
                raise UpdateError("No map data has been published yet. Please try again later.")
            target = paths.ROOT / "download" / C.DATA_ASSET

            def progress(done, total):
                frac = done / total if total else 0.0
                self.bridge.data_progress.emit(
                    frac, f"Downloading  {updater.human_size(done)} / {updater.human_size(total)}")

            updater.download(info.data, target, _throttled(progress))
            self.bridge.data_progress.emit(1.0, "Installing")
            updater.install_data(target, info.data_version)
            target.unlink(missing_ok=True)
            self.bridge.data_ready.emit()
        except Exception as exc:
            log.exception("data download failed")
            self.bridge.data_failed.emit(str(exc))

    def load_engine(self):
        self.window.set_data_version(updater.installed_data_version())
        self.window.show_loading("Loading map data")
        threading.Thread(target=self._load_job, daemon=True).start()

    def _load_job(self):
        try:
            catalog = load_catalog(paths.DATA_DIR)
            levels = load_levels(paths.DATA_DIR, catalog.items)
            store = FoundStore(paths.FOUND_FILE, catalog.ids)
            self.bridge.engine_ready.emit(Engine(self.cfg, catalog, levels, store))
        except (DataError, OSError, ValueError, KeyError) as exc:
            log.exception("could not load map data")
            self.bridge.load_failed.emit(str(exc))
        except Exception as exc:
            log.exception("unexpected error while loading")
            self.bridge.load_failed.emit(str(exc))

    def _on_engine_ready(self, engine):
        if self.engine is not None:
            self.engine.stop()
        self.engine = engine
        if self.overlay is None:
            self.overlay = Overlay(engine, self.cfg, paths.MEDIA_DIR, self.hooks, ignore=[self.window])
        else:
            self.overlay.engine = engine
        self.window.attach_engine(engine)
        if engine.camera_error:
            self.window.camera_note.setText(engine.camera_error + ". Pick the camera under Settings.")
            self.window.camera_note.show()
        self.settings_changed()

    def _on_load_failed(self, message):
        self.window.show_setup_error(
            f"The map data could not be loaded ({message}). Downloading it again usually fixes this.")

    def set_camera(self, index):
        if self.engine is None:
            self.cfg.camera = index
            return True
        if not self.engine.open_camera(index):
            return False
        self.cfg.camera = index
        self.settings_changed()
        return True

    def scan_cameras(self):
        self.window.set_scanning()
        skip = self.cfg.camera if self.engine is not None and self.engine.state != "no_signal" else None
        threading.Thread(target=lambda: self.bridge.cameras.emit(scan_cameras(skip)), daemon=True).start()

    def apply_monitor(self):
        if self.overlay is not None:
            self.overlay.place_on_monitor(self.cfg.monitor)

    def check_updates(self, startup=False):
        self.window.set_update_status("Checking for updates", busy=True)
        threading.Thread(target=self._check_job, args=(startup,), daemon=True).start()

    def _check_job(self, startup):
        try:
            info = updater.check()
        except Exception as exc:
            if not isinstance(exc, UpdateError):
                log.exception("update check crashed")
            self.bridge.update_failed.emit(str(exc), startup)
            return
        self.bridge.update_found.emit(info, startup)

    def _on_update_failed(self, message, startup):
        log.warning("update check failed: %s", message)
        self.window.set_update_status("Could not check for updates: " + message)

    def _on_update_found(self, info, startup):
        self.pending = info
        installed = updater.installed_data_version()
        if not info.available:
            self.window.set_update_status(
                f"You are up to date. Version {__version__}, map data v{installed}.")
            return
        parts = []
        if info.app:
            parts.append(f"app v{info.app_version}")
        if info.data:
            parts.append(f"map data v{info.data_version}")
        text = "Update available: " + " and ".join(parts)
        self.window.set_update_status(text)
        if self.cfg.auto_update and startup and (info.data or (info.app and updater.is_frozen())):
            self.apply_updates()
            return
        if info.app and not updater.is_frozen() and not info.data:
            self.window.show_banner(text + ". Download it from GitHub.", "Open page",
                                    lambda: open_url(info.release_url))
        else:
            self.window.show_banner(text, "Update now", self.apply_updates)

    def apply_updates(self):
        info = self.pending
        if info is None or not info.available:
            return
        self.window.set_banner_progress("Updating", None)
        threading.Thread(target=self._apply_job, args=(info,), daemon=True).start()

    def _apply_job(self, info):
        try:
            changed = False
            if info.data:
                target = paths.ROOT / "download" / C.DATA_ASSET

                def data_progress(done, total):
                    self.bridge.apply_progress.emit("Downloading map data", done / total if total else -1)

                updater.download(info.data, target, _throttled(data_progress))
                self.bridge.apply_progress.emit("Installing map data", -1)
                updater.install_data(target, info.data_version)
                target.unlink(missing_ok=True)
                changed = True
            if info.app and updater.is_frozen():
                target = updater.pending_exe_path()

                def app_progress(done, total):
                    self.bridge.apply_progress.emit(f"Downloading v{info.app_version}",
                                                    done / total if total else -1)

                updater.download(info.app, target, _throttled(app_progress))
                self.bridge.apply_progress.emit("Installing", -1)
                updater.install_app(target)
                changed = True
            self.bridge.apply_done.emit(changed)
        except Exception as exc:
            log.exception("update failed")
            self.bridge.update_failed.emit(str(exc), False)
            self.bridge.apply_progress.emit("Update failed: " + str(exc), -1)

    def _on_apply_done(self, changed):
        if not changed:
            self.window.hide_banner()
            return
        self.window.set_banner_progress("Restarting", None)
        QtCore.QTimer.singleShot(600, self.restart)

    def restart(self):
        self.save_now()
        self.lock.unlock()
        updater.relaunch()
        if self.engine is not None:
            self.engine.stop()
        self.hooks.stop()
        if self.tray is not None:
            self.tray.hide()
        self.app.quit()

def selftest():
    if sys.platform != "win32":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    import cv2
    import numpy

    for rel in ("assets/icon.png",):
        if not paths.resource_path(rel).is_file():
            print("missing resource:", rel)
            return 1
    cv2.SIFT_create(nfeatures=10)
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    noop = lambda *a, **k: None
    stub = SimpleNamespace(cfg=Settings(), download_data=noop, scan_cameras=noop, check_updates=noop,
                           settings_changed=noop, set_camera=lambda i: True, apply_monitor=noop,
                           window_closing=noop)
    window = MainWindow(stub)
    window.show()
    app.processEvents()
    print(f"selftest ok  v{__version__}  numpy {numpy.__version__}  cv2 {cv2.__version__}")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        return selftest()
    setup_logging()
    if updater.is_frozen():
        updater.cleanup_leftovers()

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(C.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    lock = QtCore.QLockFile(str(paths.LOCK_FILE))
    if not lock.tryLock(300):
        QtWidgets.QMessageBox.information(None, C.APP_NAME, f"{C.APP_NAME} is already running.\n"
                                          "Look for its icon in the system tray.")
        return 0

    cfg = Settings.load(paths.SETTINGS_FILE)
    controller = Controller(app, cfg, lock)
    controller.start()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.exec_()
