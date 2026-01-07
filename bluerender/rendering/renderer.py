"""
Main BlueMap 3D Renderer facade.

Coordinates tile loading, texture management, and rendering.
Provides a simple API for capturing 3D views.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

from bluerender.core import RenderDefaults
from bluerender.core import (
    TileGeometry,
    CameraConfig,
    RenderSettings,
    TextureAtlas,
)
from bluerender.io import BlueMapClient
from .gpu_renderer import GPURenderer, MODERNGL_AVAILABLE
from .software_renderer import SoftwareRenderer


class BlueMap3DRenderer:
    """
    Renders BlueMap hires tiles to images.

    Supports GPU rendering via ModernGL or software rendering via numpy.
    """

    def __init__(self, base_url: str, use_gpu: bool = True):
        """
        Initialize the renderer.

        Args:
            base_url: BlueMap server URL
            use_gpu: Use GPU rendering if available
        """
        self._client = BlueMapClient(base_url)
        self._gpu_renderer = GPURenderer()
        self._software_renderer = SoftwareRenderer()

        self.use_gpu = use_gpu and MODERNGL_AVAILABLE
        if self.use_gpu:
            self.use_gpu = self._gpu_renderer.initialize()

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
        """
        Capture a 3D view of the BlueMap.

        Args:
            map_id: Map to render (e.g., 'world')
            center_x, center_z: World coordinates to center on
            radius: Number of tiles to load in each direction
            width, height: Output image size
            camera_distance: Distance from camera to center
            camera_angle: Vertical angle (0=top-down, 90=horizontal)
            camera_rotation: Horizontal rotation (0=north)
            fov: Field of view in degrees
            sunlight_strength: Sun light intensity (0-1)
            ambient_light: Ambient light intensity (0-1)
            perspective: True for perspective, False for orthographic
            output_path: Optional path to save image
            void_color: Background color RGB

        Returns:
            Rendered PIL Image
        """
        # Load tiles
        geometries = self._load_tiles(map_id, center_x, center_z, radius)

        if not geometries:
            return self._create_empty_image(width, height, void_color, output_path)

        # Load textures
        texture_atlas = self._client.get_textures(map_id)

        # Configure camera
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

        # Configure render settings
        settings = RenderSettings(
            width=width,
            height=height,
            sunlight_strength=sunlight_strength,
            ambient_light=ambient_light,
            void_color=void_color,
        )

        # Render
        image = self._render(geometries, camera, settings, texture_atlas)

        # Save if requested
        if output_path:
            self._save_image(image, output_path)

        return image

    def _load_tiles(
        self,
        map_id: str,
        center_x: float,
        center_z: float,
        radius: int,
    ) -> List[TileGeometry]:
        """Load tiles around center point."""
        tile_size, translate = self._client.get_tile_config(map_id)

        tile_x = int((center_x - translate[0]) / tile_size[0])
        tile_z = int((center_z - translate[1]) / tile_size[1])

        logging.info(f"Center ({center_x}, {center_z}) -> tile ({tile_x}, {tile_z})")
        logging.info(f"Loading tiles in radius {radius}...")

        geometries = []
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                tx, tz = tile_x + dx, tile_z + dz
                geom = self._client.fetch_tile(map_id, tx, tz)

                if geom is not None:
                    offset_x = tx * tile_size[0] + translate[0]
                    offset_z = tz * tile_size[1] + translate[1]

                    geometries.append(
                        TileGeometry(
                            geometry=geom,
                            offset_x=offset_x,
                            offset_z=offset_z,
                        )
                    )

                    logging.debug(
                        f"Loaded tile ({tx}, {tz}): {geom.num_triangles} triangles"
                    )

        logging.info(f"Loaded {len(geometries)} tiles")
        return geometries

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
    ) -> CameraConfig:
        """Create camera configuration."""
        # Calculate average Y from geometry
        avg_y = np.mean([g.geometry.position[:, 1].mean() for g in geometries])

        target = np.array([center_x, avg_y, center_z], dtype=np.float32)

        camera = CameraConfig.from_spherical(
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
        camera: CameraConfig,
        settings: RenderSettings,
        texture_atlas: TextureAtlas,
    ) -> Image.Image:
        """Render using appropriate renderer."""
        if self.use_gpu:
            return self._gpu_renderer.render(
                geometries, camera, settings, texture_atlas
            )
        else:
            logging.info("Using software rendering (this may be slow)...")
            return self._software_renderer.render(geometries, camera, settings)

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
        """Save image and log result."""
        image.save(path)
        size_kb = Path(path).stat().st_size / 1024
        logging.info(f"Saved: {path} ({size_kb:.1f} KB)")
