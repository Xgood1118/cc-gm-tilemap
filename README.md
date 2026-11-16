# 瓦片地图渲染

纯标准库的多层瓦片地图渲染器：读 PNG 图集与 JSON 地图，按视野合成三层（地面、装饰、动画），输出 PNG。

## 功能

- **图集取块**：`Tileset.tile_rect` 按 margin 与 spacing 定位瓦片，最后一列/最后一行不错位；索引越界抛 `IndexError`，不会读到别的瓦片。
- **图层**：`render_map` 按 `layers` 顺序合成，上层 source-over 混合到下层；每层 `opacity` 可配置，半透明瓦片与不透明覆盖结果可区分。
- **翻转**：`flip_flags` 按位解释（1=水平，2=垂直，3=两者），翻转在瓦片内部进行，位置不偏移。
- **动画**：图层带 `frames`（帧序列，值为 gid）与 `frame_duration` 时，数据里的非零 gid 选中第 `(gid-1) % len(frames)` 组序列，帧下标为 `floor(time_s / frame_duration) % 帧数`；帧数 × 帧时长 = 一个循环，同一时刻多次渲染结果一致。
- **视野**：只遍历与视野相交的瓦片；视野起点不对齐瓦片时，边缘瓦片按像素裁剪而不是整体平移；地图外区域保持背景色。

## 运行

```
python gen_samples.py
python -m tilemap.cli data/map.json --tileset data/tileset.png --view 0,0,256,192 --out tilemap.png
python -m pytest tests -q
```

图集 8x8 个 32x32 瓦片，带 2 像素边距和 2 像素间隔；地图 24x16 块，三层：地面、装饰、动画。
装饰层带水平与垂直翻转标记，动画层有 4 帧、帧时长 0.15 秒。

## 渲染统计

`python -m tilemap.cli data/map.json --tileset data/tileset.png --view 0,0,256,192 --out tilemap.png`（time_s=0）：

| 层 | 视野内非透明像素数 |
|---|---|
| ground | 49152 |
| decor | 2048 |
| anim | 1024 |

- 视野内翻转瓦片数：2（decor 层，flip_flags 非零且该格有瓦片）
- 动画层 t=0 选中帧：第 0 帧，gid 1
