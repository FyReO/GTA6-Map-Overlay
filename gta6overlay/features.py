import math

import cv2
import numpy as np

from . import config as C


def merc(lat, lng):
    x = (lng + 180.0) / 360.0
    y = 0.5 - math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) / (2 * math.pi)
    return x, y


def extract_tiled(img, sift, tile=C.REF_TILE, overlap=C.REF_TILE_OVERLAP, progress=None):
    height, width = img.shape
    step = tile - overlap
    half = overlap // 2
    ys = list(range(0, max(height - overlap, 1), step))
    xs = list(range(0, max(width - overlap, 1), step))
    pts_all, des_all = [], []
    for r, y0 in enumerate(ys):
        for c, x0 in enumerate(xs):
            kp, des = sift.detectAndCompute(img[y0:y0 + tile, x0:x0 + tile], None)
            if des is None:
                continue
            pts = np.float32([k.pt for k in kp]) + np.float32([x0, y0])
            cx0 = 0 if c == 0 else x0 + half
            cx1 = width if c == len(xs) - 1 else x0 + step + half
            cy0 = 0 if r == 0 else y0 + half
            cy1 = height if r == len(ys) - 1 else y0 + step + half
            keep = (pts[:, 0] >= cx0) & (pts[:, 0] < cx1) & (pts[:, 1] >= cy0) & (pts[:, 1] < cy1)
            pts_all.append(pts[keep])
            des_all.append(des[keep])
        if progress:
            progress(r + 1, len(ys))
    return np.vstack(pts_all), np.vstack(des_all).astype(np.float32)


def save_features(path, pts, des):
    packed = np.clip(np.rint(des), 0, 255).astype(np.uint8)
    np.savez_compressed(path, pts=pts.astype(np.float32), des=packed)


def load_features(path):
    with np.load(path) as data:
        return data["pts"].astype(np.float32), data["des"].astype(np.float32)


def fit_transform(src, dst, thr, model=C.ALIGN_MODEL):
    if len(src) < 4:
        return None, 0
    if model == "homography":
        H, mask = cv2.findHomography(src.reshape(-1, 1, 2), dst.reshape(-1, 1, 2), cv2.RANSAC, thr)
    else:
        fit = cv2.estimateAffine2D if model == "affine" else cv2.estimateAffinePartial2D
        M, mask = fit(src, dst, method=cv2.RANSAC, ransacReprojThreshold=thr)
        H = None if M is None else np.vstack([M, [0, 0, 1]])
    if H is None or mask is None:
        return None, 0
    return H, int(mask.sum())
