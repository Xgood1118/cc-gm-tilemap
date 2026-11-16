# -*- coding: utf-8 -*-
"""瓦片地图渲染器。

支持：图集边距/间隔取块、多图层按序合成与 alpha 混合、水平/垂直翻转、
按时间选帧的动画层、视野裁剪（视野外的瓦片不遍历，边缘瓦片裁掉）。
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
        """返回第 index 块瓦片（从 0 计）在图集里的左上角坐标。

        按边距与间隔定位；索引为负或瓦片区域超出图集时抛 IndexError，
        避免错位读到别的瓦片或间隔像素。
        """
        if index < 0:
            raise IndexError("瓦片索引不能为负: %d" % index)
        col = index % self.columns
        row = index // self.columns
        x = self.margin + col * (self.tile_w + self.spacing)
        y = self.margin + row * (self.tile_h + self.spacing)
        if x + self.tile_w > self.image.width or y + self.tile_h > self.image.height:
            raise IndexError(
                "瓦片索引 %d 超出图集范围（图集 %dx%d）" % (
                    index, self.image.width, self.image.height))
        return x, y


def load_map(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _blend(img, x, y, src, opacity):
    """把 src 像素按图层不透明度 source-over 混合到 img 的 (x, y)。"""
    sr, sg, sb, sa = src
    a = int(round(sa * opacity))
    if a <= 0:
        return
    if a >= 255:
        img.set(x, y, (sr, sg, sb, 255))
        return
    dr, dg, db, da = img.at(x, y)
    inv = 255 - a
    r = (sr * a + dr * inv + 127) // 255
    g = (sg * a + dg * inv + 127) // 255
    b = (sb * a + db * inv + 127) // 255
    out_a = min(255, a + (da * inv + 127) // 255)
    img.set(x, y, (r, g, b, out_a))


def _anim_gid(layer, gid, time_s):
    """动画层按时间选帧，返回该时刻应显示的 gid。

    数据里的非零 gid 选中第 (gid - 1) % len(frames) 组帧序列；
    帧下标 = floor(time_s / frame_duration) % 帧数，
    帧数乘帧时长正好是一个循环，同一时刻渲染结果一致。
    """
    frames = layer.get("frames")
    if not frames:
        return gid
    duration = float(layer.get("frame_duration", 1.0))
    if duration <= 0:
        raise ValueError("frame_duration 必须为正数")
    group = frames[(gid - 1) % len(frames)]
    if not group:
        return gid
    frame_idx = int(time_s / duration) % len(group)
    return group[frame_idx]


def render_map(world, tileset, view_x, view_y, view_w, view_h, time_s=0.0):
    """按视野渲染地图：三层按顺序合成，上层覆盖/混合到下层之上。"""
    img = Image(view_w, view_h, [(20, 20, 20, 255)] * (view_w * view_h))
    tile_w = tileset.tile_w
    tile_h = tileset.tile_h
    for layer in world["layers"]:
        data = layer["data"]
        opacity = float(layer.get("opacity", 1.0))
        flags = layer.get("flip_flags")
        rows = len(data)
        # 只遍历与视野相交的瓦片，视野外的一律不算
        tx0 = max(0, view_x // tile_w)
        ty0 = max(0, view_y // tile_h)
        tx1 = min((max((len(r) for r in data), default=0)),
                  (view_x + view_w + tile_w - 1) // tile_w)
        ty1 = min(rows, (view_y + view_h + tile_h - 1) // tile_h)
        for ty in range(ty0, ty1):
            row = data[ty]
            flag_row = flags[ty] if flags else None
            for tx in range(tx0, min(tx1, len(row))):
                gid = row[tx]
                if gid == 0:
                    continue
                gid = _anim_gid(layer, gid, time_s)
                flip = flag_row[tx] if flag_row else 0
                src_x, src_y = tileset.tile_rect(gid - 1)
                dst_x = tx * tile_w - view_x
                dst_y = ty * tile_h - view_y
                # 视野起点不对齐瓦片时，边缘瓦片只画落在视野内的那一半
                px0 = max(0, -dst_x)
                px1 = min(tile_w, view_w - dst_x)
                py0 = max(0, -dst_y)
                py1 = min(tile_h, view_h - dst_y)
                for py in range(py0, py1):
                    sy = src_y + (tile_h - 1 - py if flip & 2 else py)
                    dy = dst_y + py
                    for px in range(px0, px1):
                        sx = src_x + (tile_w - 1 - px if flip & 1 else px)
                        dx = dst_x + px
                        _blend(img, dx, dy, tileset.image.at(sx, sy), opacity)
    return img


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="tilemap")
    ap.add_argument("map")
    ap.add_argument("--tileset", default="data/tileset.png")
    ap.add_argument("--view", default="0,0,256,192")
    ap.add_argument("--out", default="tilemap.png")
    ap.add_argument("--time", type=float, default=0.0)
    args = ap.parse_args(argv)
    world = load_map(args.map)
    image = load_png(args.tileset)
    tileset = Tileset(image, world["tile_width"], world["tile_height"],
                      world.get("margin", 0), world.get("spacing", 0),
                      world.get("columns", 8))
    vx, vy, vw, vh = [int(v) for v in args.view.split(",")]
    out = render_map(world, tileset, vx, vy, vw, vh, time_s=args.time)
    save_png(out, args.out)
    print("已输出 %s" % args.out)
    return 0
