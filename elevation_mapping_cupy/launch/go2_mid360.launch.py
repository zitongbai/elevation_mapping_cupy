import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_name = "elevation_mapping_cupy"
    share_dir = get_package_share_directory(package_name)

    core_param_path = os.path.join(share_dir, "config", "core", "core_param.yaml")
    go2_param_path = os.path.join(share_dir, "config", "setups", "go2", "mid360.yaml")

    if not os.path.exists(core_param_path):
        raise FileNotFoundError(f"Missing core params: {core_param_path}")
    if not os.path.exists(go2_param_path):
        raise FileNotFoundError(f"Missing Go2 MID360 params: {go2_param_path}")

    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="Use /clock if true.",
    )
    launch_rviz_arg = DeclareLaunchArgument(
        "launch_rviz",
        default_value="false",
        description="Launch RViz2.",
    )
    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value=os.path.join(share_dir, "rviz", "go2_mid360.rviz"),
        description="Path to an RViz config file.",
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    launch_rviz = LaunchConfiguration("launch_rviz")
    rviz_config = LaunchConfiguration("rviz_config")

    elevation_mapping_node = Node(
        package=package_name,
        executable="elevation_mapping_node.py",
        name="elevation_mapping_node",
        output="screen",
        parameters=[
            core_param_path,
            go2_param_path,
            {"use_sim_time": use_sim_time},
        ],
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", rviz_config],
        parameters=[{"use_sim_time": use_sim_time}],
        output="screen",
        condition=IfCondition(launch_rviz),
    )

    return LaunchDescription(
        [
            use_sim_time_arg,
            launch_rviz_arg,
            rviz_config_arg,
            elevation_mapping_node,
            rviz_node,
        ]
    )
