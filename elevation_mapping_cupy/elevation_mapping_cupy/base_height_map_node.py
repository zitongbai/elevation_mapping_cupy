from typing import Tuple

import numpy as np
import rclpy
from grid_map_msgs.msg import GridMap
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import Float32MultiArray
from std_msgs.msg import MultiArrayDimension as MAD
from std_msgs.msg import MultiArrayLayout as MAL
from tf_transformations import quaternion_matrix
import tf2_ros

from elevation_mapping_cupy.gridmap_utils import decode_multiarray_to_rows_cols


def compute_output_shape(x_min: float, x_max: float, y_min: float, y_max: float, resolution: float) -> Tuple[int, int]:
    if resolution <= 0.0:
        raise ValueError("resolution must be positive")
    if x_max <= x_min:
        raise ValueError("x_max must be greater than x_min")
    if y_max <= y_min:
        raise ValueError("y_max must be greater than y_min")
    rows = int(round((x_max - x_min) / resolution))
    cols = int(round((y_max - y_min) / resolution))
    if rows <= 0 or cols <= 0:
        raise ValueError("output shape must be non-empty")
    return rows, cols


def make_base_grid(
    rows: int,
    cols: int,
    resolution: float,
    x_max: float,
    y_max: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return base-frame grid coordinates with row->-base_x and col->-base_y."""
    row_idx = np.arange(rows, dtype=np.float32)
    col_idx = np.arange(cols, dtype=np.float32)
    x_base = x_max - row_idx * resolution
    y_base = y_max - col_idx * resolution
    return np.meshgrid(x_base, y_base, indexing="ij")


def grid_map_xy_to_indices(
    x: np.ndarray,
    y: np.ndarray,
    center_x: float,
    center_y: float,
    resolution: float,
    rows: int,
    cols: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Convert map-frame x/y into GridMap row/col indices.

    Published GridMap arrays use row->-map_x and col->-map_y.
    """
    row = np.rint((center_x - x) / resolution + (rows - 1) / 2.0).astype(np.int64)
    col = np.rint((center_y - y) / resolution + (cols - 1) / 2.0).astype(np.int64)
    return row, col


def encode_base_multiarray(array: np.ndarray) -> Float32MultiArray:
    arr = np.asarray(array, dtype=np.float32)
    rows, cols = arr.shape
    msg = Float32MultiArray()
    msg.layout = MAL()
    msg.layout.dim.append(MAD(label="base_x_index", size=rows, stride=rows * cols))
    msg.layout.dim.append(MAD(label="base_y_index", size=cols, stride=cols))
    msg.data = arr.flatten(order="C").tolist()
    return msg


def resample_layer_to_base(
    source_layer: np.ndarray,
    source_resolution: float,
    source_center_x: float,
    source_center_y: float,
    transform_matrix: np.ndarray,
    output_rows: int,
    output_cols: int,
    output_resolution: float,
    x_max: float,
    y_max: float,
    unknown_value: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Nearest-neighbor resample from source GridMap convention into base coordinates."""
    x_base, y_base = make_base_grid(output_rows, output_cols, output_resolution, x_max, y_max)
    x_odom = transform_matrix[0, 0] * x_base + transform_matrix[0, 1] * y_base + transform_matrix[0, 3]
    y_odom = transform_matrix[1, 0] * x_base + transform_matrix[1, 1] * y_base + transform_matrix[1, 3]

    src_rows, src_cols = source_layer.shape
    src_row, src_col = grid_map_xy_to_indices(
        x_odom,
        y_odom,
        source_center_x,
        source_center_y,
        source_resolution,
        src_rows,
        src_cols,
    )

    valid = (src_row >= 0) & (src_row < src_rows) & (src_col >= 0) & (src_col < src_cols)
    out = np.full((output_rows, output_cols), unknown_value, dtype=np.float32)
    valid_mask = np.zeros((output_rows, output_cols), dtype=np.float32)

    sampled = np.full((output_rows, output_cols), np.nan, dtype=np.float32)
    sampled[valid] = source_layer[src_row[valid], src_col[valid]]
    finite = np.isfinite(sampled)
    out[finite] = sampled[finite]
    valid_mask[finite] = 1.0
    return out, valid_mask


class BaseHeightMapNode(Node):
    def __init__(self):
        super().__init__("base_height_map_node")

        self.declare_parameter("input_topic", "/elevation_mapping_node/elevation_map_filter")
        self.declare_parameter("output_topic", "/elevation_mapping_node/base_height_map")
        self.declare_parameter("valid_output_topic", "/elevation_mapping_node/base_height_map_valid")
        self.declare_parameter("input_layer", "inpaint")
        self.declare_parameter("source_frame", "odom")
        self.declare_parameter("target_frame", "base")
        self.declare_parameter("resolution", 0.1)
        self.declare_parameter("x_min", -2.0)
        self.declare_parameter("x_max", 6.0)
        self.declare_parameter("y_min", -3.0)
        self.declare_parameter("y_max", 3.0)
        self.declare_parameter("publish_rate", 10.0)
        self.declare_parameter("unknown_value", float("nan"))
        self.declare_parameter("interpolation", "nearest")
        self.declare_parameter("use_latest_tf", True)
        self.declare_parameter("tf_timeout", 0.05)

        self.input_topic = self.get_parameter("input_topic").value
        self.output_topic = self.get_parameter("output_topic").value
        self.valid_output_topic = self.get_parameter("valid_output_topic").value
        self.input_layer = self.get_parameter("input_layer").value
        self.source_frame = self.get_parameter("source_frame").value
        self.target_frame = self.get_parameter("target_frame").value
        self.resolution = float(self.get_parameter("resolution").value)
        self.x_min = float(self.get_parameter("x_min").value)
        self.x_max = float(self.get_parameter("x_max").value)
        self.y_min = float(self.get_parameter("y_min").value)
        self.y_max = float(self.get_parameter("y_max").value)
        self.publish_rate = float(self.get_parameter("publish_rate").value)
        self.unknown_value = float(self.get_parameter("unknown_value").value)
        self.interpolation = self.get_parameter("interpolation").value
        self.use_latest_tf = bool(self.get_parameter("use_latest_tf").value)
        self.tf_timeout = float(self.get_parameter("tf_timeout").value)

        if self.interpolation != "nearest":
            raise ValueError("Only interpolation='nearest' is currently supported")
        self.rows, self.cols = compute_output_shape(self.x_min, self.x_max, self.y_min, self.y_max, self.resolution)

        self._tf_buffer = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(self._tf_buffer, self)
        self._last_grid_map = None

        self._height_pub = self.create_publisher(Float32MultiArray, self.output_topic, 10)
        self._valid_pub = self.create_publisher(Float32MultiArray, self.valid_output_topic, 10)
        self._grid_sub = self.create_subscription(GridMap, self.input_topic, self._on_grid_map, 10)

        if self.publish_rate > 0.0:
            self._timer = self.create_timer(1.0 / self.publish_rate, self._publish_latest)
        else:
            self._timer = None

    def _on_grid_map(self, msg: GridMap) -> None:
        self._last_grid_map = msg
        if self._timer is None:
            self._publish_from_msg(msg)

    def _publish_latest(self) -> None:
        if self._last_grid_map is None:
            return
        self._publish_from_msg(self._last_grid_map)

    def _lookup_transform_matrix(self, msg: GridMap):
        source_frame = self.source_frame or msg.header.frame_id
        if not source_frame:
            self.get_logger().warning("No source_frame configured and GridMap header.frame_id is empty")
            return None
        stamp = Time() if self.use_latest_tf else Time.from_msg(msg.header.stamp)
        try:
            transform = self._tf_buffer.lookup_transform(
                source_frame,
                self.target_frame,
                stamp,
                timeout=Duration(seconds=self.tf_timeout),
            )
        except Exception as exc:
            self.get_logger().warning(
                f"Transform from '{self.target_frame}' to '{source_frame}' not available: {exc}",
                throttle_duration_sec=5.0,
            )
            return None

        t = transform.transform.translation
        q = transform.transform.rotation
        matrix = quaternion_matrix([q.x, q.y, q.z, q.w]).astype(np.float32)
        matrix[0, 3] = t.x
        matrix[1, 3] = t.y
        matrix[2, 3] = t.z
        return matrix

    def _publish_from_msg(self, msg: GridMap) -> None:
        if self.input_layer not in msg.layers:
            self.get_logger().warning(
                f"Layer '{self.input_layer}' not found in GridMap layers={list(msg.layers)}",
                throttle_duration_sec=5.0,
            )
            return

        transform_matrix = self._lookup_transform_matrix(msg)
        if transform_matrix is None:
            return

        layer_idx = msg.layers.index(self.input_layer)
        source_layer = decode_multiarray_to_rows_cols(self.input_layer, msg.data[layer_idx])
        height_map, valid_mask = resample_layer_to_base(
            source_layer=source_layer,
            source_resolution=float(msg.info.resolution),
            source_center_x=float(msg.info.pose.position.x),
            source_center_y=float(msg.info.pose.position.y),
            transform_matrix=transform_matrix,
            output_rows=self.rows,
            output_cols=self.cols,
            output_resolution=self.resolution,
            x_max=self.x_max,
            y_max=self.y_max,
            unknown_value=self.unknown_value,
        )

        self._height_pub.publish(encode_base_multiarray(height_map))
        self._valid_pub.publish(encode_base_multiarray(valid_mask))


def main(args=None):
    rclpy.init(args=args)
    node = BaseHeightMapNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
