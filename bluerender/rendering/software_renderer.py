"""
Software renderer using CPU-based rasterization.
"""

from typing import List

import numpy as np
from PIL import Image

from bluerender.core import (
    TileGeometry,
    CameraConfig,
    RenderSettings,
)
from .math_utils import create_mvp_matrix, transform_vertices, ndc_to_screen


class SoftwareRenderer:
    """CPU-based triangle rasterizer."""

    def render(
        self,
        geometries: List[TileGeometry],
        camera: CameraConfig,
        settings: RenderSettings,
    ) -> Image.Image:
        """
        Render the scene using software rasterization.

        Args:
            geometries: List of tile geometries to render
            camera: Camera configuration
            settings: Render settings

        Returns:
            Rendered PIL Image
        """
        buffers = _RenderBuffers(settings)
        mvp = create_mvp_matrix(camera, settings)

        for tile_geom in geometries:
            self._render_geometry(tile_geom, mvp, settings, buffers)

        return buffers.to_image()

    def _render_geometry(
        self,
        tile_geom: TileGeometry,
        mvp: np.ndarray,
        settings: RenderSettings,
        buffers: "_RenderBuffers",
    ) -> None:
        """Render a single geometry to buffers."""
        geom = tile_geom.geometry
        if geom.is_empty:
            return

        # Apply offset
        offset_geom = tile_geom.offset_geometry

        # Transform to screen space
        ndc_x, ndc_y, ndc_z = transform_vertices(offset_geom.position, mvp)
        screen_x, screen_y = ndc_to_screen(
            ndc_x, ndc_y, settings.width, settings.height
        )

        # Prepare vertex attributes
        attrs = _VertexAttributes.from_geometry(geom, settings)

        # Render triangles
        for i in range(0, len(offset_geom.position), 3):
            self._render_triangle(
                i, screen_x, screen_y, ndc_z, attrs, buffers, settings
            )

    def _render_triangle(
        self,
        i: int,
        screen_x: np.ndarray,
        screen_y: np.ndarray,
        screen_z: np.ndarray,
        attrs: "_VertexAttributes",
        buffers: "_RenderBuffers",
        settings: RenderSettings,
    ) -> None:
        """Render a single triangle."""
        # Get triangle vertices
        x0, y0, z0 = screen_x[i], screen_y[i], screen_z[i]
        x1, y1, z1 = screen_x[i + 1], screen_y[i + 1], screen_z[i + 1]
        x2, y2, z2 = screen_x[i + 2], screen_y[i + 2], screen_z[i + 2]

        # Clip against view frustum
        if not _is_triangle_visible(z0, z1, z2):
            return

        # Calculate bounding box
        bounds = _triangle_bounds(
            x0, y0, x1, y1, x2, y2, settings.width, settings.height
        )
        if bounds is None:
            return

        min_x, max_x, min_y, max_y = bounds

        # Calculate triangle color
        color = attrs.triangle_color(i)
        avg_z = (z0 + z1 + z2) / 3.0

        # Rasterize
        self._rasterize_triangle(
            x0, y0, x1, y1, x2, y2, min_x, max_x, min_y, max_y, avg_z, color, buffers
        )

    def _rasterize_triangle(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
        depth: float,
        color: np.ndarray,
        buffers: "_RenderBuffers",
    ) -> None:
        """Fill triangle using point-in-triangle tests."""
        for py in range(min_y, max_y + 1):
            for px in range(min_x, max_x + 1):
                if _point_in_triangle(px, py, x0, y0, x1, y1, x2, y2):
                    buffers.write_pixel(px, py, depth, color)


