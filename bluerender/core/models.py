"""
Data models for BlueMap 3D renderer.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from .config import MISSING_TEXTURE_COLOR


@dataclass
class TextureInfo:
    """Information about a single texture."""

    resource_path: str
    color: Tuple[float, float, float, float]  # RGBA fallback color
    image: Optional[np.ndarray] = None  # HxWx4 RGBA array
    half_transparent: bool = False

    def sample(self, u: float, v: float) -> np.ndarray:
        """
        Sample color at UV coordinates.

        Returns:
            RGBA color as float array (0-1 range)
        """
        if self.image is None:
            return np.array(self.color)

        h, w = self.image.shape[:2]
        px = int((u % 1.0) * w) % w
        py = int((v % 1.0) * h) % h
        return self.image[py, px] / 255.0


@dataclass
class TextureAtlas:
    """Texture atlas containing all block textures."""

    textures: List[TextureInfo] = field(default_factory=list)

    def get_color(self, material_index: int, u: float, v: float) -> np.ndarray:
        """
        Sample color from texture at given UV coordinates.

        Args:
            material_index: Index into textures list
            u, v: Texture coordinates (0-1 range)

        Returns:
            RGBA color as float array (0-1 range)
        """
        if not self._is_valid_index(material_index):
            return np.array(MISSING_TEXTURE_COLOR)
        return self.textures[material_index].sample(u, v)

    def _is_valid_index(self, index: int) -> bool:
        return 0 <= index < len(self.textures)

    def __len__(self) -> int:
        return len(self.textures)


@dataclass
class MaterialGroup:
    """A group of vertices sharing the same material."""

    material_index: int
    start: int
    count: int

    @classmethod
    def from_dict(cls, data: dict) -> "MaterialGroup":
        return cls(
            material_index=data["materialIndex"],
            start=data["start"],
            count=data["count"],
        )


@dataclass
class PRBMGeometry:
    """Parsed PRBM geometry data."""

    position: np.ndarray  # (N, 3) float32 - vertex positions
    normal: np.ndarray  # (N, 3) int8 - vertex normals
    color: np.ndarray  # (N, 3) uint8 - vertex colors
    uv: np.ndarray  # (N, 2) float32 - texture coordinates
    ao: np.ndarray  # (N,) uint8 - ambient occlusion
    blocklight: np.ndarray  # (N,) int8 - block light level
    sunlight: np.ndarray  # (N,) int8 - sun light level
    groups: List[MaterialGroup]  # Material groups

    @property
    def num_vertices(self) -> int:
        return len(self.position)

    @property
    def num_triangles(self) -> int:
        return len(self.position) // 3

    @property
    def is_empty(self) -> bool:
        return self.num_vertices == 0

    def with_offset(self, offset_x: float, offset_z: float) -> "PRBMGeometry":
        """Create a copy with position offset applied."""
        new_position = self.position.copy()
        new_position[:, 0] += offset_x
        new_position[:, 2] += offset_z
        return PRBMGeometry(
            position=new_position,
            normal=self.normal,
            color=self.color,
            uv=self.uv,
            ao=self.ao,
            blocklight=self.blocklight,
            sunlight=self.sunlight,
            groups=self.groups,
        )


@dataclass
class TileGeometry:
    """Geometry with its world offset."""

    geometry: PRBMGeometry
    offset_x: float
    offset_z: float

    @property
    def offset_geometry(self) -> PRBMGeometry:
        """Get geometry with offset applied."""
        return self.geometry.with_offset(self.offset_x, self.offset_z)


@dataclass
class CameraConfig:
    """Camera configuration for rendering."""

    position: np.ndarray
    target: np.ndarray
    fov: float = 60.0
    perspective: bool = True

    @property
    def distance(self) -> float:
        return float(np.linalg.norm(self.position - self.target))

    @classmethod
    def from_spherical(
        cls,
        target: np.ndarray,
        distance: float,
        angle: float,
        rotation: float,
        fov: float = 60.0,
        perspective: bool = True,
    ) -> "CameraConfig":
        """Create camera from spherical coordinates."""
        import math

        angle_rad = math.radians(angle)
        rot_rad = math.radians(rotation)

        position = np.array(
            [
                target[0] + distance * math.sin(rot_rad) * math.cos(angle_rad),
                target[1] + distance * math.sin(angle_rad),
                target[2] + distance * math.cos(rot_rad) * math.cos(angle_rad),
            ],
            dtype=np.float32,
        )

        return cls(
            position=position,
            target=target,
            fov=fov,
            perspective=perspective,
        )


@dataclass
class RenderSettings:
    """Settings for a render pass."""

    width: int
    height: int
    sunlight_strength: float = 1.0
    ambient_light: float = 0.2
    void_color: Tuple[int, int, int] = (20, 20, 30)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def void_color_normalized(self) -> Tuple[float, float, float]:
        return tuple(c / 255.0 for c in self.void_color)
