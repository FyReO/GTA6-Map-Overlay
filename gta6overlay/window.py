from pathlib import Path

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

from . import config as C
from . import paths
from .icon import render_icon
from .input import HOTKEYS, hotkey_label
from .version import __version__
from .widgets import (Card, ComboRow, GroupSection, SliderRow, ToggleRow, QSS, muted, separator)

STATES = {
    "ok": ("Tracking", "#3ddc97"),
    "search": ("Searching for map", "#f2b544"),
    "nosignal": ("No video signal", "#ff6b6b"),
    "loading": ("Loading", "#8b93a3"),
    "setup": ("Setup needed", "#8b93a3"),
}
BUTTON_CHOICES = [("Left click", "left"), ("Right click", "right"), ("Middle click", "middle")]
PAGE_SETUP, PAGE_LOADING, PAGE_MAIN = 0, 1, 2


def open_url(url):
    QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


def open_path(path):
    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))


def button(text, name=None, slot=None):
    b = QtWidgets.QPushButton(text)
    b.setCursor(QtCore.Qt.PointingHandCursor)
    if name:
        b.setObjectName(name)
    if slot:
        b.clicked.connect(slot)
    return b


def scrolling(widget):
    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    area.viewport().setAutoFillBackground(False)
    widget.setAutoFillBackground(False)
    area.setWidget(widget)
    return area


def column(spacing=10, margins=(0, 10, 6, 10)):
    host = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(host)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return host, lay


