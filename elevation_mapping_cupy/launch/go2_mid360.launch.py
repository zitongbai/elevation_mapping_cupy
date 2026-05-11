import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    package_name = "elevation_mapping_cupy"
    share_dir = get_package_share_directory(package_name)

    core_param_path = os.path.join(share_dir, "config", "core", "core_param.yaml")
    default_go2_config = "go2/mid360.yaml"

    if not os.path.exists(core_param_path):
        raise FileNotFoundError(f"Missing core params: {core_param_path}")

    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="Use /clock if true.",
    )
    launch_rviz_arg = DeclareLaunchArgument(
        "launch_rviz",
        default_value="true",
        description="Launch RViz2.",
    )
    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value=os.path.join(share_dir, "rviz", "go2_mid360.rviz"),
        description="Path to an RViz config file.",
    )
    robot_config_arg = DeclareLaunchArgument(
        "robot_config",
        default_value=default_go2_config,
        description="Name of the Go2 setup config file within config/setups/.",
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    launch_rviz = LaunchConfiguration("launch_rviz")
    rviz_config = LaunchConfiguration("rviz_config")
    robot_config = LaunchConfiguration("robot_config")
    go2_param_path = PathJoinSubstitution([share_dir, "config", "setups", robot_config])

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
            robot_config_arg,
            elevation_mapping_node,
            rviz_node,
        ]
    )
