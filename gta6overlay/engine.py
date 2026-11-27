import sys
import threading
import time

import cv2
import numpy as np

from . import config as C
from .catalog import default_color
from .tracking import FastLayer, Tracker, visible_mask


def _backend():
    return cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY


def open_capture(index):
    cap = cv2.VideoCapture(index, _backend())
    if not cap.isOpened():
        cap.release()
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def scan_cameras(skip=None, limit=6):
    found = []
    for index in range(limit):
        if index == skip:
            found.append((index, f"Camera {index} (in use)"))
            continue
        cap = open_capture(index)
        if cap is None:
            continue
        ok, frame = cap.read()
        cap.release()
        label = f"Camera {index}"
        if ok and frame is not None:
            label += f" ({frame.shape[1]}x{frame.shape[0]})"
        found.append((index, label))
    return found


class Engine:
    def __init__(self, cfg, catalog, levels, store):
        self.cfg = cfg
        self.catalog = catalog
        self.store = store
        self.tracker = Tracker(cfg, levels)
        self.fast = FastLayer()
        self.set_on = np.array([bool(cfg.enabled.get(n, True)) for n in catalog.set_names])
        self.set_colors = [cfg.colors.get(n, default_color(i)) for i, n in enumerate(catalog.set_names)]
        self.latest = None
        self.latest_id = 0
        self.done_id = 0
        self.last_frame_time = 0.0
        self.lock = threading.Lock()
        self._cap_lock = threading.Lock()
        self._cap = None
        self._stop = threading.Event()
        self.job = None
        self.result = None
        self.job_ev = threading.Event()
        self.fast_ms = 0.0
        self.status = "starting"
        self.size = None
        self.locked = False
        self.camera_error = None
        self.open_camera(cfg.camera)
        threading.Thread(target=self._capture, daemon=True).start()
        threading.Thread(target=self._worker, daemon=True).start()

    @property
    def state(self):
        if time.time() - self.last_frame_time > C.NO_SIGNAL_SECONDS:
            return "no_signal"
        return "locked" if self.locked else "searching"

    def open_camera(self, index):
        cap = open_capture(index)
        if cap is None:
            self.camera_error = f"Could not open camera {index}"
            return False
        with self._cap_lock:
            old, self._cap = self._cap, cap
            if old is not None:
                old.release()
        self.camera_error = None
        self.last_frame_time = 0.0
        return True

    def stop(self):
        self._stop.set()
        self.job_ev.set()
        with self._cap_lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None

    def set_enabled(self, i, on):
        self.set_on[i] = on
        self.cfg.enabled[self.catalog.set_names[i]] = bool(on)

    def set_many_enabled(self, ids, on):
        for i in ids:
            self.set_enabled(i, on)

    def set_color(self, i, color):
        self.set_colors[i] = color
        self.cfg.colors[self.catalog.set_names[i]] = color

    def _capture(self):
        while not self._stop.is_set():
            with self._cap_lock:
                cap = self._cap
                ok, frame = cap.read() if cap is not None else (False, None)
            if ok and frame is not None:
                with self.lock:
                    self.latest = frame
                    self.latest_id += 1
                    self.last_frame_time = time.time()
            else:
                time.sleep(0.03)

    def _worker(self):
        while not self._stop.is_set():
            self.job_ev.wait()
            self.job_ev.clear()
            if self._stop.is_set() or self.job is None:
                continue
            fid, frame = self.job
            try:
                self.tracker.process(frame)
                self.result = (fid, self.tracker.last, self.tracker.mode, self.tracker.inliers)
            finally:
                self.job = None

    def tick(self):
        with self.lock:
            frame, fid = self.latest, self.latest_id
        if frame is None or fid == self.done_id:
            return self._points()
        self.done_id = fid
        t0 = time.time()
        h, w = frame.shape[:2]
        fh = int(h * C.FAST_WIDTH / w)
        gray = cv2.cvtColor(cv2.resize(frame, (C.FAST_WIDTH, fh), interpolation=cv2.INTER_AREA),
                            cv2.COLOR_BGR2GRAY)
        self.size = (C.FAST_WIDTH, fh)
        self.fast.step(fid, gray)
        if self.job is None:
            self.job = (fid, frame.copy())
            self.job_ev.set()
        res, self.result = self.result, None
        if res is not None:
            rfid, last, mode, n = res
            self.status = f"{mode} {n}"
            if last is not None:
                H, lv, _, sz = last
                D = np.diag([C.FAST_WIDTH / sz[0], C.FAST_WIDTH / sz[0], 1.0])
                self.fast.apply_fix(rfid, D @ H, lv, time.time(), self.size, self.cfg.fix_blend)
        self.fast_ms = (time.time() - t0) * 1000
        return self._points()

    def _points(self):
        self.locked = False
        if self.size is None:
            return None
        H, lv = self.fast.current(time.time())
        if H is None:
            return None
        self.locked = True
        p = cv2.perspectiveTransform(lv.cards, H).reshape(-1, 2)
        p[:, 0] /= self.size[0]
        p[:, 1] /= self.size[1]
        keep = visible_mask(p, self.cfg.radius_fraction)
        keep &= self.set_on[self.catalog.set_idx]
        if not self.cfg.show_found:
            keep &= ~self.store.mask
        idx = np.flatnonzero(keep)
        return p[idx], idx, self.store.mask[idx]
