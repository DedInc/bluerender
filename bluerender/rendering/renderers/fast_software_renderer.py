"""
High-performance CPU renderer using Numba JIT compilation.

This renderer uses Numba to compile critical rendering loops to native code,
achieving near-C performance while maintaining Python flexibility.
"""

import logging
from typing import List, Optional

import numpy as np
from PIL import Image

from bluerender.core import TileGeometry, CameraConfig, RenderSettings, TextureAtlas
from ..utils.math_utils import create_mvp_matrix
from ..rasterization.rasterization import NUMBA_AVAILABLE, rasterize_triangles
from ..utils.geometry_utils import (
    transform_to_screen,
    prepare_textures,
    collect_geometry_batch,
    calculate_lighting,
)

if not NUMBA_AVAILABLE:
    logging.warning("Numba not available, falling back to numpy vectorized renderer")


class FastSoftwareRenderer:
    """
    High-performance CPU renderer using Numba JIT compilation.
    Implements a two-pass rendering strategy (Opaque -> Transparent) to handle
    water and glass correctly.
    """

    def __init__(self):
        self._texture_array: Optional[np.ndarray] = None
        self._texture_sizes: Optional[np.ndarray] = None
        self._transparent_materials: set = set()

    def render(
        self,
        geometries: List[TileGeometry],
        camera: CameraConfig,
        settings: RenderSettings,
        texture_atlas: Optional[TextureAtlas] = None,
    ) -> Image.Image:
        """Render using optimized CPU rasterization."""
        if not NUMBA_AVAILABLE:
            return self._render_numpy(geometries, camera, settings)

        color_buffer, depth_buffer = self._initialize_buffers(settings)
        mvp = create_mvp_matrix(camera, settings)

        if texture_atlas and len(texture_atlas) > 0:
            self._prepare_textures_internal(texture_atlas)

        opaque_batch = collect_geometry_batch(
            geometries, self._transparent_materials, transparent_pass=False
        )
        trans_batch = collect_geometry_batch(
            geometries, self._transparent_materials, transparent_pass=True
        )

        if opaque_batch:
            self._render_batch(
                opaque_batch,
                mvp,
                settings,
                color_buffer,
                depth_buffer,
                write_depth=True,
                blend_enabled=False,
            )

        if trans_batch:
            self._render_batch(
                trans_batch,
                mvp,
                settings,
                color_buffer,
                depth_buffer,
                write_depth=False,
                blend_enabled=True,
            )

        pixels = np.clip(color_buffer * 255, 0, 255).astype(np.uint8)
        return Image.fromarray(pixels, "RGB")

    def _initialize_buffers(self, settings: RenderSettings) -> tuple:
        """Initialize color and depth buffers."""
        color_buffer = np.zeros((settings.height, settings.width, 3), dtype=np.float32)
        color_buffer[:] = settings.void_color_normalized
        depth_buffer = np.full(
            (settings.height, settings.width), np.inf, dtype=np.float32
        )
        return color_buffer, depth_buffer

    def _prepare_textures_internal(self, texture_atlas: TextureAtlas) -> None:
        """Pack textures and identify transparency."""
        tex_arr, tex_sizes, trans_mats = prepare_textures(texture_atlas)
        self._texture_array = tex_arr
        self._texture_sizes = tex_sizes
        self._transparent_materials = trans_mats

    def _render_batch(
        self,
        batch: dict,
        mvp: np.ndarray,
        settings: RenderSettings,
        color_buffer: np.ndarray,
        depth_buffer: np.ndarray,
        write_depth: bool,
        blend_enabled: bool,
    ):
        """Render a batch of geometry (opaque or transparent)."""
        positions = batch["pos"]
        normals = batch["norm"] / 127.0
        colors = batch["col"] / 255.0
        uvs = batch["uv"]
        ao = batch["ao"] / 255.0
        sunlight = batch["sun"]
        blocklight = batch["blk"]
        material_indices = batch["mat"]

        light = calculate_lighting(sunlight, blocklight, settings)

        screen_x, screen_y, screen_z, inv_w = transform_to_screen(
            positions, mvp, settings
        )

        tex_arr = (
            self._texture_array
            if self._texture_array is not None
            else np.zeros((0, 0, 0, 4), dtype=np.uint8)
        )
        tex_sizes = (
            self._texture_sizes
            if self._texture_sizes is not None
            else np.zeros((0, 2), dtype=np.int32)
        )

        rasterize_triangles(
            screen_x,
            screen_y,
            screen_z,
            inv_w,
            colors,
            ao,
            light,
            normals,
            uvs,
            material_indices,
            tex_arr,
            tex_sizes,
            color_buffer,
            depth_buffer,
            settings.width,
            settings.height,
            write_depth,
            blend_enabled,
        )

    def _render_numpy(
        self,
        geometries: List[TileGeometry],
        camera: CameraConfig,
        settings: RenderSettings,
    ) -> Image.Image:
        """Fallback to numpy renderer when Numba unavailable."""
        from .software_renderer import SoftwareRenderer

        return SoftwareRenderer().render(geometries, camera, settings)
