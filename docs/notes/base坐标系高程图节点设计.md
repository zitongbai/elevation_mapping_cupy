# base 坐标系高程图节点设计

本文记录新增 `base_height_map_node` 的设计目标、数据流、坐标约定和实现细节。

## 设计目标

原始 `/elevation_mapping_node/elevation_map_filter` 是 `odom` 对齐的 rolling map：

```text
中心随机器人位置移动
方向始终对齐 odom
不会随机器人 yaw 旋转
```

这对建图和 RViz 检查是合理的，但对某些下游任务不方便，例如：

- 机器人局部规划
- 足端落脚点选择
- 控制器局部地形输入
- 学习模型输入

这些任务通常希望输入固定在机器人自身坐标系下：

```text
中心: base
方向: 跟随机器人朝向
x: 机器人前后
y: 机器人左右
```

因此新增一个后处理节点：

```text
输入:  odom 对齐的 GridMap
输出:  base 对齐的 Float32MultiArray
```

## 为什么不能只改 frame_id

不能简单把原始 GridMap 的 `frame_id` 从 `odom` 改成 `base`。

原因是原始数组的行列方向仍然是 `odom` 对齐的：

```text
row -> -odom_x
col -> -odom_y
```

如果只改 header，下游会误以为数组已经跟随机器人旋转，但实际数据没有旋转，坐标语义会错误。

正确做法是重采样：

```text
对输出 base 图中的每个 cell:
  1. 计算该 cell 在 base 下的 (x_base, y_base)
  2. 用 TF 转到 odom 下的 (x_odom, y_odom)
  3. 在原始 GridMap 中查找对应高度
  4. 写入输出 Float32MultiArray
```

公式形式：

```text
p_odom = T_odom_base * p_base
```

## 节点输入输出

新增节点：

```text
base_height_map_node.py
```

输入：

```text
topic: /elevation_mapping_node/elevation_map_filter
type:  grid_map_msgs/msg/GridMap
layer: inpaint
```

TF：

```text
source_frame -> target_frame
默认: odom -> base
```

输出高程图：

```text
topic: /elevation_mapping_node/base_height_map
type:  std_msgs/msg/Float32MultiArray
```

输出有效性 mask：

```text
topic: /elevation_mapping_node/base_height_map_valid
type:  std_msgs/msg/Float32MultiArray
```

mask 约定：

```text
1.0 = 有效采样
0.0 = 越界或源数据为 NaN
```

## 输出矩阵坐标约定

假设 `base` 使用 ROS 常规定义：

```text
base_x: 前方
base_y: 左方
base_z: 上方
```

输出矩阵 `height_map[row, col]` 定义为：

```text
row 增大 -> base_x 减小
col 增大 -> base_y 减小
```

因此：

```text
row = 0        -> 机器人前方
row = rows-1   -> 机器人后方

col = 0        -> 机器人左侧
col = cols-1   -> 机器人右侧
```

四个角的含义：

```text
height_map[0, 0]                 前左
height_map[0, cols-1]            前右
height_map[rows-1, 0]            后左
height_map[rows-1, cols-1]       后右
```

坐标公式：

```python
x_base = x_max - row * resolution
y_base = y_max - col * resolution
```

如果配置为：

```yaml
resolution: 0.1
x_min: -2.0
x_max: 6.0
y_min: -3.0
y_max: 3.0
```

则输出尺寸为：

```text
rows = round((x_max - x_min) / resolution) = 80
cols = round((y_max - y_min) / resolution) = 60
```

矩阵覆盖：

```text
前方 6m
后方 2m
左侧 3m
右侧 3m
```

## Float32MultiArray layout

输出高度图和 mask 都使用普通 row-major 编码：

```python
msg.data = array.astype(np.float32).flatten(order="C")
```

layout：

```text
dim[0].label = "base_x_index"
dim[0].size = rows
dim[0].stride = rows * cols

dim[1].label = "base_y_index"
dim[1].size = cols
dim[1].stride = cols
```

下游还原方式：

```python
rows = msg.layout.dim[0].size
cols = msg.layout.dim[1].size
height_map = np.array(msg.data, dtype=np.float32).reshape((rows, cols), order="C")
```

## 高度值的参考

需要特别注意：输出矩阵的 XY 是 `base` 坐标系，但高度值当前仍是从原始 GridMap 直接采样出来的高度。

也就是说：

```text
输出数组的 x/y: base 坐标系
输出数组的 z:   原始 odom/map frame 下的高度值
```

每个元素可以理解为：

```text
在 base 坐标下某个 (x_base, y_base) 位置，
映射到 odom 后对应地面点的 odom_z 高度。
```

当前实现没有把高度转换成相对 `base_z` 的高度。

如果下游希望使用相对机器人高度，例如：

```text
z_relative = 地面高度 - 当前 base 高度
```

则应在节点中增加一个可选参数，在采样后减掉 `odom -> base` 的 `translation.z`：

```python
height_map = sampled_odom_height - base_z_in_odom
```

目前默认保持原始高度，是为了不改变 `elevation_mapping_cupy` 原始高程语义。

## 重采样细节

当前实现使用最近邻采样。

对输出的每个 cell：

```python
x_base = x_max - row * resolution
y_base = y_max - col * resolution
```

通过 TF 得到：

```python
x_odom, y_odom = T_odom_base @ [x_base, y_base, 0, 1]
```

再按原始 GridMap 的行列约定查源索引：

```python
src_row = round((center_x - x_odom) / source_resolution + (src_rows - 1) / 2)
src_col = round((center_y - y_odom) / source_resolution + (src_cols - 1) / 2)
```

有效条件：

```text
0 <= src_row < src_rows
0 <= src_col < src_cols
source_layer[src_row, src_col] 是 finite
```

如果无效：

```text
height_map[row, col] = unknown_value
valid_mask[row, col] = 0.0
```

如果有效：

```text
height_map[row, col] = source_layer[src_row, src_col]
valid_mask[row, col] = 1.0
```

## 为什么发布 mask

`Float32MultiArray` 不带 header、frame、layer、validity 等语义字段。单独发布高度图时，下游只能通过 NaN 或特殊值判断无效区域。

发布 mask 的好处：

- 明确区分有效采样和无效采样
- 支持 `unknown_value` 不是 NaN 的情况
- 方便下游规划器、控制器或模型过滤未知区域
- 避免把越界区域误当成可靠地形
