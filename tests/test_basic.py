# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tilemap.core import Image, Tileset, load_map  # noqa: E402


def test_image_default():
    img = Image(4, 3)
    assert img.width == 4 and img.height == 3
    assert img.at(0, 0) == (0, 0, 0, 255)


def test_tileset_rect():
    ts = Tileset(Image(1, 1), 32, 32, 2, 2, 8)
    assert ts.tile_rect(0) == (2, 2)
    assert ts.tile_rect(8) == (2, 2 + 34)


def test_map_layers():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "map.json")
    if not os.path.exists(path):
        return
    world = load_map(path)
    assert len(world["layers"]) == 3
    assert world["tile_width"] == 32
