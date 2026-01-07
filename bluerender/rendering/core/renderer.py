"""
Main BlueMap 3D Renderer facade.

Coordinates tile loading, texture management, and rendering.
Provides a simple API for capturing 3D views.
"""

import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from bluerender.core import RenderDefaults, TileGeometry, RenderSettings, TextureAtlas
from bluerender.io import BlueMapClient
from ..renderers.gpu_renderer import GPURenderer, MODERNGL_AVAILABLE
from ..renderers.software_renderer import SoftwareRenderer
from ..renderers.fast_software_renderer import FastSoftwareRenderer, NUMBA_AVAILABLE
from .tile_loader import TileLoader
from ..utils.camera_utils import create_camera_from_target, calculate_scene_center


class BlueMap3DRenderer:
    """
    Renders BlueMap hires tiles to images.

    Supports GPU rendering via ModernGL or software rendering via numpy.
    """

    def __init__(self, base_url: str, use_gpu: bool = True):
        """Initialize the renderer."""
        self._client = BlueMapClient(base_url)
        self._tile_loader = TileLoader(self._client)
        self._gpu_renderer = GPURenderer()
        self._software_renderer = SoftwareRenderer()
        self._fast_software_renderer = FastSoftwareRenderer()

        self.use_gpu = use_gpu and MODERNGL_AVAILABLE
        if self.use_gpu:
            self.use_gpu = self._gpu_renderer.initialize()

        self.timing: dict = {}

    @property
    def maps(self):
        """Available maps from the server."""
        return self._client.maps

    def capture(
        self,
        map_id: str,
        center_x: float,
        center_z: float,
        radius: int = RenderDefaults.TILE_RADIUS,
        width: int = RenderDefaults.WIDTH,
        height: int = RenderDefaults.HEIGHT,
        camera_distance: float = RenderDefaults.CAMERA_DISTANCE,
        camera_angle: float = RenderDefaults.CAMERA_ANGLE,
        camera_rotation: float = RenderDefaults.CAMERA_ROTATION,
        fov: float = RenderDefaults.FOV,
        sunlight_strength: float = RenderDefaults.SUNLIGHT_STRENGTH,
        ambient_light: float = RenderDefaults.AMBIENT_LIGHT,
        perspective: bool = True,
        output_path: Optional[str] = None,
        void_color: Tuple[int, int, int] = RenderDefaults.VOID_COLOR,
    ) -> Image.Image:
        """Capture a 3D view of the BlueMap."""
        self.timing = {}

        t0 = time.perf_counter()
        geometries = self._tile_loader.load_tiles_around_center(
            map_id, center_x, center_z, radius
        )
        self.timing["tiles"] = time.perf_counter() - t0

        if not geometries:
            return self._create_empty_image(width, height, void_color, output_path)

        t0 = time.perf_counter()
        texture_atlas = self._client.get_textures(map_id)
        self.timing["textures"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        camera = self._create_camera(
            geometries,
            center_x,
            center_z,
            camera_distance,
            camera_angle,
            camera_rotation,
            fov,
            perspective,
        )

        settings = RenderSettings(
            width=width,
            height=height,
            sunlight_strength=sunlight_strength,
            ambient_light=ambient_light,
            void_color=void_color,
        )
        self.timing["setup"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        image = self._render(geometries, camera, settings, texture_atlas)
        self.timing["render"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        if output_path:
            self._save_image(image, output_path)
        self.timing["save"] = time.perf_counter() - t0

        return image

    def _create_camera(
        self,
        geometries: List[TileGeometry],
        center_x: float,
        center_z: float,
        distance: float,
        angle: float,
        rotation: float,
        fov: float,
        perspective: bool,
    ):
        """Create camera configuration."""
        target = calculate_scene_center(geometries, center_x, center_z)

        camera = create_camera_from_target(
            target=target,
            distance=distance,
            angle=angle,
            rotation=rotation,
            fov=fov,
            perspective=perspective,
        )

        logging.info(f"Camera: pos={camera.position}, target={camera.target}")
        return camera

    def _render(
        self,
        geometries: List[TileGeometry],
        camera,
        settings: RenderSettings,
        texture_atlas: TextureAtlas,
    ) -> Image.Image:
        """Render using appropriate renderer."""
        if self.use_gpu:
            return self._gpu_renderer.render(
                geometries, camera, settings, texture_atlas
            )

        if NUMBA_AVAILABLE:
            logging.info("Using fast CPU rendering (Numba JIT)...")
        else:
            logging.info("Using software rendering (this may be slow)...")
        return self._fast_software_renderer.render(
            geometries, camera, settings, texture_atlas
        )

    def _create_empty_image(
        self,
        width: int,
        height: int,
        void_color: Tuple[int, int, int],
        output_path: Optional[str],
    ) -> Image.Image:
        """Create empty image when no tiles found."""
        logging.warning("No tiles found!")
        img = Image.new("RGB", (width, height), void_color)
        if output_path:
            img.save(output_path)
        return img

    def _save_image(self, image: Image.Image, path: str) -> None:
        """Save image with optimized settings."""
        path_lower = path.lower()
        if path_lower.endswith(".png"):
            image.save(path, compress_level=1)
        elif path_lower.endswith(".jpg") or path_lower.endswith(".jpeg"):
            image.save(path, quality=90, optimize=False)
        else:
            image.save(path)
        size_kb = Path(path).stat().st_size / 1024
        logging.info(f"Saved: {path} ({size_kb:.1f} KB)")
