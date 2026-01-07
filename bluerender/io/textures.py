"""
Texture loading and management with optimized caching.

Implements disk-based texture caching using compressed numpy arrays
for fast subsequent loads. Textures are decoded once, quantized for
better compression (using pngquant's imagequant algorithm), and cached.
This avoids expensive base64+PNG decoding on repeat runs.
"""

import logging
from pathlib import Path
from typing import List, Optional

import numpy as np

from bluerender.core import TextureInfo, TextureAtlas
from .cache import TextureCache
from .decoder import ImageDecoder


class TextureLoader:
    """
    Loads and decodes textures from BlueMap texture data.

    Uses disk caching for fast subsequent loads. Textures are decoded
    from base64 PNG once and cached as compressed numpy arrays.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self._cache = TextureCache(cache_dir)
        self._decoder = ImageDecoder()

    def load_atlas_cached_only(self, map_id: str) -> Optional[TextureAtlas]:
        """
        Try to load texture atlas from cache only (no network).

        Args:
            map_id: Map identifier

        Returns:
            TextureAtlas if cache exists, None otherwise
        """
        cached = self._cache.load_cached_direct(map_id)
        if cached is not None:
            return self._build_atlas_from_cache(cached[0], cached[1])
        return None

    def load_atlas(self, textures_data: list, map_id: str = "default") -> TextureAtlas:
        """
        Load texture atlas from textures.json data.

        Uses disk cache for fast loading on subsequent runs.

        Args:
            textures_data: List of texture definitions from textures.json
            map_id: Map identifier for cache keying

        Returns:
            TextureAtlas containing all loaded textures
        """
        cached = self._cache.load_cached(map_id, textures_data)
        if cached is not None:
            return self._build_atlas_from_cache(cached[0], cached[1])

        logging.info("Decoding textures (first run, will be cached)...")
        atlas, images, texture_info = self._decode_textures(textures_data)

        self._cache.save_to_cache(map_id, textures_data, images, texture_info)
        logging.info(f"Loaded {len(atlas)} textures")
        return atlas

    def _decode_textures(self, textures_data: list) -> tuple:
        """Decode all textures from base64 PNG data."""
        atlas = TextureAtlas()
        images = []
        texture_info = []

        for tex_data in textures_data:
            tex_info = self._parse_texture_entry(tex_data)
            atlas.textures.append(tex_info)
            images.append(tex_info.image)
            texture_info.append(
                {
                    "resource_path": tex_info.resource_path,
                    "color": list(tex_info.color),
                    "half_transparent": tex_info.half_transparent,
                }
            )

        return atlas, images, texture_info

    def _build_atlas_from_cache(
        self, images: List[Optional[np.ndarray]], texture_info: List[dict]
    ) -> TextureAtlas:
        """Build atlas from cached data."""
        atlas = TextureAtlas()

        for i, info in enumerate(texture_info):
            tex = TextureInfo(
                resource_path=info["resource_path"],
                color=tuple(info["color"]),
                half_transparent=info["half_transparent"],
                image=images[i] if i < len(images) else None,
            )
            atlas.textures.append(tex)

        return atlas

    def _parse_texture_entry(self, tex_data: dict) -> TextureInfo:
        """Parse a single texture entry."""
        tex_info = TextureInfo(
            resource_path=tex_data.get("resourcePath", ""),
            color=tuple(tex_data.get("color", [1.0, 0.0, 1.0, 1.0])),
            half_transparent=tex_data.get("halfTransparent", False),
        )

        texture_str = tex_data.get("texture", "")
        tex_info.image = self._decoder.decode(texture_str, tex_info.resource_path)

        return tex_info
