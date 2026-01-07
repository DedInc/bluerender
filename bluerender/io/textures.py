"""
Texture loading and management.
"""

import base64
import io
import logging
from typing import Optional

import numpy as np
from PIL import Image

from bluerender.core import TextureInfo, TextureAtlas


class TextureLoader:
    """Loads and decodes textures from BlueMap texture data."""

    BASE64_PREFIX = "data:image/png;base64,"

    def load_atlas(self, textures_data: list) -> TextureAtlas:
        """
        Load texture atlas from textures.json data.

        Args:
            textures_data: List of texture definitions from textures.json

        Returns:
            TextureAtlas containing all loaded textures
        """
        atlas = TextureAtlas()

        for tex_data in textures_data:
            tex_info = self._parse_texture_entry(tex_data)
            atlas.textures.append(tex_info)

        logging.info(f"Loaded {len(atlas)} textures")
        return atlas

    def _parse_texture_entry(self, tex_data: dict) -> TextureInfo:
        """Parse a single texture entry."""
        tex_info = TextureInfo(
            resource_path=tex_data.get("resourcePath", ""),
            color=tuple(tex_data.get("color", [1.0, 0.0, 1.0, 1.0])),
            half_transparent=tex_data.get("halfTransparent", False),
        )

        texture_str = tex_data.get("texture", "")
        tex_info.image = self._decode_base64_image(texture_str, tex_info.resource_path)

        return tex_info

    def _decode_base64_image(
        self, texture_str: str, resource_path: str
    ) -> Optional[np.ndarray]:
        """Decode base64 encoded PNG image."""
        if not texture_str.startswith(self.BASE64_PREFIX):
            return None

        try:
            b64_data = texture_str[len(self.BASE64_PREFIX) :]
            img_bytes = base64.b64decode(b64_data)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            return np.array(img)
        except Exception as e:
            logging.debug(f"Failed to decode texture {resource_path}: {e}")
            return None
