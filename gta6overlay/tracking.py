import collections
import json
import math

import cv2
import numpy as np

from . import config as C
from .errors import DataError
from .features import fit_transform, load_features, merc


def _hud_mask(shape):
    mask = np.full(shape, 255, np.uint8)
    height, width = shape
    for x0, y0, x1, y1 in C.HUD_ZONES:
        mask[int(y0 * height):int(y1 * height), int(x0 * width):int(x1 * width)] = 0
    return mask


def _flann():
    return cv2.FlannBasedMatcher(dict(algorithm=1, trees=4), dict(checks=40))


def _ratio_matches(matches, ratio):
    return [m for m, n in (p for p in matches if len(p) == 2) if m.distance < ratio * n.distance]


class Level:
    def __init__(self, info, items, features_path):
        self.zoom = info["zoom"]
        self.S, self.ox, self.oy = info["S"], info["ox"], info["oy"]
        self.pts, self.des = load_features(features_path)
        self.matcher = _flann()
        self.matcher.add([self.des])
        self.matcher.train()
        xy = [merc(c["lat"], c["lng"]) for c in items]
        self.cards = np.float32([[x * self.S - self.ox, y * self.S - self.oy] for x, y in xy]).reshape(-1, 1, 2)


def load_levels(data_dir, items, progress=None):
    try:
        with open(data_dir / "ref_meta.json", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        raise DataError("ref_meta.json is missing from the map data")
    levels = []
    entries = meta.get("levels", [])
    for n, info in enumerate(entries):
        path = data_dir / info.get("features", "")
        if path.is_file():
            levels.append(Level(info, items, path))
        if progress:
            progress(n + 1, len(entries))
    if not levels:
        raise DataError("the map data contains no reference levels")
    return levels


def visible_mask(p, radius=None):
    keep = (p[:, 0] >= 0) & (p[:, 0] <= 1) & (p[:, 1] >= 0) & (p[:, 1] <= 1)
    for x0, y0, x1, y1 in C.HUD_ZONES:
        keep &= ~((p[:, 0] >= x0) & (p[:, 0] <= x1) & (p[:, 1] >= y0) & (p[:, 1] <= y1))
    if radius:
        d = np.hypot((p[:, 0] - 0.5) * 16 / 9, p[:, 1] - 0.5)
        keep &= d < radius
    return keep


class Tracker:
    def __init__(self, cfg, levels):
        self.cfg = cfg
        self.levels = levels
        self.sift = cv2.SIFT_create(nfeatures=4000)
        self.matcher = _flann()
        self.key = None
        self.memory = collections.deque(maxlen=C.MEMORY_KEYFRAMES)
        self.allow_ref = True
        self.last = None
        self.lost = 0
        self.inliers = 0
        self.level_zoom = None
        self.mode = "-"
        self.frame_i = 0
        self._mask = None

    def _feature_mask(self, shape):
        if self._mask is None or self._mask.shape != shape:
            self._mask = _hud_mask(shape)
        return self._mask

    def _try_level(self, lv, kp_pts, des):
        if len(kp_pts) < 8:
            return None, 0
        good = _ratio_matches(lv.matcher.knnMatch(des, k=2), 0.75)
        floor = self.cfg.min_inliers
        if len(good) < floor:
            return None, 0
        dst = kp_pts[[m.queryIdx for m in good]]
        src = lv.pts[[m.trainIdx for m in good]]
        H, n = fit_transform(src, dst, C.ALIGN_THRESH)
        return (H, n) if H is not None and n >= floor else (None, 0)

    def _track(self, kp_pts, des, key=None):
        key = key or self.key
        if len(kp_pts) < 8 or len(key["pts"]) < 8:
            return None, 0
        good = _ratio_matches(self.matcher.knnMatch(des, key["des"], k=2), 0.75)
        if len(good) < C.MIN_TRACK_INLIERS:
            return None, 0
        dst = kp_pts[[m.queryIdx for m in good]]
        src = key["pts"][[m.trainIdx for m in good]]
        M, mask = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0)
        if M is None:
            return None, 0
        n = int(mask.sum())
        if n < C.MIN_TRACK_INLIERS:
            return None, 0
        return np.vstack([M, [0, 0, 1]]), n

    def _recover(self, kp_pts, des):
        for key in reversed(self.memory):
            Ht, nt = self._track(kp_pts, des, key)
            if Ht is not None and nt >= C.RECOVER_INLIERS:
                self.key = key
                return

    def _refine(self, kp_pts, des, H, lv, size):
        s = self._scale(H)
        if not s > 0:
            return None
        best = min(self.levels, key=lambda L: abs(math.log(s * lv.S / L.S)))
        k = lv.S / best.S
        T = np.array([[k, 0, best.ox * k - lv.ox], [0, k, best.oy * k - lv.oy], [0, 0, 1.0]])
        try:
            inv = np.linalg.inv(H @ T)
        except np.linalg.LinAlgError:
            return None
        w, h = size
        corners = np.array([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]], float).T
        q = inv @ corners
        q = (q[:2] / q[2]).T
        x0, y0 = q.min(0)
        x1, y1 = q.max(0)
        mx, my = 0.1 * (x1 - x0), 0.1 * (y1 - y0)
        P = best.pts
        sel = np.flatnonzero((P[:, 0] >= x0 - mx) & (P[:, 0] <= x1 + mx)
                             & (P[:, 1] >= y0 - my) & (P[:, 1] <= y1 + my))
        if len(sel) < 30:
            return None
        good = _ratio_matches(self.matcher.knnMatch(des, best.des[sel], k=2), 0.8)
        if len(good) < C.REFINE_MIN_INLIERS:
            return None
        dst = kp_pts[[m.queryIdx for m in good]]
        src = P[sel[[m.trainIdx for m in good]]]
        H2, n = fit_transform(src, dst, C.ALIGN_THRESH)
        if H2 is None or n < C.REFINE_MIN_INLIERS:
            return None
        r = H2 @ (inv @ np.array([w / 2, h / 2, 1.0]))
        r = r[:2] / r[2]
        if np.hypot(r[0] - w / 2, r[1] - h / 2) > 0.25 * w:
            return None
        if not 0.8 < self._scale(H2) / (s * lv.S / best.S) < 1.25:
            return None
        return H2, best, n

    @staticmethod
    def _scale(H):
        return math.sqrt(abs(np.linalg.det(H[:2, :2]) / H[2, 2] ** 2))

    def _agree(self, H_ref, lv_ref, H_trk, lv_trk, size):
        c = np.array([size[0] / 2, size[1] / 2, 1.0])
        p = np.linalg.inv(H_trk) @ c
        p = p[:2] / p[2]
        wx, wy = (p[0] + lv_trk.ox) / lv_trk.S, (p[1] + lv_trk.oy) / lv_trk.S
        q = np.array([wx * lv_ref.S - lv_ref.ox, wy * lv_ref.S - lv_ref.oy, 1.0])
        r = H_ref @ q
        r = r[:2] / r[2]
        return np.hypot(r[0] - c[0], r[1] - c[1]) < 0.05 * size[0]

    def process(self, frame):
        self.frame_i += 1
        self.last = None
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (C.PROC_WIDTH, int(h * C.PROC_WIDTH / w)))
        size = (small.shape[1], small.shape[0])
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        kp, des = self.sift.detectAndCompute(gray, self._feature_mask(gray.shape))
        if des is None or len(kp) < 8:
            self._miss()
            return
        kp_pts = np.float32([k.pt for k in kp])

        if self.key is None and self.memory:
            self._recover(kp_pts, des)

        trk = None
        if self.key is not None:
            Ht, nt = self._track(kp_pts, des)
            if Ht is not None:
                trk = (Ht @ self.key["H"], nt, Ht)

        ref = None
        if self.allow_ref and (trk is None or self.frame_i % C.RECHECK_EVERY == 0):
            for lv in self.levels:
                H, n = self._try_level(lv, kp_pts, des)
                if H is not None and (ref is None or n > ref[1]):
                    ref = (H, n, lv)

        use_ref = ref is not None
        if use_ref and trk is not None and ref[1] < 40:
            use_ref = self._agree(ref[0], ref[2], trk[0], self.key["lv"], size)

        if use_ref:
            H, n, lv = ref
            self.mode = "ref"
            new_key = True
        elif trk is not None:
            H, n, _ = trk
            lv = self.key["lv"]
            self.mode = "track"
            new_key = n < C.KEYFRAME_INLIERS or not (0.75 < self._scale(trk[2]) < 1.33)
        else:
            self._miss()
            return

        refined = self._refine(kp_pts, des, H, lv, size)
        if refined is not None:
            H, lv, n = refined
            self.mode += "+"
            new_key = True
        if new_key:
            self.key = dict(pts=kp_pts, des=des, H=H, lv=lv)

        self.inliers, self.level_zoom = n, lv.zoom
        self.last = (H, lv, n, size)
        self.lost = 0

    def _miss(self):
        self.inliers = 0
        self.mode = "lost"
        self.lost += 1
        if self.lost > C.LOST_FRAMES and self.key is not None:
            if not self.memory or self.memory[-1] is not self.key:
                self.memory.append(self.key)
            self.key = None


