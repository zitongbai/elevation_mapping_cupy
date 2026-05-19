# base 高程图运行与参数配置

本文说明如何运行新增的 base 坐标系高程图节点，以及各参数的含义和建议设置。

## 默认运行方式

新增节点已经集成到 Go2 MID360 launch 中。

默认启动：

```bash
ros2 launch elevation_mapping_cupy go2_mid360.launch.py \
  robot_config:=go2/dual_lidar.yaml \
  launch_rviz:=true
```

默认会同时启动：

```text
elevation_mapping_node
base_height_map_node
rviz2
```

如果只想启动原始建图，不启动 base 高程图节点：

```bash
ros2 launch elevation_mapping_cupy go2_mid360.launch.py \
  robot_config:=go2/dual_lidar.yaml \
  launch_rviz:=true \
  launch_base_height_map:=false
```

## 输出 topic

高程图：

```text
/elevation_mapping_node/base_height_map
```

类型：

```text
std_msgs/msg/Float32MultiArray
```

有效性 mask：

```text
/elevation_mapping_node/base_height_map_valid
```

类型：

```text
std_msgs/msg/Float32MultiArray
```

检查 topic：

```bash
ros2 topic info /elevation_mapping_node/base_height_map
ros2 topic info /elevation_mapping_node/base_height_map_valid
```

查看一帧数据：

```bash
ros2 topic echo /elevation_mapping_node/base_height_map --once
ros2 topic echo /elevation_mapping_node/base_height_map_valid --once
```

## 默认配置文件

默认参数文件：

```text
elevation_mapping_cupy/config/setups/go2/base_height_map.yaml
```

launch 参数：

```text
base_height_map_config:=go2/base_height_map.yaml
```

可以指定其他配置文件：

```bash
ros2 launch elevation_mapping_cupy go2_mid360.launch.py \
  robot_config:=go2/dual_lidar.yaml \
  base_height_map_config:=go2/my_base_height_map.yaml
```

## 默认参数

当前默认配置：

```yaml
/base_height_map_node:
  ros__parameters:
    input_topic: "/elevation_mapping_node/elevation_map_filter"
    output_topic: "/elevation_mapping_node/base_height_map"
    valid_output_topic: "/elevation_mapping_node/base_height_map_valid"
    input_layer: "inpaint"

    source_frame: "odom"
    target_frame: "base"

    resolution: 0.1
    x_min: -2.0
    x_max: 6.0
    y_min: -3.0
    y_max: 3.0

    publish_rate: 10.0
    unknown_value: .nan
    interpolation: "nearest"
    use_latest_tf: true
    tf_timeout: 0.05
```

## 参数说明

### 输入输出参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `input_topic` | `/elevation_mapping_node/elevation_map_filter` | 原始 GridMap 输入 |
| `output_topic` | `/elevation_mapping_node/base_height_map` | base 高程图输出 |
| `valid_output_topic` | `/elevation_mapping_node/base_height_map_valid` | 有效性 mask 输出 |
| `input_layer` | `inpaint` | 从 GridMap 中采样的 layer |

常用 `input_layer` 选择：

| Layer | 适用场景 |
| --- | --- |
| `inpaint` | 默认推荐，连续性较好，适合局部规划或模型输入 |
| `despiked` | 不希望补洞虚构高度时使用 |
| `smooth` | 需要平滑可视化或低噪声输入时使用 |
| `elevation` | 想看原始融合高度时使用 |

### 坐标系参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `source_frame` | `odom` | 原始 GridMap 所在参考系 |
| `target_frame` | `base` | 输出高程图的参考系 |

节点会查询：

```text
source_frame -> target_frame
```

默认即：

```text
odom -> base
```

如果机器人实际 TF 中底盘 frame 不是 `base`，需要改成实际 frame，例如：

```yaml
target_frame: "base_link"
```

### 输出范围参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `resolution` | `0.1` | 输出栅格分辨率，单位 m/cell |
| `x_min` | `-2.0` | base_x 后方边界 |
| `x_max` | `6.0` | base_x 前方边界 |
| `y_min` | `-3.0` | base_y 右侧边界 |
| `y_max` | `3.0` | base_y 左侧边界 |

输出尺寸：

```python
rows = round((x_max - x_min) / resolution)
cols = round((y_max - y_min) / resolution)
```

默认输出：

