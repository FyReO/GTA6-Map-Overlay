import argparse
import hashlib
import json
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from gta6overlay import config as C
from gta6overlay.features import extract_tiled, save_features


def find_reference(source, name):
    stem, ext = Path(name).stem, Path(name).suffix
    for candidate in (name, stem.replace(".", "_") + ext):
        path = source / candidate
        if path.is_file():
            return path
    raise SystemExit(f"reference image not found: {name} (looked in {source})")


def load_json(path, required=False):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if required:
            raise SystemExit(f"missing or unreadable: {path}")
        return None


def build_features(source, stage, levels):
    sift = cv2.SIFT_create(nfeatures=C.REF_TILE_FEATURES)
    out = []
    (stage / "features").mkdir(parents=True, exist_ok=True)
    for info in levels:
        path = find_reference(source, info["file"])
        print(f"zoom {info['zoom']}: reading {path.name}")
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise SystemExit(f"could not decode {path}")
        started = time.time()
        pts, des = extract_tiled(
            img, sift, progress=lambda r, n: print(f"  tile row {r}/{n}", end="\r", flush=True))
        rel = f"features/z{info['zoom']}.npz"
        save_features(stage / rel, pts, des)
        print(f"\n  {len(pts)} features in {time.time() - started:.0f}s -> {rel}")
        entry = {k: v for k, v in info.items() if k != "file"}
        entry["features"] = rel
        out.append(entry)
        del img
    return out


def copy_content(source, stage):
    cards = load_json(source / "cards_latlng.json", required=True)
    info = load_json(source / "cards_info.json") or {}
    extras = load_json(source / "extras.json") or []
    media = source / "card_media"
    needed = set()

    slim_info = {}
    for cid, entry in info.items():
        files = entry.get("files", [])
        needed.update(files)
        slim_info[cid] = {"title": entry.get("title", ""), "description": entry.get("description", ""),
                          "files": files}
    for entry in extras:
        needed.update(entry.get("files", []))
        entry.pop("images", None)

    (stage / "card_media").mkdir(parents=True, exist_ok=True)
    missing = 0
    for name in sorted(needed):
        src = media / name
        if src.is_file():
            shutil.copy2(src, stage / "card_media" / name)
        else:
            missing += 1
    if missing:
        print(f"warning: {missing} referenced images were not found in {media}")
    (stage / "cards_latlng.json").write_text(json.dumps(cards), encoding="utf-8")
    (stage / "cards_info.json").write_text(json.dumps(slim_info), encoding="utf-8")
    if extras:
        (stage / "extras.json").write_text(json.dumps(extras), encoding="utf-8")
    return len(cards), len(extras), len(needed) - missing


def zip_stage(stage, target):
    with zipfile.ZipFile(target, "w") as zf:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                kind = zipfile.ZIP_STORED if path.suffix in (".npz", ".jpg", ".png") else zipfile.ZIP_DEFLATED
                zf.write(path, path.relative_to(stage).as_posix(), compress_type=kind)


def main():
    parser = argparse.ArgumentParser(description="Build data-pack.zip for a GitHub data release")
    parser.add_argument("--version", type=int, required=True, help="data version number (release tag data-N)")
    parser.add_argument("--source", type=Path, default=Path("."), help="folder with ref_meta.json, ref_z*.png, "
                        "cards_latlng.json, cards_info.json, extras.json and card_media/")
    parser.add_argument("--out", type=Path, default=Path("dist-data"))
    args = parser.parse_args()

    meta = load_json(args.source / "ref_meta.json", required=True)
    stage = args.out / "stage"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)

    levels = build_features(args.source, stage, meta["levels"])
    meta["levels"] = levels
    (stage / "ref_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    cards, extras, images = copy_content(args.source, stage)
    (stage / "manifest.json").write_text(json.dumps({
        "data_version": args.version,
        "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "levels": [l["zoom"] for l in levels], "cards": cards, "extras": extras, "images": images,
    }, indent=1), encoding="utf-8")

    target = args.out / C.DATA_ASSET
    zip_stage(stage, target)
    shutil.rmtree(stage, ignore_errors=True)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (args.out / (C.DATA_ASSET + ".sha256")).write_text(f"{digest}  {C.DATA_ASSET}\n", encoding="ascii")

    size = target.stat().st_size / 1024 ** 2
    print(f"\nbuilt {target} ({size:.1f} MB): {cards} cards, {extras} extra markers, {images} images")
    print("\nPublish it with:\n")
    print(f'  gh release create data-{args.version} "{target}" "{target}.sha256" '
          f'--repo {C.GITHUB_REPO} --title "Map data {args.version}" --notes "Map data update"')


if __name__ == "__main__":
    main()
