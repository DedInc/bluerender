"""
Software renderer using CPU-based rasterization.
"""

from typing import List

import numpy as np
from PIL import Image

from bluerender.core import TileGeometry, CameraConfig, RenderSettings
from ..utils.math_utils import create_mvp_matrix, transform_vertices, ndc_to_screen
from ..core.buffers import RenderBuffers
from ..utils.triangle_utils import (
    is_triangle_visible,
    triangle_bounds,
    point_in_triangle,
)


class VertexAttributes:
    """Pre-computed vertex attributes for rendering."""

    __slots__ = ("colors", "ao", "light", "normals")

    def __init__(
        self, colors: np.ndarray, ao: np.ndarray, light: np.ndarray, normals: np.ndarray
    ):
        self.colors = colors
        self.ao = ao
        self.light = light
        self.normals = normals

    @classmethod
    def from_geometry(cls, geom, settings: RenderSettings) -> "VertexAttributes":
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
        c0 = self.colors[i] * self.ao[i] * self.light[i]
        c1 = self.colors[i + 1] * self.ao[i + 1] * self.light[i + 1]
        c2 = self.colors[i + 2] * self.ao[i + 2] * self.light[i + 2]
        avg_color = (c0 + c1 + c2) / 3.0

        avg_normal = (self.normals[i] + self.normals[i + 1] + self.normals[i + 2]) / 3.0
        shade = 1.0 - max(0, -avg_normal[1]) * 0.3

        return avg_color * shade


class SoftwareRenderer:
    """CPU-based triangle rasterizer."""

    def render(
        self,
        geometries: List[TileGeometry],
        camera: CameraConfig,
        settings: RenderSettings,
    ) -> Image.Image:
        """Render the scene using software rasterization."""
        buffers = RenderBuffers(settings)
        mvp = create_mvp_matrix(camera, settings)

        for tile_geom in geometries:
            self._render_geometry(tile_geom, mvp, settings, buffers)

        return buffers.to_image()

    def _render_geometry(
        self,
        tile_geom: TileGeometry,
        mvp: np.ndarray,
        settings: RenderSettings,
        buffers: RenderBuffers,
    ) -> None:
        """Render a single geometry to buffers."""
        geom = tile_geom.geometry
        if geom.is_empty:
            return

        offset_geom = tile_geom.offset_geometry

        ndc_x, ndc_y, ndc_z = transform_vertices(offset_geom.position, mvp)
        screen_x, screen_y = ndc_to_screen(
            ndc_x, ndc_y, settings.width, settings.height
        )

        attrs = VertexAttributes.from_geometry(geom, settings)

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
        attrs: VertexAttributes,
        buffers: RenderBuffers,
        settings: RenderSettings,
    ) -> None:
        """Render a single triangle."""
        x0, y0, z0 = screen_x[i], screen_y[i], screen_z[i]
        x1, y1, z1 = screen_x[i + 1], screen_y[i + 1], screen_z[i + 1]
        x2, y2, z2 = screen_x[i + 2], screen_y[i + 2], screen_z[i + 2]

        if not is_triangle_visible(z0, z1, z2):
            return

        bounds = triangle_bounds(
            x0, y0, x1, y1, x2, y2, settings.width, settings.height
        )
        if bounds is None:
            return

        min_x, max_x, min_y, max_y = bounds
        color = attrs.triangle_color(i)
        avg_z = (z0 + z1 + z2) / 3.0

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
        buffers: RenderBuffers,
    ) -> None:
        """Fill triangle using point-in-triangle tests."""
        for py in range(min_y, max_y + 1):
            for px in range(min_x, max_x + 1):
                if point_in_triangle(px, py, x0, y0, x1, y1, x2, y2):
                    buffers.write_pixel(px, py, depth, color)