class MainWindow(QtWidgets.QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.cfg = ctl.cfg
        self.engine = None
        self.sections = []
        self._banner_action = None
        self._page_state = "loading"
        self.setObjectName("root")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setWindowTitle(C.APP_NAME)
        self.setStyleSheet(QSS)
        self.resize(440, 720)
        self.setMinimumSize(390, 540)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)
        root.addLayout(self._build_header())
        root.addWidget(self._build_banner())
        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self._build_setup_page())
        self.stack.addWidget(self._build_loading_page())
        self.tabbar = QtWidgets.QTabBar()
        self.tabbar.setExpanding(True)
        self.tabbar.setDrawBase(False)
        self.pages = QtWidgets.QStackedWidget()
        self.overlay_tab = QtWidgets.QWidget()
        QtWidgets.QVBoxLayout(self.overlay_tab).setContentsMargins(0, 0, 0, 0)
        for title, page in (("Overlay", self.overlay_tab), ("Settings", self._build_settings_tab()),
                            ("Support", self._build_support_tab())):
            self.tabbar.addTab(title)
            self.pages.addWidget(page)
        self.tabbar.currentChanged.connect(self.pages.setCurrentIndex)
        main = QtWidgets.QWidget()
        main_lay = QtWidgets.QVBoxLayout(main)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(self.tabbar)
        main_lay.addWidget(self.pages, 1)
        self.stack.addWidget(main)
        root.addWidget(self.stack, 1)
        footer = muted(f"{hotkey_label(HOTKEYS[0][0])} shows or hides this window", wrap=False)
        footer.setAlignment(QtCore.Qt.AlignCenter)
        root.addWidget(footer)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)
        self.show_loading("Starting")

    def closeEvent(self, event):
        self.ctl.window_closing(event)

    def _build_header(self):
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        logo = QtWidgets.QLabel()
        logo.setPixmap(QtGui.QPixmap.fromImage(render_icon(64)).scaled(
            30, 30, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(0)
        title = QtWidgets.QLabel(C.APP_NAME)
        title.setObjectName("title")
        col.addWidget(title)
        col.addWidget(muted(f"Version {__version__}", wrap=False))
        self.pill = QtWidgets.QLabel()
        self.pill.setAlignment(QtCore.Qt.AlignCenter)
        self._pill_state = None
        row.addWidget(logo)
        row.addLayout(col, 1)
        row.addWidget(self.pill)
        return row

    def _build_banner(self):
        self.banner = QtWidgets.QFrame()
        self.banner.setObjectName("banner")
        self.banner.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        lay = QtWidgets.QHBoxLayout(self.banner)
        lay.setContentsMargins(12, 8, 8, 8)
        self.banner_label = QtWidgets.QLabel()
        self.banner_label.setWordWrap(True)
        self.banner_bar = QtWidgets.QProgressBar()
        self.banner_bar.setFixedWidth(90)
        self.banner_btn = button("Update", "primary", self._banner_clicked)
        lay.addWidget(self.banner_label, 1)
        lay.addWidget(self.banner_bar)
        lay.addWidget(self.banner_btn)
        self.banner.hide()
        return self.banner

    def _build_setup_page(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(20, 30, 20, 30)
        lay.setSpacing(12)
        lay.addStretch(1)
        art = QtWidgets.QLabel()
        art.setPixmap(QtGui.QPixmap.fromImage(render_icon(160)).scaled(
            80, 80, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        art.setAlignment(QtCore.Qt.AlignCenter)
        self.setup_title = QtWidgets.QLabel("Download the map data")
        self.setup_title.setObjectName("title")
        self.setup_title.setAlignment(QtCore.Qt.AlignCenter)
        self.setup_text = muted("The overlay needs its reference maps, locations and screenshots. "
                                "This is a one-time download; later updates are applied automatically.")
        self.setup_text.setAlignment(QtCore.Qt.AlignCenter)
        self.setup_bar = QtWidgets.QProgressBar()
        self.setup_bar.hide()
        self.setup_error = QtWidgets.QLabel()
        self.setup_error.setWordWrap(True)
        self.setup_error.setAlignment(QtCore.Qt.AlignCenter)
        self.setup_error.setStyleSheet("color: #ff8b8b;")
        self.setup_error.hide()
        self.setup_btn = button("Download", "primary", self.ctl.download_data)
        self.setup_btn.setMinimumHeight(34)
        log_btn = button("Open log file", None, lambda: open_path(paths.LOG_FILE))
        for w in (art, self.setup_title, self.setup_text, self.setup_bar, self.setup_error,
                  self.setup_btn, log_btn):
            lay.addWidget(w)
        lay.addStretch(2)
        return page

    def _build_loading_page(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.addStretch(1)
        self.loading_label = QtWidgets.QLabel("Loading map data")
        self.loading_label.setAlignment(QtCore.Qt.AlignCenter)
        self.loading_label.setObjectName("h2")
        bar = QtWidgets.QProgressBar()
        bar.setRange(0, 0)
        bar.setFixedWidth(220)
        lay.addWidget(self.loading_label)
        lay.addWidget(bar, 0, QtCore.Qt.AlignHCenter)
        lay.addStretch(1)
        return page

    def show_setup(self, text=None):
        self._page_state = "setup"
        if text:
            self.setup_text.setText(text)
        self.setup_bar.hide()
        self.setup_btn.setEnabled(True)
        self.setup_btn.setText("Download")
        self.stack.setCurrentIndex(PAGE_SETUP)

    def set_setup_progress(self, fraction, text):
        self.setup_error.hide()
        self.setup_bar.show()
        self.setup_bar.setRange(0, 1000)
        self.setup_bar.setValue(int(fraction * 1000))
        self.setup_btn.setEnabled(False)
        self.setup_btn.setText(text)

    def show_setup_error(self, message):
        self._page_state = "setup"
        self.setup_bar.hide()
        self.setup_error.setText(message)
        self.setup_error.show()
        self.setup_btn.setEnabled(True)
        self.setup_btn.setText("Try again")
        self.stack.setCurrentIndex(PAGE_SETUP)

    def show_loading(self, text):
        self._page_state = "loading"
        self.loading_label.setText(text)
        self.stack.setCurrentIndex(PAGE_LOADING)

    def show_banner(self, text, action_text=None, action=None):
        self.banner_label.setText(text)
        self.banner_bar.hide()
        self._banner_action = action
        self.banner_btn.setVisible(action_text is not None)
        self.banner_btn.setEnabled(True)
        if action_text:
            self.banner_btn.setText(action_text)
        self.banner.show()

    def set_banner_progress(self, text, fraction=None):
        self.banner_label.setText(text)
        self.banner_btn.hide()
        self.banner_bar.show()
        if fraction is None:
            self.banner_bar.setRange(0, 0)
        else:
            self.banner_bar.setRange(0, 1000)
            self.banner_bar.setValue(int(fraction * 1000))
        self.banner.show()

    def hide_banner(self):
        self.banner.hide()

    def _banner_clicked(self):
        if self._banner_action:
            self._banner_action()

    def attach_engine(self, engine):
        self.engine = engine
        if self.cfg.collapsed is None:
            self.cfg.collapsed = list(engine.catalog.groups)
        self._build_overlay_tab()
        self.stack.setCurrentIndex(PAGE_MAIN)
        self._page_state = "ready"
        self.refresh()

    def _build_overlay_tab(self):
        eng, cfg = self.engine, self.cfg
        lay = self.overlay_tab.layout()
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.sections = []
        host, col = column(spacing=8, margins=(0, 10, 0, 0))
        lay.addWidget(host)

        summary = Card()
        top = QtWidgets.QHBoxLayout()
        self.found_label = QtWidgets.QLabel("0")
        self.found_label.setObjectName("big")
        self.found_pct = muted("", wrap=False)
        top.addWidget(self.found_label)
        top.addStretch(1)
        top.addWidget(self.found_pct, 0, QtCore.Qt.AlignBottom)
        summary.add_layout(top)
        self.found_bar = QtWidgets.QProgressBar()
        self.found_bar.setRange(0, max(1, len(eng.store.ids)))
        summary.add(self.found_bar)
        col.addWidget(summary)

        toggles = Card()
        self.t_overlay = ToggleRow("Show overlay", "Hides every marker while off", cfg.overlay_visible)
        self.t_overlay.clicked.connect(lambda on: self._set("overlay_visible", on))
        self.t_found = ToggleRow("Show collected", "Collected markers stay on the map, greyed out", cfg.show_found)
        self.t_found.clicked.connect(lambda on: self._set("show_found", on))
        self.t_click = ToggleRow("Clickable markers", "", cfg.click_enabled)
        self.t_click.clicked.connect(lambda on: self._set("click_enabled", on))
        toggles.add(self.t_overlay)
        toggles.add(separator())
        toggles.add(self.t_found)
        toggles.add(separator())
        toggles.add(self.t_click)
        col.addWidget(toggles)
        self._update_click_hint()

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(button("Show all", None, lambda: self._all(True)))
        row.addWidget(button("Hide all", None, lambda: self._all(False)))
        row.addStretch(1)
        col.addLayout(row)

        host2, col2 = column(spacing=8)
        for g in eng.catalog.groups:
            ids = [i for i, gg in enumerate(eng.catalog.set_group) if gg == g]
            sec = GroupSection(eng, g, ids, cfg.collapsed, self.ctl.settings_changed, self._pick_color)
            self.sections.append(sec)
            col2.addWidget(sec)
        col2.addStretch(1)
        col.addWidget(scrolling(host2), 1)

    def _set(self, name, value):
        setattr(self.cfg, name, value)
        self.ctl.settings_changed()

    def _all(self, on):
        eng = self.engine
        eng.set_many_enabled(range(len(eng.catalog.set_names)), on)
        self.ctl.settings_changed()
        self.refresh()

    def _pick_color(self, i):
        eng = self.engine
        c = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(eng.set_colors[i]), self, f"Colour for {eng.catalog.set_names[i]}")
        if c.isValid():
            eng.set_color(i, c.name())
            for sec in self.sections:
                if i in sec.dots:
                    sec.restyle(i)
            self.ctl.settings_changed()

    def _update_click_hint(self):
        cfg = self.cfg
        if hasattr(self, "t_click"):
            self.t_click.set_subtitle(
                f"{cfg.info_button.capitalize()}-click shows info, {cfg.mark_button}-click marks found")

    def _build_settings_tab(self):
        cfg = self.cfg
        host, col = column()

        capture = Card("Video source")
        self.scan_btn = button("Scan", None, self.ctl.scan_cameras)
        self.camera_row = ComboRow("Video device", [(f"Device {cfg.camera}", cfg.camera)], self.scan_btn,
                                   "Choose the device that shows your game: a capture card (like an Elgato) or a "
                                   "virtual camera. The overlay reads the picture from it, not from your screen.")
        self.camera_row.set_current(cfg.camera)
        self.camera_row.picked.connect(self._pick_camera)
        self.camera_note = muted("")
        self.camera_note.setStyleSheet("color: #ff8b8b;")
        self.camera_note.hide()
        self.monitor_row = ComboRow("Monitor", self._monitor_items(),
                                    hint="The screen where the overlay is drawn.")
        self.monitor_row.set_current(cfg.monitor)
        self.monitor_row.picked.connect(self._pick_monitor)
        capture.add(self.camera_row)
        capture.add(self.camera_note)
        capture.add(separator())
        capture.add(self.monitor_row)
        col.addWidget(capture)

        markers = Card("Markers")
        size = SliderRow("Marker size", 5, 16, cfg.marker_size, "{} px")
        size.changed.connect(lambda v: self._set("marker_size", v))
        opacity = SliderRow("Marker opacity", 30, 100, cfg.marker_opacity, "{}%")
        opacity.changed.connect(lambda v: self._set("marker_opacity", v))
        self.radius_toggle = ToggleRow("Only show near screen centre",
                                       "Hide markers far from the middle of the screen", cfg.radius_enabled)
        self.radius_slider = SliderRow("Display radius", 10, 100, cfg.radius, "{}%")
        self.radius_slider.setEnabled(cfg.radius_enabled)
        self.radius_toggle.clicked.connect(self._radius_toggled)
        self.radius_slider.changed.connect(lambda v: self._set("radius", v))
        status = ToggleRow("Show status text", "Debug line in the corner of the overlay", cfg.show_status)
        status.clicked.connect(lambda on: self._set("show_status", on))
        for w in (size, opacity, separator(), self.radius_toggle, self.radius_slider, separator(), status):
            markers.add(w)
        col.addWidget(markers)

        controls = Card("Mouse controls")
        self.info_row = ComboRow("Open info popup", BUTTON_CHOICES, hint="Click anywhere to close a popup.")
        self.info_row.set_current(cfg.info_button)
        self.mark_row = ComboRow("Mark as found", BUTTON_CHOICES)
        self.mark_row.set_current(cfg.mark_button)
        self.info_row.picked.connect(lambda v: self._pick_button("info_button", "mark_button", v))
        self.mark_row.picked.connect(lambda v: self._pick_button("mark_button", "info_button", v))
        controls.add(self.info_row)
        controls.add(self.mark_row)
        col.addWidget(controls)

        tracking = Card("Tracking")
        smooth = SliderRow("Smoothing", 0, 100, cfg.smoothing, "{}%",
                           "Higher glides markers more gently; lower snaps to the map faster.")
        smooth.changed.connect(lambda v: self._set("smoothing", v))
        sens = SliderRow("Sensitivity", 0, 100, cfg.sensitivity, "{}%",
                         "Raise it if the map is not found; lower it if markers jump around.")
        sens.changed.connect(lambda v: self._set("sensitivity", v))
        tracking.add(smooth)
        tracking.add(sens)
        col.addWidget(tracking)

        data = Card("Progress and files")
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(6)
        grid.addWidget(button("Export progress", None, self._export), 0, 0)
        grid.addWidget(button("Import progress", None, self._import), 0, 1)
        grid.addWidget(button("Open data folder", None, lambda: open_path(paths.ROOT)), 1, 0)
        grid.addWidget(button("Open log file", None, lambda: open_path(paths.LOG_FILE)), 1, 1)
        grid.addWidget(button("Reset all progress", "danger", self._reset), 2, 0, 1, 2)
        data.add_layout(grid)
        col.addWidget(data)

        keys = Card("Hotkeys", "These work even while the game has focus.")
        for spec, _, text in HOTKEYS:
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(text))
            row.addStretch(1)
            row.addWidget(muted(hotkey_label(spec), wrap=False))
            keys.add_layout(row)
        col.addWidget(keys)
        col.addStretch(1)
        return scrolling(host)

    def _monitor_items(self):
        items = []
        primary = QtWidgets.QApplication.primaryScreen()
        for i, screen in enumerate(QtWidgets.QApplication.screens()):
            g = screen.geometry()
            tag = "  (primary)" if screen is primary else ""
            items.append((f"Monitor {i + 1}  -  {g.width()}x{g.height()}{tag}", i))
        return items

    def _pick_camera(self, index):
        self.camera_note.hide()
        if not self.ctl.set_camera(index):
            self.camera_note.setText(f"Could not open device {index}. Make sure it is connected and not in use by another program.")
            self.camera_note.show()
            self.camera_row.set_current(self.cfg.camera)

    def set_cameras(self, cameras):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan")
        items = [(label, index) for index, label in cameras]
        if not items:
            self.camera_note.setText("No video devices found. Connect your capture card (or start a virtual camera) and scan again.")
            self.camera_note.show()
            return
        self.camera_note.hide()
        self.camera_row.set_items(items, self.cfg.camera)

    def set_scanning(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Scanning")

    def _pick_monitor(self, index):
        self.cfg.monitor = index
        self.ctl.apply_monitor()
        self.ctl.settings_changed()

    def _radius_toggled(self, on):
        self.radius_slider.setEnabled(on)
        self._set("radius_enabled", on)

    def _pick_button(self, mine, other, value):
        cfg = self.cfg
        if getattr(cfg, other) == value:
            setattr(cfg, other, getattr(cfg, mine))
        setattr(cfg, mine, value)
        self.info_row.set_current(cfg.info_button)
        self.mark_row.set_current(cfg.mark_button)
        self._update_click_hint()
        self.ctl.settings_changed()

    def _export(self):
        if self.engine is None:
            return
        name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export progress", str(Path.home() / "gta6-overlay-progress.json"), "JSON (*.json)")
        if name:
            try:
                self.engine.store.export_to(Path(name))
            except OSError as exc:
                QtWidgets.QMessageBox.warning(self, C.APP_NAME, f"Could not save the file:\n{exc}")

    def _import(self):
        if self.engine is None:
            return
        name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import progress", str(Path.home()), "JSON (*.json)")
        if not name:
            return
        try:
            added = self.engine.store.import_from(Path(name))
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, C.APP_NAME, f"Could not read that file:\n{exc}")
            return
        QtWidgets.QMessageBox.information(self, C.APP_NAME, f"Imported {added} new collected item(s).")

    def _reset(self):
        if self.engine is None:
            return
        answer = QtWidgets.QMessageBox.question(
            self, C.APP_NAME, "Clear every collected item? This cannot be undone.\n"
                              "Tip: use Export progress first to keep a backup.")
        if answer == QtWidgets.QMessageBox.Yes:
            self.engine.store.reset()

    def _build_support_tab(self):
        host, col = column()

        hero = Card("Made by FyReO")
        hero.add(muted("Free to use and updated regularly. If it saved you time, subscribing or "
                       "chipping in helps keep the updates coming."))
        hero.add(button("Watch on YouTube", "youtube", lambda: open_url(C.YOUTUBE_URL)))
        if C.DONATE_URL:
            hero.add(button("Donate", "donate", lambda: open_url(C.DONATE_URL)))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        repo = f"https://github.com/{C.GITHUB_REPO}"
        row.addWidget(button("GitHub", None, lambda: open_url(repo)))
        row.addWidget(button("Report a problem", None, lambda: open_url(repo + "/issues")))
        hero.add_layout(row)
        col.addWidget(hero)

        about = Card("About and updates")
        self.version_label = QtWidgets.QLabel()
        about.add(self.version_label)
        self.update_status = muted("")
        about.add(self.update_status)
        self.check_btn = button("Check for updates", None, self.ctl.check_updates)
        about.add(self.check_btn)
        auto = ToggleRow("Update automatically", "Install new versions and map data when the app starts",
                         self.cfg.auto_update)
        auto.clicked.connect(lambda on: self._set("auto_update", on))
        about.add(separator())
        about.add(auto)
        col.addWidget(about)

        guide = Card("Quick start")
        for line in ("1.  Your game's picture must reach this PC through a video device, such as a capture "
                     "card (Elgato and similar) or the OBS Virtual Camera.",
                     "2.  Open the in-game map and keep it on screen.",
                     "3.  Under Settings > Video source, pick that device (press Scan to refresh the list).",
                     "4.  When the map is found, the status at the top turns green and says Tracking.",
                     "5.  Left-click a marker for info, right-click to mark it found. You can change these buttons "
                     "in Settings."):
            guide.add(muted(line))
        col.addWidget(guide)
        col.addStretch(1)
        self.set_data_version(0)
        return scrolling(host)

    def set_data_version(self, version):
        data = f"map data v{version}" if version else "map data not installed"
        self.version_label.setText(f"Version {__version__}   |   {data}")

    def set_update_status(self, text, busy=False):
        self.update_status.setText(text)
        self.check_btn.setEnabled(not busy)

    def _set_pill(self, state):
        if state == self._pill_state:
            return
        self._pill_state = state
        text, color = STATES[state]
        self.pill.setText("  " + text + "  ")
        self.pill.setStyleSheet(
            f"background: rgba(255,255,255,0.05); color: {color}; border: 1px solid {color};"
            f" border-radius: 11px; padding: 3px 8px; font-weight: 600;")

    def refresh(self):
        eng = self.engine
        if eng is None:
            self._set_pill("setup" if self._page_state == "setup" else "loading")
            return
        self._set_pill({"locked": "ok", "searching": "search", "no_signal": "nosignal"}[eng.state])
        cat, cfg = eng.catalog, self.cfg
        n = len(cat.set_names)
        got = np.bincount(cat.set_idx[eng.store.mask], minlength=n)
        total = len(eng.store.ids)
        found = eng.store.count()
        self.found_label.setText(f"{found} / {total}")
        self.found_pct.setText(f"{100 * found / max(1, total):.0f}% collected")
        self.found_bar.setValue(found)
        for sec in self.sections:
            sec.refresh(got)
        self.t_overlay.set_checked(cfg.overlay_visible)
        self.t_found.set_checked(cfg.show_found)
        self.t_click.set_checked(cfg.click_enabled)