class _RenderBuffers:
    """Color and depth buffers for software rendering."""

    def __init__(self, settings: RenderSettings):
        self.width = settings.width
        self.height = settings.height

        self.color = np.zeros((settings.height, settings.width, 3), dtype=np.float32)
        self.color[:] = settings.void_color_normalized

        self.depth = np.full(
            (settings.height, settings.width), np.inf, dtype=np.float32
        )

    def write_pixel(self, x: int, y: int, depth: float, color: np.ndarray) -> None:
        """Write pixel if closer than existing depth."""
        if depth < self.depth[y, x]:
            self.depth[y, x] = depth
            self.color[y, x] = color

    def to_image(self) -> Image.Image:
        """Convert buffers to PIL Image."""
        pixels = np.clip(self.color * 255, 0, 255).astype(np.uint8)
        return Image.fromarray(pixels, "RGB")


class _VertexAttributes:
    """Pre-computed vertex attributes for rendering."""

    def __init__(
        self,
        colors: np.ndarray,
        ao: np.ndarray,
        light: np.ndarray,
        normals: np.ndarray,
    ):
        self.colors = colors
        self.ao = ao
        self.light = light
        self.normals = normals

    @classmethod
    def from_geometry(cls, geom, settings: RenderSettings) -> "_VertexAttributes":
        """Create attributes from geometry."""
        colors = geom.color.astype(np.float32) / 255.0
        ao = geom.ao.astype(np.float32) / 255.0

        sun = geom.sunlight.astype(np.float32)
        block = geom.blocklight.astype(np.float32)
        light = np.maximum(sun, block) * settings.sunlight_strength + block * (
            1 - settings.sunlight_strength
        )
        light = settings.ambient_light + (1 - settings.ambient_light) * (light / 15.0)

        normals = geom.normal.astype(np.float32) / 127.0

        return cls(colors, ao, light, normals)

    def triangle_color(self, i: int) -> np.ndarray:
        """Calculate average color for triangle at index i."""
        # Vertex colors with AO and lighting
        c0 = self.colors[i] * self.ao[i] * self.light[i]
        c1 = self.colors[i + 1] * self.ao[i + 1] * self.light[i + 1]
        c2 = self.colors[i + 2] * self.ao[i + 2] * self.light[i + 2]
        avg_color = (c0 + c1 + c2) / 3.0

        # Normal-based shading
        avg_normal = (self.normals[i] + self.normals[i + 1] + self.normals[i + 2]) / 3.0
        shade = 1.0 - max(0, -avg_normal[1]) * 0.3

        return avg_color * shade


def _is_triangle_visible(z0: float, z1: float, z2: float) -> bool:
    """Check if triangle is within view frustum."""
    if z0 < -1 or z1 < -1 or z2 < -1:
        return False
    if z0 > 1 or z1 > 1 or z2 > 1:
        return False
    return True


def _triangle_bounds(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    width: int,
    height: int,
) -> tuple[int, int, int, int] | None:
    """Calculate screen-space bounding box for triangle."""
    min_x = max(0, min(x0, x1, x2))
    max_x = min(width - 1, max(x0, x1, x2))
    min_y = max(0, min(y0, y1, y2))
    max_y = min(height - 1, max(y0, y1, y2))

    if min_x > max_x or min_y > max_y:
        return None

    return min_x, max_x, min_y, max_y


def _point_in_triangle(
    px: int,
    py: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> bool:
    """Test if point is inside triangle using barycentric coordinates."""
    v0 = (x2 - x0, y2 - y0)
    v1 = (x1 - x0, y1 - y0)
    v2 = (px - x0, py - y0)

    dot00 = v0[0] * v0[0] + v0[1] * v0[1]
    dot01 = v0[0] * v1[0] + v0[1] * v1[1]
    dot02 = v0[0] * v2[0] + v0[1] * v2[1]
    dot11 = v1[0] * v1[0] + v1[1] * v1[1]
    dot12 = v1[0] * v2[0] + v1[1] * v2[1]

    denom = dot00 * dot11 - dot01 * dot01
    if abs(denom) < 1e-10:
        return False

    inv_denom = 1.0 / denom
    u = (dot11 * dot02 - dot01 * dot12) * inv_denom
    v = (dot00 * dot12 - dot01 * dot02) * inv_denom

    return u >= 0 and v >= 0 and u + v <= 1
