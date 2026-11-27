import hashlib
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

INFO_JSON = "cards_info.json"
CARDS_JSON = "cards_latlng.json"
EXTRAS_JSON = "extras.json"
MEDIA_DIR = "card_media"
MAX_SIDE = 640   # images are shrunk to this (they're shown small in the overlay)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://mapgenie.io/",
}
FAILS = []


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def fetch(url):
    name = hashlib.sha1(url.encode()).hexdigest()[:16] + ".jpg"
    path = os.path.join(MEDIA_DIR, name)
    if os.path.exists(path):
        return url, name
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        data = urllib.request.urlopen(req, timeout=30).read()
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("not a decodable image")
        f = MAX_SIDE / max(img.shape[:2])
        if f < 1:
            img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return url, name
    except Exception as e:
        FAILS.append((url, e))
        if len(FAILS) <= 5:
            print("failed:", url, e)
        return url, None


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def main():
    os.makedirs(MEDIA_DIR, exist_ok=True)
    info = load(INFO_JSON)
    extras = load(EXTRAS_JSON)
    cards = load(CARDS_JSON) or []
    if info is None and extras is None:
        raise SystemExit(f"Neither {INFO_JSON} nor {EXTRAS_JSON} found - run the export scripts first.")
    info = info or {}
    extras = extras or []
    wanted = [str(c["id"]) for c in cards]

    urls = {u for cid in wanted for u in info.get(cid, {}).get("images", [])}
    urls |= {u for e in extras for u in e.get("images", [])}
    urls = sorted(urls)
    print(f"{len(urls)} unique images to fetch")
    with ThreadPoolExecutor(8) as ex:
        done = dict(ex.map(fetch, urls))

    for cid in wanted:
        e = info.get(cid)
        if e:
            e["files"] = [done[u] for u in e.get("images", []) if done.get(u)]
    for e in extras:
        e["files"] = [done[u] for u in e.get("images", []) if done.get(u)]

    if info:
        save(INFO_JSON, info)
    if extras:
        save(EXTRAS_JSON, extras)
    ok = sum(1 for v in done.values() if v)
    print(f"done: {ok}/{len(urls)} images saved to {MEDIA_DIR}/")
    if FAILS:
        print(f"{len(FAILS)} failed (only the first 5 were printed above)")


if __name__ == "__main__":
    main()
