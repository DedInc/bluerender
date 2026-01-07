"""
Camera configuration and positioning utilities.
"""

import numpy as np

from bluerender.core import CameraConfig, RenderDefaults
from bluerender.core import TileGeometry
from typing import List


def create_camera_from_target(
    target: np.ndarray,
    distance: float = RenderDefaults.CAMERA_DISTANCE,
    angle: float = RenderDefaults.CAMERA_ANGLE,
    rotation: float = RenderDefaults.CAMERA_ROTATION,
    fov: float = RenderDefaults.FOV,
    perspective: bool = True,
) -> CameraConfig:
    """
    Create camera configuration from target position.

    Args:
        target: 3D target position (x, y, z)
        distance: Distance from camera to target
        angle: Vertical angle (0=top-down, 90=horizontal)
        rotation: Horizontal rotation (0=north)
        fov: Field of view in degrees
        perspective: True for perspective, False for orthographic

    Returns:
        Configured CameraConfig
    """
    return CameraConfig.from_spherical(
        target=target,
        distance=distance,
        angle=angle,
        rotation=rotation,
        fov=fov,
        perspective=perspective,
    )


def calculate_scene_center(
    geometries: List[TileGeometry], center_x: float, center_z: float
) -> np.ndarray:
    """
    Calculate scene center including average Y from geometry.

    Args:
        geometries: List of tile geometries
        center_x: World X coordinate
        center_z: World Z coordinate

    Returns:
        3D center position (x, y, z)
    """
    avg_y = np.mean([g.geometry.position[:, 1].mean() for g in geometries])
    return np.array([center_x, avg_y, center_z], dtype=np.float32)
