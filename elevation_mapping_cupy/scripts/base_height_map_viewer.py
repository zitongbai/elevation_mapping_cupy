#!/usr/bin/env python3

import math
import sys
import time
from typing import Optional

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from std_msgs.msg import Float32MultiArray

try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit(
        "matplotlib is required for base_height_map_viewer.py. "
        "Install it with: sudo apt install python3-matplotlib"
    ) from exc


def _finite_or_none(value: float) -> Optional[float]:
    return value if math.isfinite(value) else None


def decode_float32_multiarray(name: str, msg: Float32MultiArray) -> np.ndarray:
    data = np.asarray(msg.data, dtype=np.float32)
    dims = msg.layout.dim

    if len(dims) >= 2 and dims[0].label and dims[1].label:
        label0 = dims[0].label
        label1 = dims[1].label

        if label0 in ("base_x_index", "row_index") and label1 in ("base_y_index", "column_index"):
            rows = dims[0].size
            cols = dims[1].size
            if rows * cols != data.size:
                raise ValueError(f"{name} layout says {rows}x{cols}, but data has {data.size} values")
            return data.reshape((rows, cols), order="C")

        if label0 == "column_index" and label1 == "row_index":
            cols = dims[0].size
            rows = dims[1].size
            if rows * cols != data.size:
                raise ValueError(f"{name} layout says {rows}x{cols}, but data has {data.size} values")
            return data.reshape((rows, cols), order="F")

    if len(dims) >= 2:
        rows = dims[0].size
        cols = dims[1].size
        if rows * cols == data.size:
            return data.reshape((rows, cols), order="C")

    side = int(math.sqrt(data.size))
    if side * side == data.size:
        return data.reshape((side, side), order="C")

    raise ValueError(f"{name} does not contain enough layout metadata to infer a 2D shape")


class BaseHeightMapViewer(Node):
    def __init__(self):
        super().__init__("base_height_map_viewer")

        self.declare_parameter("height_topic", "/elevation_mapping_node/base_height_map")
        self.declare_parameter("valid_topic", "/elevation_mapping_node/base_height_map_valid")
        self.declare_parameter("update_rate", 30.0)
        self.declare_parameter("colormap", "viridis")
        self.declare_parameter("mask_invalid", True)
        self.declare_parameter("show_valid", True)
        self.declare_parameter("vmin", 0.0)
        self.declare_parameter("vmax", 0.4)

        self.height_topic = self.get_parameter("height_topic").value
        self.valid_topic = self.get_parameter("valid_topic").value
        self.update_rate = float(self.get_parameter("update_rate").value)
        self.colormap = self.get_parameter("colormap").value
        self.mask_invalid = bool(self.get_parameter("mask_invalid").value)
        self.show_valid = bool(self.get_parameter("show_valid").value)
        self.vmin = _finite_or_none(float(self.get_parameter("vmin").value))
        self.vmax = _finite_or_none(float(self.get_parameter("vmax").value))

        self.height_map = None
        self.valid_mask = None
        self._fig = None
        self._height_ax = None
        self._valid_ax = None
        self._height_image = None
        self._valid_image = None
        self._last_draw_time = 0.0

        latest_only_qos = QoSProfile(depth=1)
        self.create_subscription(Float32MultiArray, self.height_topic, self._on_height_map, latest_only_qos)
        self.create_subscription(Float32MultiArray, self.valid_topic, self._on_valid_mask, latest_only_qos)

        self.get_logger().info(f"Subscribed to height map: {self.height_topic}")
        self.get_logger().info(f"Subscribed to valid mask: {self.valid_topic}")

    def _on_height_map(self, msg: Float32MultiArray) -> None:
        try:
            self.height_map = decode_float32_multiarray("height map", msg)
        except ValueError as exc:
            self.get_logger().warning(str(exc), throttle_duration_sec=2.0)

    def _on_valid_mask(self, msg: Float32MultiArray) -> None:
        try:
            self.valid_mask = decode_float32_multiarray("valid mask", msg)
        except ValueError as exc:
            self.get_logger().warning(str(exc), throttle_duration_sec=2.0)

    def maybe_update_plot(self) -> None:
        if self.height_map is None:
            return

        now = time.monotonic()
        min_period = 1.0 / self.update_rate if self.update_rate > 0.0 else 0.0
        if now - self._last_draw_time < min_period:
            return

        display_height = self._make_display_height()
        if display_height is None:
            return

        if self._fig is None:
            self._create_plot(display_height)
        else:
            self._update_plot(display_height)

        self._last_draw_time = now

    def _make_display_height(self):
        height = self.height_map
        if self.valid_mask is None or not self.mask_invalid:
            return np.ma.masked_invalid(height)

        if self.valid_mask.shape != height.shape:
            self.get_logger().warning(
                f"height map shape {height.shape} does not match valid mask shape {self.valid_mask.shape}",
                throttle_duration_sec=2.0,
            )
            return None

        return np.ma.masked_where(self.valid_mask <= 0.5, height)

    def _create_plot(self, display_height) -> None:
        plt.ion()

        if self.show_valid:
            self._fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
            self._height_ax = axes[0]
            self._valid_ax = axes[1]
        else:
            self._fig, self._height_ax = plt.subplots(1, 1, figsize=(7, 5), constrained_layout=True)

        cmap = plt.get_cmap(self.colormap).copy()
        cmap.set_bad(color="lightgray")

        self._height_image = self._height_ax.imshow(
            display_height,
            origin="upper",
            interpolation="nearest",
            cmap=cmap,
            vmin=self.vmin,
            vmax=self.vmax,
        )
        self._height_ax.set_title("Base Height Map")
        self._height_ax.set_xlabel("base_y_index")
        self._height_ax.set_ylabel("base_x_index")
        self._fig.colorbar(self._height_image, ax=self._height_ax, label="height")

        if self.show_valid:
            valid = self._valid_for_display(display_height.shape)
            self._valid_image = self._valid_ax.imshow(
                valid,
                origin="upper",
                interpolation="nearest",
                cmap="gray",
                vmin=0.0,
                vmax=1.0,
            )
            self._valid_ax.set_title("Valid Mask")
            self._valid_ax.set_xlabel("base_y_index")
            self._valid_ax.set_ylabel("base_x_index")

        self._fig.canvas.draw_idle()
        self._fig.canvas.flush_events()

    def _update_plot(self, display_height) -> None:
        self._height_image.set_data(display_height)
        if self.vmin is None and self.vmax is None:
            self._height_image.autoscale()

        if self.show_valid and self._valid_image is not None:
            self._valid_image.set_data(self._valid_for_display(display_height.shape))

        self._fig.canvas.draw_idle()
        self._fig.canvas.flush_events()

    def _valid_for_display(self, shape):
        if self.valid_mask is None or self.valid_mask.shape != shape:
            return np.zeros(shape, dtype=np.float32)
        return self.valid_mask

    @property
    def plot_is_open(self) -> bool:
        return self._fig is None or plt.fignum_exists(self._fig.number)


def main(args=None):
    rclpy.init(args=args)
    node = BaseHeightMapViewer()

    try:
        while rclpy.ok() and node.plot_is_open:
            rclpy.spin_once(node, timeout_sec=0.01)
            node.maybe_update_plot()
            plt.pause(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        plt.close("all")


if __name__ == "__main__":
    main(sys.argv)
