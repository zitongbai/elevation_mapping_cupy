import numpy as np

from elevation_mapping_cupy.base_height_map_node import (
    compute_output_shape,
    encode_base_multiarray,
    grid_map_xy_to_indices,
    make_base_grid,
    resample_layer_to_base,
)


def test_base_grid_row_col_direction():
    rows, cols = compute_output_shape(-1.0, 1.0, -2.0, 2.0, 1.0)

    x_base, y_base = make_base_grid(rows, cols, resolution=1.0, x_max=1.0, y_max=2.0)

    assert rows == 2
    assert cols == 4
    assert np.array_equal(x_base[:, 0], np.array([1.0, 0.0], dtype=np.float32))
    assert np.array_equal(y_base[0, :], np.array([2.0, 1.0, 0.0, -1.0], dtype=np.float32))


def test_grid_map_xy_to_indices_uses_gridmap_direction():
    x = np.array([[0.0, 1.0, -1.0]], dtype=np.float32)
    y = np.array([[0.0, 1.0, -1.0]], dtype=np.float32)

    row, col = grid_map_xy_to_indices(x, y, 0.0, 0.0, 1.0, rows=5, cols=5)

    assert np.array_equal(row, np.array([[2, 1, 3]]))
    assert np.array_equal(col, np.array([[2, 1, 3]]))


def test_resample_identity_transform_samples_centered_crop():
    source = np.arange(49, dtype=np.float32).reshape((7, 7))
    transform = np.eye(4, dtype=np.float32)

    out, valid = resample_layer_to_base(
        source_layer=source,
        source_resolution=1.0,
        source_center_x=0.0,
        source_center_y=0.0,
        transform_matrix=transform,
        output_rows=3,
        output_cols=3,
        output_resolution=1.0,
        x_max=1.0,
        y_max=1.0,
        unknown_value=np.nan,
    )

    expected = source[np.ix_([2, 3, 4], [2, 3, 4])]
    assert np.array_equal(out, expected)
    assert np.array_equal(valid, np.ones((3, 3), dtype=np.float32))


def test_resample_yaw_90_transform_rotates_sampling_frame():
    source = np.arange(49, dtype=np.float32).reshape((7, 7))
    transform = np.array(
        [
            [0.0, -1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )

    out, valid = resample_layer_to_base(
        source_layer=source,
        source_resolution=1.0,
        source_center_x=0.0,
        source_center_y=0.0,
        transform_matrix=transform,
        output_rows=3,
        output_cols=3,
        output_resolution=1.0,
        x_max=1.0,
        y_max=1.0,
        unknown_value=np.nan,
    )

    assert out[0, 1] == source[3, 2]  # base +x maps to odom +y.
    assert out[1, 0] == source[4, 3]  # base +y maps to odom -x.
    assert np.array_equal(valid, np.ones((3, 3), dtype=np.float32))


def test_resample_marks_out_of_bounds_and_nan_invalid():
    source = np.arange(9, dtype=np.float32).reshape((3, 3))
    source[1, 1] = np.nan
    transform = np.eye(4, dtype=np.float32)

    out, valid = resample_layer_to_base(
        source_layer=source,
        source_resolution=1.0,
        source_center_x=0.0,
        source_center_y=0.0,
        transform_matrix=transform,
        output_rows=3,
        output_cols=3,
        output_resolution=1.0,
        x_max=1.0,
        y_max=1.0,
        unknown_value=-999.0,
    )

    assert out[1, 1] == -999.0
    assert valid[1, 1] == 0.0
    assert valid[0, 0] == 1.0


def test_encode_base_multiarray_is_row_major_with_base_labels():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)

    msg = encode_base_multiarray(arr)

    assert msg.layout.dim[0].label == "base_x_index"
    assert msg.layout.dim[0].size == 2
    assert msg.layout.dim[1].label == "base_y_index"
    assert msg.layout.dim[1].size == 2
    assert list(msg.data) == [1.0, 2.0, 3.0, 4.0]
