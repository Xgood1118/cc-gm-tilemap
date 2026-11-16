# -*- coding: utf-8 -*-
"""生成 8x8 的瓦片图集（32x32，带 2 像素边距与 2 像素间隔）与三层地图。"""
import json
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TILE = 32
MARGIN = 2
SPACING = 2
COLS = 8
ROWS = 8
COLORS = [
    (90, 140, 70), (60, 110, 200), (200, 170, 80), (140, 90, 60),
    (180, 60, 60), (80, 80, 160), (220, 220, 220), (40, 40, 40),
]


def build_tileset():
    w = MARGIN * 2 + COLS * TILE + (COLS - 1) * SPACING
    h = MARGIN * 2 + ROWS * TILE + (ROWS - 1) * SPACING
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            c = (0, 0, 0, 0)
            if MARGIN <= y < h - MARGIN and MARGIN <= x < w - MARGIN:
                col = (x - MARGIN) // (TILE + SPACING)
                row = (y - MARGIN) // (TILE + SPACING)
                if col < COLS and row < ROWS:
                    idx = row * COLS + col
                    base = COLORS[idx % len(COLORS)]
                    shade = 1.0 - 0.5 * ((x - MARGIN) % TILE) / float(TILE)
                    c = (int(base[0] * shade), int(base[1] * shade),
                         int(base[2] * shade), 255)
            raw.extend(c)
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    path = os.path.join(HERE, "data", "tileset.png")
    with open(path, "wb") as f:
        f.write(data)
    return w, h


def build_map():
    ground = [[0] * 24 for _ in range(16)]
    for y in range(16):
        for x in range(24):
            ground[y][x] = 1 if (x + y) % 3 != 0 else 2
    decor = [[0] * 24 for _ in range(16)]
    for y in range(2, 14, 4):
        for x in range(1, 22, 5):
            decor[y][x] = 5
    anim = [[0] * 24 for _ in range(16)]
    anim[3][3] = 7
    world = {
        "tile_width": TILE,
        "tile_height": TILE,
        "margin": MARGIN,
        "spacing": SPACING,
        "columns": COLS,
        "layers": [
            {"name": "ground", "opacity": 1.0, "data": ground,
             "flip_flags": [[0] * 24 for _ in range(16)]},
            {"name": "decor", "opacity": 1.0, "data": decor,
             "flip_flags": [[3 if x % 2 else 1 for x in range(24)] for _ in range(16)]},
            {"name": "anim", "opacity": 1.0, "data": anim,
             "frames": [[1, 2, 3, 4]], "frame_duration": 0.15},
        ],
    }
    path = os.path.join(HERE, "data", "map.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(world, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    size = build_tileset()
    build_map()
    print("已生成 tileset %dx%d 与 map.json" % size)
