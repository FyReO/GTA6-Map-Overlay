import colorsys
import json
from dataclasses import dataclass

import numpy as np

from . import config as C
from .errors import DataError


def default_color(i):
    r, g, b = colorsys.hsv_to_rgb((i * 0.61803398875) % 1.0, 0.85, 1.0 if i % 2 == 0 else 0.8)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


@dataclass
class Catalog:
    items: list
    info: dict
    ids: list
    set_names: list
    set_idx: np.ndarray
    set_group: list
    groups: list
    set_gidx: np.ndarray
    group_shapes: list

    def set_totals(self):
        return np.bincount(self.set_idx, minlength=len(self.set_names))


def load_catalog(data_dir):
    items = _read_json(data_dir / "cards_latlng.json")
    if not items:
        raise DataError("cards_latlng.json is missing from the map data")
    for item in items:
        item.setdefault("group", C.DEFAULT_GROUP)
    have = {item["id"] for item in items}
    extras = _read_json(data_dir / "extras.json") or []
    items += [x for x in extras if x["id"] not in have]

    info = {str(k): v for k, v in (_read_json(data_dir / "cards_info.json") or {}).items()}
    for item in items:
        if "description" in item or "files" in item:
            info.setdefault(str(item["id"]), {}).update(
                description=item.get("description", ""), files=item.get("files", []))

    sets = [str(item.get("set", "")) for item in items]
    set_names = list(dict.fromkeys(sets))
    position = {name: i for i, name in enumerate(set_names)}
    first_group = {}
    for item, name in zip(items, sets):
        first_group.setdefault(name, item["group"])
    set_group = [first_group[name] for name in set_names]
    groups = list(dict.fromkeys(set_group))
    return Catalog(
        items=items,
        info=info,
        ids=[item["id"] for item in items],
        set_names=set_names,
        set_idx=np.array([position[s] for s in sets]),
        set_group=set_group,
        groups=groups,
        set_gidx=np.array([groups.index(g) for g in set_group]),
        group_shapes=[C.GROUP_SHAPES.get(g, "circle") for g in groups],
    )
