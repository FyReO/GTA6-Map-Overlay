import json
import os
from dataclasses import dataclass, field, fields

import numpy as np


def _atomic_write(path, payload, indent=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=indent)
    os.replace(tmp, path)


@dataclass
class Settings:
    camera: int = 0
    monitor: int = 0
    marker_size: int = 9
    marker_opacity: int = 92
    radius_enabled: bool = False
    radius: int = 45
    show_status: bool = False
    info_button: str = "left"
    mark_button: str = "right"
    click_enabled: bool = True
    overlay_visible: bool = True
    show_found: bool = False
    smoothing: int = 55
    sensitivity: int = 50
    auto_update: bool = True
    enabled: dict = field(default_factory=dict)
    colors: dict = field(default_factory=dict)
    collapsed: list = None

    LIMITS = {"camera": (0, 15), "monitor": (0, 15), "marker_size": (5, 16), "marker_opacity": (30, 100),
              "radius": (10, 100), "smoothing": (0, 100), "sensitivity": (0, 100)}
    BUTTONS = ("left", "right", "middle")

    @property
    def fix_blend(self):
        return max(0.15, 1.0 - 0.85 * self.smoothing / 100.0)

    @property
    def min_inliers(self):
        return int(round(30 - 0.2 * self.sensitivity))

    @property
    def radius_fraction(self):
        return self.radius / 100.0 if self.radius_enabled else None

    @classmethod
    def load(cls, path):
        cfg = cls()
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            return cfg
        if not isinstance(raw, dict):
            return cfg
        for fld in fields(cls):
            if fld.name not in raw:
                continue
            value, default = raw[fld.name], getattr(cfg, fld.name)
            if fld.name == "collapsed":
                if isinstance(value, list):
                    cfg.collapsed = [str(v) for v in value]
            elif isinstance(default, bool):
                if isinstance(value, bool):
                    setattr(cfg, fld.name, value)
            elif isinstance(default, int):
                if isinstance(value, int) and not isinstance(value, bool):
                    lo, hi = cls.LIMITS.get(fld.name, (value, value))
                    setattr(cfg, fld.name, min(max(value, lo), hi))
            elif isinstance(default, str):
                if value in cls.BUTTONS:
                    setattr(cfg, fld.name, value)
            elif isinstance(default, dict):
                if isinstance(value, dict):
                    setattr(cfg, fld.name, value)
        if cfg.info_button == cfg.mark_button:
            cfg.info_button, cfg.mark_button = "left", "right"
        return cfg

    def save(self, path):
        payload = {f.name: getattr(self, f.name) for f in fields(self)}
        try:
            _atomic_write(path, payload, indent=1)
        except OSError:
            pass


class FoundStore:
    def __init__(self, path, ids):
        self.path = path
        self.ids = list(ids)
        self.index = {cid: i for i, cid in enumerate(self.ids)}
        self.mask = np.zeros(len(self.ids), bool)
        self.undo = []
        self._merge(self._read(path))

    @staticmethod
    def _read(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            found = data.get("found", []) if isinstance(data, dict) else []
            return found if isinstance(found, list) else []
        except (OSError, ValueError):
            return []

    def _merge(self, found):
        added = 0
        for cid in found:
            i = self.index.get(cid)
            if i is not None and not self.mask[i]:
                self.mask[i] = True
                added += 1
        return added

    def _save(self):
        try:
            _atomic_write(self.path, {"found": [self.ids[i] for i in np.flatnonzero(self.mask)]})
        except OSError:
            pass

    def toggle(self, i):
        self.mask[i] = not self.mask[i]
        if self.mask[i]:
            self.undo.append(i)
        self._save()
        return bool(self.mask[i])

    def undo_last(self):
        while self.undo:
            i = self.undo.pop()
            if self.mask[i]:
                self.mask[i] = False
                self._save()
                return i
        return None

    def count(self):
        return int(self.mask.sum())

    def reset(self):
        self.mask[:] = False
        self.undo.clear()
        self._save()

    def export_to(self, path):
        _atomic_write(path, {"found": [self.ids[i] for i in np.flatnonzero(self.mask)]})

    def import_from(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        found = data.get("found") if isinstance(data, dict) else None
        if not isinstance(found, list):
            raise ValueError("not a progress file")
        added = self._merge(found)
        self._save()
        return added
