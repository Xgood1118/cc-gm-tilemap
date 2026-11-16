# -*- coding: utf-8 -*-
"""瓦片地图渲染骨架。

当前只画第一层，忽略翻转标记与动画帧，越出地图范围的瓦片直接崩。
"""

import json
import struct
import zlib


class Image(object):
    def __init__(self, width, height, pixels=None):
        self.width = int(width)
        self.height = int(height)
        self.pixels = pixels or [(0, 0, 0, 255)] * (self.width * self.height)

    def at(self, x, y):
        return self.pixels[y * self.width + x]

    def set(self, x, y, rgba):
        self.pixels[y * self.width + x] = rgba


def load_png(path):
    with open(path, "rb") as f:
        data = f.read()
    pos = 8
    idat = b""
    width = height = bit = ctype = None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, bit, ctype = struct.unpack(">IIBB", body[:10])
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
    if bit != 8 or ctype != 6:
        raise ValueError("只支持 8 位 RGBA")
    raw = zlib.decompress(idat)
    pixels = []
    stride = width * 4
    for y in range(height):
        ft = raw[y * (stride + 1)]
        line = raw[y * (stride + 1) + 1: y * (stride + 1) + 1 + stride]
        if ft != 0:
            raise ValueError("只支持无过滤")
        for x in range(width):
            pixels.append(tuple(line[x * 4:x * 4 + 4]))
    return Image(width, height, pixels)


def save_png(img, path):
    raw = bytearray()
    for y in range(img.height):
        raw.append(0)
        for x in range(img.width):
            raw.extend(img.at(x, y))
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", img.width, img.height, 8, 6, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


class Tileset(object):
    def __init__(self, image, tile_w, tile_h, margin=0, spacing=0, columns=8):
        self.image = image
        self.tile_w = int(tile_w)
        self.tile_h = int(tile_h)
        self.margin = int(margin)
        self.spacing = int(spacing)
        self.columns = int(columns)

    def tile_rect(self, index):
        col = index % self.columns
        row = index // self.columns
        x = self.margin + col * (self.tile_w + self.spacing)
        y = self.margin + row * (self.tile_h + self.spacing)
        return x, y


def load_map(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_map(world, tileset, view_x, view_y, view_w, view_h, time_s=0.0):
    """渲染地图。只画第一层，不做翻转，不做视野裁剪。"""
    img = Image(view_w, view_h, [(20, 20, 20, 255)])
    tile_w = tileset.tile_w
    tile_h = tileset.tile_h
    layer = world["layers"][0]
    for ty, row in enumerate(layer["data"]):
        for tx, gid in enumerate(row):
            if gid == 0:
                continue
            src_x, src_y = tileset.tile_rect(gid - 1)
            dst_x = tx * tile_w - view_x
            dst_y = ty * tile_h - view_y
            for py in range(tile_h):
                for px in range(tile_w):
                    sx = src_x + px
                    sy = src_y + py
                    dx = dst_x + px
                    dy = dst_y + py
                    img.set(dx, dy, tileset.image.at(sx, sy))
    return img


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="tilemap")
    ap.add_argument("map")
    ap.add_argument("--tileset", default="data/tileset.png")
    ap.add_argument("--view", default="0,0,256,192")
    ap.add_argument("--out", default="tilemap.png")
    args = ap.parse_args(argv)
    world = load_map(args.map)
    image = load_png(args.tileset)
    tileset = Tileset(image, world["tile_width"], world["tile_height"],
                      world.get("margin", 0), world.get("spacing", 0),
                      world.get("columns", 8))
    vx, vy, vw, vh = [int(v) for v in args.view.split(",")]
    out = render_map(world, tileset, vx, vy, vw, vh)
    save_png(out, args.out)
    print("已输出 %s" % args.out)
    return 0
