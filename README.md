# 瓦片地图渲染

骨架能读图集与地图、能按索引取瓦片、能出 PNG，但只画了最底下那一层。

## 已知缺口

- `render_map` 只读 `layers[0]`，地面之上的装饰层与动画层完全没画。
- 图集取块没扣 margin 与 spacing，第 2 列之后的瓦片全部错位，取到间隔像素。
- `flip_flags` 被忽略，装饰层里水平翻转与垂直翻转的瓦片画反。
- 动画层有 4 帧与 0.15 秒帧时长，但没有按时间选帧。
- 视野裁剪靠写入时钳制，越界的瓦片仍然逐像素遍历，视野外的图块被白白算了。
- 空瓦片（gid 为 0）跳过，但半透明装饰瓦片的 alpha 没有做混合，直接覆盖。

## 运行

```
python gen_samples.py
python -m tilemap.cli data/map.json --tileset data/tileset.png --view 0,0,256,192 --out tilemap.png
python -m pytest tests -q
```

图集 8x8 个 32x32 瓦片，带 2 像素边距和 2 像素间隔；地图 24x16 块，三层：地面、装饰、动画。
装饰层带水平与垂直翻转标记，动画层有 4 帧。