class FastLayer:
    def __init__(self):
        self.mask = None
        self.prev = None
        self.prev_pts = None
        self.hist = collections.OrderedDict()
        self.B = None
        self.lv = None
        self.anchor_time = 0.0
        self.epoch = 0
        self._break()

    def _break(self):
        self.G = np.eye(3)
        self.epoch += 1
        self.hist.clear()
        self.B = None
        self.lv = None

    def step(self, fid, gray):
        if self.prev is not None:
            ok = False
            if self.prev_pts is not None and len(self.prev_pts) >= 25:
                p1, st, _ = cv2.calcOpticalFlowPyrLK(
                    self.prev, gray, self.prev_pts, None, winSize=(21, 21), maxLevel=4,
                    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
                st = st.ravel() == 1
                if st.sum() >= 20:
                    M, inl = cv2.estimateAffinePartial2D(
                        self.prev_pts[st], p1[st], method=cv2.RANSAC, ransacReprojThreshold=1.5)
                    if M is not None and inl.sum() >= 15:
                        self.G = np.vstack([M, [0, 0, 1]]) @ self.G
                        ok = True
            if not ok:
                self._break()
        self.hist[fid] = (self.G.copy(), self.epoch)
        while len(self.hist) > 90:
            self.hist.popitem(last=False)
        if self.mask is None or self.mask.shape != gray.shape:
            self.mask = _hud_mask(gray.shape)
        self.prev_pts = cv2.goodFeaturesToTrack(
            gray, maxCorners=300, qualityLevel=0.01, minDistance=8, mask=self.mask)
        self.prev = gray

    def apply_fix(self, fid, H, lv, now, size=None, blend=0.5):
        h = self.hist.get(fid)
        if h is None or h[1] != self.epoch:
            return False
        B_new = np.linalg.inv(h[0]) @ H
        if (size is not None and self.B is not None and self.lv is lv
                and now - self.anchor_time <= C.ANCHOR_TIMEOUT):
            c = np.array([size[0] / 2, size[1] / 2, 1.0])
            o = h[0] @ self.B @ (np.linalg.inv(H) @ c)
            o = o[:2] / o[2]
            if np.hypot(o[0] - c[0], o[1] - c[1]) < C.FIX_SNAP * size[0]:
                B_new = (1 - blend) * self.B + blend * B_new
        self.B = B_new
        self.lv = lv
        self.anchor_time = now
        return True

    def current(self, now):
        if self.B is None or now - self.anchor_time > C.ANCHOR_TIMEOUT:
            return None, None
        return self.G @ self.B, self.lv
