import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

from . import config as C
from .popup import PopupRenderer


def nearest_item(px, idx, x, y, radius):
    if px is None or len(px) == 0:
        return None
    d = np.hypot(px[:, 0] - x, px[:, 1] - y)
    j = int(np.argmin(d))
    return int(idx[j]) if d[j] <= radius else None


class Overlay(QtWidgets.QWidget):
    def __init__(self, engine, cfg, media_dir, hooks, ignore=()):
        super().__init__()
        self.engine = engine
        self.cfg = cfg
        self.ignore = list(ignore)
        self.renderer = PopupRenderer(media_dir)
        self.px = None
        self.idx = None
        self.found = None
        self.popup = None
        self._colors = {}
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
                            | QtCore.Qt.Tool | QtCore.Qt.WindowTransparentForInput)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.place_on_monitor(cfg.monitor)
        self.show()
        hooks.click.connect(self.on_click)
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(6)

    def place_on_monitor(self, index):
        screens = QtWidgets.QApplication.screens()
        self.setGeometry(screens[min(index, len(screens) - 1)].geometry())

    def on_click(self, button):
        cfg = self.cfg
        if not cfg.click_enabled or not cfg.overlay_visible:
            return
        cursor = QtGui.QCursor.pos()
        if any(w.isVisible() and w.frameGeometry().contains(cursor) for w in self.ignore):
            return
        pos = self.mapFromGlobal(cursor)
        if button == cfg.info_button:
            if self.popup is not None:
                self.popup = None
                return
            self.popup = nearest_item(self.px, self.idx, pos.x(), pos.y(), C.HIT_RADIUS)
        elif button == cfg.mark_button:
            i = nearest_item(self.px, self.idx, pos.x(), pos.y(), C.HIT_RADIUS)
            if i is not None:
                self.engine.store.toggle(i)
                if self.popup == i:
                    self.popup = None

    def tick(self):
        res = self.engine.tick() if self.cfg.overlay_visible else None
        if res is None:
            self.px = self.idx = self.found = None
        else:
            pts, self.idx, self.found = res
            self.px = pts * [self.width(), self.height()]
        if self.popup is not None and self.idx is not None and self.popup not in self.idx:
            self.popup = None
        self.update()

    def _color(self, hex_):
        key = (hex_, self.cfg.marker_opacity)
        c = self._colors.get(key)
        if c is None:
            c = QtGui.QColor(hex_)
            c.setAlpha(int(255 * self.cfg.marker_opacity / 100))
            self._colors[key] = c
        return c

    def _marker(self, p, shape, x, y):
        r = self.cfg.marker_size
        pts = C.SHAPE_POINTS.get(shape)
        if pts is None:
            p.drawEllipse(QtCore.QPointF(x, y), r, r)
        else:
            p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x + ux * r, y + uy * r) for ux, uy in pts]))

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        engine, cat = self.engine, self.engine.catalog
        if self.px is not None:
            sidx = cat.set_idx[self.idx]
            gidx = cat.set_gidx[sidx]
            grey = QtGui.QColor(150, 150, 150, int(130 * self.cfg.marker_opacity / 92))
            for (x, y), found, ci, si, gi in zip(self.px, self.found, self.idx, sidx, gidx):
                if found:
                    p.setBrush(grey)
                    pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 100), 1)
                else:
                    p.setBrush(self._color(engine.set_colors[si]))
                    pen = QtGui.QPen(QtCore.Qt.black, 2)
                if ci == self.popup:
                    pen = QtGui.QPen(QtCore.Qt.white, 3)
                p.setPen(pen)
                self._marker(p, cat.group_shapes[gi], x, y)
        if self.cfg.show_status:
            p.setPen(QtGui.QColor(255, 255, 255))
            p.drawText(12, 20, f"found {engine.store.count()}/{len(engine.store.ids)}   "
                               f"slow: {engine.status}   fast: {engine.fast_ms:.0f} ms")
        if self.popup is not None and self.px is not None:
            j = np.flatnonzero(self.idx == self.popup)
            if len(j):
                item = cat.items[self.popup]
                self.renderer.paint(
                    p, item, cat.info.get(str(item.get("id")), {}), bool(engine.store.mask[self.popup]),
                    self.cfg.mark_button, self.px[j[0]], self.cfg.marker_size, (self.width(), self.height()))
