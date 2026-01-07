"""
Rendering buffers and pixel operations.
"""

import numpy as np
from PIL import Image

from bluerender.core import RenderSettings


class RenderBuffers:
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