```text
80 x 60
```

覆盖范围：

```text
前方 6m
后方 2m
左侧 3m
右侧 3m
```

如果只需要更小局部窗口，例如前方 3m、后方 1m、左右 2m：

```yaml
resolution: 0.1
x_min: -1.0
x_max: 3.0
y_min: -2.0
y_max: 2.0
```

输出尺寸：

```text
40 x 40
```

### 发布和 TF 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `publish_rate` | `10.0` | 输出发布频率 |
| `use_latest_tf` | `true` | 使用最新 TF 进行重采样 |
| `tf_timeout` | `0.05` | TF 查询超时时间，单位秒 |

如果 `publish_rate > 0`，节点会按固定频率发布最新输入图重采样结果。

如果 `publish_rate <= 0`，节点会在收到每帧输入 GridMap 时发布一次。

`use_latest_tf: true` 的含义：

```text
使用最新 odom -> base TF
即使原始 GridMap 频率较低，输出图也能更及时跟随机器人姿态
```

如果需要严格按输入 GridMap 时间戳对齐 TF，可设置：

```yaml
use_latest_tf: false
```

但这要求 TF buffer 中有对应时间戳的变换，否则可能出现查询失败。

### 采样和未知值参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `interpolation` | `nearest` | 当前只支持最近邻采样 |
| `unknown_value` | `.nan` | 越界或无效采样时写入的高度值 |

当前初版只实现：

```yaml
interpolation: "nearest"
```

如果设置其他值，节点会直接报错，避免用户误以为已经使用双线性插值。

## 下游读取示例

Python 下游节点中还原高度图：

```python
import numpy as np

def on_height_map(msg):
    rows = msg.layout.dim[0].size
    cols = msg.layout.dim[1].size
    height_map = np.array(msg.data, dtype=np.float32).reshape((rows, cols), order="C")

    # height_map[row, col]
    # row 增大 -> base_x 减小
    # col 增大 -> base_y 减小
```

还原 mask：

```python
def on_valid_mask(msg):
    rows = msg.layout.dim[0].size
    cols = msg.layout.dim[1].size
    valid = np.array(msg.data, dtype=np.float32).reshape((rows, cols), order="C")

    # valid == 1.0 有效
    # valid == 0.0 无效
```

根据行列计算 base 坐标：

```python
x_base = x_max - row * resolution
y_base = y_max - col * resolution
```

使用默认参数时：

```python
resolution = 0.1
x_max = 6.0
y_max = 3.0

x_base = 6.0 - row * 0.1
y_base = 3.0 - col * 0.1
```

## 常见问题

### 输出数据的 XY 是什么参考系

输出 `base_height_map` 的 XY 是 `base` 坐标系：

```text
row/col 会随机器人朝向改变
```

这和原始 `/elevation_mapping_node/elevation_map_filter` 不同。原始图的 row/col 始终对齐 `odom`。

### 输出高度值是不是 base 坐标系下的 z

当前不是。

当前高度值仍是原始 GridMap 中的高度，即 `odom`/map frame 下的高度值。

也就是说：

```text
XY: base
Z:  odom/map height
```

如果需要相对机器人高度，需要后续增加参数，例如：

```yaml
height_reference: "base"
```

并在采样后执行：

```python
height_map = height_map - base_z_in_odom
```

### 为什么输出不用 GridMap

设计上故意输出 `Float32MultiArray`：

- 减少下游节点对 `grid_map_msgs/msg/GridMap` 的依赖
- 下游直接拿二维 float 数组更简单
- base 局部图尺寸较小，不需要完整 GridMap 元信息

代价是 `Float32MultiArray` 没有 header、frame_id、stamp、resolution 等字段，因此这些语义必须由 YAML 参数和 `layout.dim` 约定共同确定。

### 如果看不到输出怎么办

优先检查：

```bash
ros2 topic list | grep base_height
ros2 topic info /elevation_mapping_node/elevation_map_filter
ros2 topic echo /elevation_mapping_node/elevation_map_filter --once
ros2 run tf2_ros tf2_echo odom base
```

常见原因：

- 原始 GridMap 没有发布
- `input_layer` 不存在
- `odom -> base` TF 不可用
- `target_frame` 配错，应使用 `base_link` 或其他实际 frame
- 输出范围落在原始 rolling map 之外，导致 mask 大量为 0
