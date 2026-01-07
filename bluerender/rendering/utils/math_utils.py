"""
Matrix and vector math utilities for 3D rendering.
"""

import math

import numpy as np

from bluerender.core import RenderDefaults
from bluerender.core import CameraConfig, RenderSettings


def create_view_matrix(
    eye: np.ndarray,
    target: np.ndarray,
    up: np.ndarray = None,
) -> np.ndarray:
    """
    Create a view matrix (look-at).

    Args:
        eye: Camera position
        target: Point camera is looking at
        up: Up vector (default: Y-up)

    Returns:
        4x4 view matrix
    """
    if up is None:
        up = np.array([0, 1, 0], dtype=np.float32)

    forward = target - eye
    forward = forward / np.linalg.norm(forward)

    right = np.cross(forward, up)
    right = right / np.linalg.norm(right)

    up_corrected = np.cross(right, forward)

    m = np.eye(4, dtype=np.float32)
    m[0, :3] = right
    m[1, :3] = up_corrected
    m[2, :3] = -forward
    m[0, 3] = -np.dot(right, eye)
    m[1, 3] = -np.dot(up_corrected, eye)
    m[2, 3] = np.dot(forward, eye)

    return m


def create_perspective_matrix(
    fov: float,
    aspect: float,
    near: float = RenderDefaults.NEAR_PLANE,
    far: float = RenderDefaults.FAR_PLANE,
) -> np.ndarray:
    """
    Create a perspective projection matrix.

    Args:
        fov: Field of view in radians
        aspect: Aspect ratio (width / height)
        near: Near clipping plane
        far: Far clipping plane

    Returns:
        4x4 perspective projection matrix
    """
    f = 1.0 / math.tan(fov / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2 * far * near) / (near - far)
    m[3, 2] = -1
    return m


def create_orthographic_matrix(
    left: float,
    right: float,
    bottom: float,
    top: float,
    near: float = RenderDefaults.NEAR_PLANE,
    far: float = RenderDefaults.FAR_PLANE,
) -> np.ndarray:
    """
    Create an orthographic projection matrix.

    Args:
        left, right: Horizontal clipping planes
        bottom, top: Vertical clipping planes
        near, far: Depth clipping planes

    Returns:
        4x4 orthographic projection matrix
    """
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 2.0 / (right - left)
    m[1, 1] = 2.0 / (top - bottom)
    m[2, 2] = -2.0 / (far - near)
    m[0, 3] = -(right + left) / (right - left)
    m[1, 3] = -(top + bottom) / (top - bottom)
    m[2, 3] = -(far + near) / (far - near)
    m[3, 3] = 1.0
    return m


def create_mvp_matrix(camera: CameraConfig, settings: RenderSettings) -> np.ndarray:
    """
    Create combined model-view-projection matrix.

    Args:
        camera: Camera configuration
        settings: Render settings for aspect ratio

    Returns:
        4x4 MVP matrix
    """
    view = create_view_matrix(camera.position, camera.target)

    if camera.perspective:
        proj = create_perspective_matrix(
            math.radians(camera.fov),
            settings.aspect_ratio,
        )
    else:
        size = camera.distance * 0.5
        proj = create_orthographic_matrix(
            -size * settings.aspect_ratio,
            size * settings.aspect_ratio,
            -size,
            size,
        )

    return proj @ view


def transform_vertices(
    positions: np.ndarray, mvp: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Transform vertices through MVP and project to screen space.

    Args:
        positions: (N, 3) vertex positions
        mvp: 4x4 MVP matrix

    Returns:
        Tuple of (screen_x, screen_y, screen_z) arrays
    """
    # Homogeneous coordinates
    pos_h = np.hstack([positions, np.ones((len(positions), 1), dtype=np.float32)])

    # Transform
    clip = pos_h @ mvp.T

    # Perspective divide
    ndc = clip[:, :3] / clip[:, 3:4]

    return ndc[:, 0], ndc[:, 1], ndc[:, 2]


def ndc_to_screen(
    ndc_x: np.ndarray,
    ndc_y: np.ndarray,
    width: int,
    height: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert NDC coordinates to screen pixels.

    Args:
        ndc_x, ndc_y: Normalized device coordinates (-1 to 1)
        width, height: Screen dimensions

    Returns:
        Tuple of (screen_x, screen_y) as integer arrays
    """
    screen_x = ((ndc_x + 1) * 0.5 * width).astype(np.int32)
    screen_y = ((1 - ndc_y) * 0.5 * height).astype(np.int32)  # Flip Y
    return screen_x, screen_y
