import importlib.util
from pathlib import Path
from unittest.mock import patch

from launch import LaunchDescription


def load_launch(path: Path) -> LaunchDescription:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.generate_launch_description()


def test_go2_mid360_launch_description_generates_with_base_height_map():
    repo_root = Path(__file__).resolve().parents[1]
    launch_file = repo_root / "launch" / "go2_mid360.launch.py"

    with patch("ament_index_python.packages.get_package_share_directory", return_value=str(repo_root)):
        description = load_launch(launch_file)

    assert isinstance(description, LaunchDescription)
    argument_names = {
        entity.name
        for entity in description.entities
        if entity.__class__.__name__ == "DeclareLaunchArgument"
    }
    assert "launch_base_height_map" in argument_names
    assert "base_height_map_config" in argument_names
