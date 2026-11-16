# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tilemap.core import (  # noqa: E402
    Image, Tileset, load_map, render_map,
)


# ---------------------------------------------------------------- 图集取块

def test_image_default():
    img = Image(4, 3)
    assert img.width == 4 and img.height == 3
    assert img.at(0, 0) == (0, 0, 0, 255)


def test_tileset_rect():
    ts = Tileset(Image(300, 300), 32, 32, 2, 2, 8)
    assert ts.tile_rect(0) == (2, 2)
    assert ts.tile_rect(8) == (2, 2 + 34)


def test_tileset_rect_last_column_and_row():
    # 8x8 个 32x32 瓦片，margin=2 spacing=2，与 data/tileset.png 同布局
    ts = Tileset(Image(274, 274), 32, 32, 2, 2, 8)
    # 最后一列不能错位到间隔里
    assert ts.tile_rect(7) == (2 + 7 * 34, 2)
    # 最后一行最后一列
    assert ts.tile_rect(63) == (2 + 7 * 34, 2 + 7 * 34)
    x, y = ts.tile_rect(63)
    assert x + 32 == 274 - 2 and y + 32 == 274 - 2


def test_tileset_rect_out_of_range():
    ts = Tileset(Image(274, 274), 32, 32, 2, 2, 8)
    with pytest.raises(IndexError):
        ts.tile_rect(64)   # 第 9 行不存在
    with pytest.raises(IndexError):
        ts.tile_rect(-1)


def test_map_layers():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "map.json")
    if not os.path.exists(path):
        return
    world = load_map(path)
    assert len(world["layers"]) == 3
    assert world["tile_width"] == 32


# ---------------------------------------------------------------- 图层合成

def test_layer_order_and_blend():
    # 三层共用一张图集：gid1=红(不透明) gid2=绿(不透明) gid3=蓝(半透明128)
    colors = {1: (200, 0, 0, 255), 2: (0, 200, 0, 255), 3: (0, 0, 200, 128)}
    ts_img = Image(3, 1, [(0, 0, 0, 0)] * 3)
    for gid, c in colors.items():
        ts_img.set(gid - 1, 0, c)
    ts = Tileset(ts_img, 1, 1, 0, 0, 3)
    world = {"layers": [
        {"name": "bottom", "opacity": 1.0, "data": [[1]]},
        {"name": "middle", "opacity": 1.0, "data": [[2]]},
        {"name": "top", "opacity": 1.0, "data": [[3]]},
    ]}
    img = render_map(world, ts, 0, 0, 1, 1)
    r, g, b, a = img.at(0, 0)
    # 上层不透明覆盖下层：中间层完全盖住底层
    assert (r, g, b) != (200, 0, 0)
    # 半透明蓝叠在不透明绿上：是混合值，既不是纯蓝也不是纯绿
    assert (r, g, b) != (0, 0, 200)
    assert (r, g, b) != (0, 200, 0)
    assert b > 90 and g > 90  # 大约 (0, 100, 100)


def test_layer_opacity_configurable():
    ts_img = Image(2, 1, [(200, 0, 0, 255), (0, 0, 200, 255)])
    ts = Tileset(ts_img, 1, 1, 0, 0, 2)
    world = {"layers": [
        {"name": "bottom", "opacity": 1.0, "data": [[1]]},
        {"name": "top", "opacity": 0.5, "data": [[2]]},
    ]}
    img = render_map(world, ts, 0, 0, 1, 1)
    r, g, b, a = img.at(0, 0)
    # 不透明度 0.5 的蓝盖红：约 (100, 0, 100)，与不透明覆盖的纯蓝区分
    assert abs(r - 100) <= 2 and abs(b - 100) <= 2 and g == 0


# ---------------------------------------------------------------- 翻转

def test_flip_four_quadrants():
    # 2x2 瓦片，四个像素互不相同
    # A B
    # C D
    A, B, C, D = (10, 0, 0, 255), (20, 0, 0, 255), (30, 0, 0, 255), (40, 0, 0, 255)
    ts_img = Image(2, 2, [A, B, C, D])
    ts = Tileset(ts_img, 2, 2, 0, 0, 1)

    def render(flag):
        world = {"layers": [{
            "name": "L", "opacity": 1.0, "data": [[1]],
            "flip_flags": [[flag]],
        }]}
        img = render_map(world, ts, 0, 0, 2, 2)
        return [[img.at(x, y) for x in range(2)] for y in range(2)]

    assert render(0) == [[A, B], [C, D]]          # 不翻转
    assert render(1) == [[B, A], [D, C]]          # 水平
    assert render(2) == [[C, D], [A, B]]          # 垂直
    assert render(3) == [[D, C], [B, A]]          # 两者


def test_flip_does_not_shift_position():
    # 瓦片在 (tx=1, ty=0)，翻转后内容仍落在 x∈[2,4) 这一格内
    A, B = (10, 0, 0, 255), (20, 0, 0, 255)
    ts_img = Image(2, 1, [A, B])
    ts = Tileset(ts_img, 2, 1, 0, 0, 1)
    world = {"layers": [{
        "name": "L", "opacity": 1.0,
        "data": [[0, 1]],
        "flip_flags": [[0, 1]],
    }]}
    img = render_map(world, ts, 0, 0, 4, 1)
    assert img.at(0, 0) == (20, 20, 20, 255)      # 空格仍是背景
    assert img.at(2, 0) == B                       # 翻转：左格拿到源右像素
    assert img.at(3, 0) == A


# ---------------------------------------------------------------- 动画

def anim_world():
    return {"layers": [{
        "name": "anim", "opacity": 1.0, "data": [[1]],
        "frames": [[1, 2, 3, 4]], "frame_duration": 0.15,
    }]}


def anim_tileset():
    # 4 个 1x1 瓦片，红绿蓝白
    px = [(100, 0, 0, 255), (0, 100, 0, 255), (0, 0, 100, 255), (200, 200, 200, 255)]
    return Tileset(Image(4, 1, px), 1, 1, 0, 0, 4)


def test_animation_frame_selection():
    ts = anim_tileset()
    world = anim_world()
    frames = [(100, 0, 0, 255), (0, 100, 0, 255), (0, 0, 100, 255), (200, 200, 200, 255)]
    # 4 帧 x 0.15s = 0.6s 一个循环
    for i, t in enumerate([0.0, 0.15, 0.30, 0.45]):
        img = render_map(world, ts, 0, 0, 1, 1, time_s=t)
        assert img.at(0, 0) == frames[i]
    # 循环回到第一帧
    img = render_map(world, ts, 0, 0, 1, 1, time_s=0.60)
    assert img.at(0, 0) == frames[0]
    img = render_map(world, ts, 0, 0, 1, 1, time_s=0.75)
    assert img.at(0, 0) == frames[1]


def test_animation_deterministic():
    ts = anim_tileset()
    world = anim_world()
    a = render_map(world, ts, 0, 0, 1, 1, time_s=0.31)
    b = render_map(world, ts, 0, 0, 1, 1, time_s=0.31)
    assert a.pixels == b.pixels


# ---------------------------------------------------------------- 视野裁剪

def view_world(cols, rows):
    return {"layers": [{
        "name": "L", "opacity": 1.0,
        "data": [[1] * cols for _ in range(rows)],
    }]}


def test_view_clips_edge_tiles():
    # 4x4 瓦片，像素值 = 瓦片内 x 坐标（便于验证裁剪而非平移）
    tile = 4
    ts_img = Image(tile, tile,
                   [(px, 0, 0, 255) for py in range(tile) for px in range(tile)])
    ts = Tileset(ts_img, tile, tile, 0, 0, 1)
    world = view_world(4, 4)
    # 视野起点 x=2，不是瓦片整数倍：左边第一列瓦片只露右半
    img = render_map(world, ts, 2, 0, 8, 4)
    # 结果最左列应是源瓦片 px=2 的像素，而不是整体平移后的 px=0
    assert img.at(0, 0) == (2, 0, 0, 255)
    assert img.at(1, 0) == (3, 0, 0, 255)
    # 第二列瓦片从 dst x=2 开始，是下一块瓦片的 px=0
    assert img.at(2, 0) == (0, 0, 0, 255)


def test_view_excludes_outside_tiles():
    # 两块瓦片颜色不同，视野只覆盖第一块
    row = [(10, 0, 0, 255)] * 2 + [(250, 0, 0, 255)] * 2
    ts_img = Image(4, 2, row * 2)
    ts = Tileset(ts_img, 2, 2, 0, 0, 2)
    world = {"layers": [{
        "name": "L", "opacity": 1.0, "data": [[1, 2]],
    }]}
    img = render_map(world, ts, 0, 0, 2, 2)
    for y in range(2):
        for x in range(2):
            assert img.at(x, y) == (10, 0, 0, 255)


def test_view_beyond_map_keeps_background():
    ts_img = Image(2, 2, [(10, 0, 0, 255)] * 4)
    ts = Tileset(ts_img, 2, 2, 0, 0, 1)
    world = view_world(1, 1)
    img = render_map(world, ts, 0, 0, 4, 4)
    assert img.at(0, 0) == (10, 0, 0, 255)
    # 地图外的区域保持背景色，不崩溃也不重复画瓦片
    assert img.at(3, 3) == (20, 20, 20, 255)
    assert img.at(2, 0) == (20, 20, 20, 255)
