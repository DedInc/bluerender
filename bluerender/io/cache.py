"""
Persistent disk cache for decoded textures.

Uses compressed numpy arrays (.npz) for fast loading with cache invalidation
based on texture data hashing.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .quantization import quantize_texture, IMAGEQUANT_AVAILABLE

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "bluerender" / "textures"


class TextureCache:
    """
    Persistent disk cache for decoded textures.

    Uses compressed numpy arrays (.npz) for fast loading.
    Cache is keyed by a hash of the texture data for invalidation.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or _DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load_cached_direct(
        self, map_id: str
    ) -> Optional[Tuple[List[np.ndarray], List[dict]]]:
        """
        Load textures from cache without needing original data.

        Returns:
            Tuple of (images list, metadata list) if cache exists, None otherwise
        """
        meta_path = self._get_meta_path(map_id)
        if not meta_path.exists():
            return None

        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)

            cache_key = meta.get("cache_key")
            if not cache_key:
                return None

            cache_path = self._get_cache_path(map_id, cache_key)
            if not cache_path.exists():
                return None

            images = self._load_images_from_cache(cache_path, meta["num_textures"])
            logging.info(f"Loaded {meta['num_textures']} textures from cache")
            return images, meta["texture_info"]

        except Exception as e:
            logging.debug(f"Direct cache load failed: {e}")
            return None

    def load_cached(
        self, map_id: str, textures_data: list
    ) -> Optional[Tuple[List[np.ndarray], List[dict]]]:
        """
        Try to load textures from cache.

        Returns:
            Tuple of (images list, metadata list) if cache hit, None otherwise
        """
        cache_key = self._compute_cache_key(textures_data)
        cache_path = self._get_cache_path(map_id, cache_key)
        meta_path = self._get_meta_path(map_id)

        if not cache_path.exists() or not meta_path.exists():
            return None

        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)

            if meta.get("cache_key") != cache_key:
                logging.debug(f"Cache key mismatch for {map_id}, invalidating")
                return None

            images = self._load_images_from_cache(cache_path, meta["num_textures"])
            logging.info(f"Loaded {meta['num_textures']} textures from cache")
            return images, meta["texture_info"]

        except Exception as e:
            logging.debug(f"Cache load failed: {e}")
            return None

    def save_to_cache(
        self,
        map_id: str,
        textures_data: list,
        images: List[Optional[np.ndarray]],
        texture_info: List[dict],
    ) -> None:
        """
        Save decoded textures to cache with quantization.

        Args:
            map_id: Map identifier
            textures_data: Original texture data (for cache key)
            images: List of decoded image arrays
            texture_info: List of texture metadata dicts
        """
        cache_key = self._compute_cache_key(textures_data)
        cache_path = self._get_cache_path(map_id, cache_key)
        meta_path = self._get_meta_path(map_id)

        try:
            self._cleanup_old_cache_files(map_id, cache_path)

            save_dict, quantized_count = self._prepare_images_for_cache(images)
            np.savez_compressed(cache_path, **save_dict)

            self._save_metadata(meta_path, cache_key, len(images), texture_info)

            cache_size_kb = cache_path.stat().st_size / 1024
            quant_info = f", {quantized_count} quantized" if quantized_count else ""
            logging.info(
                f"Cached {len(images)} textures ({cache_size_kb:.1f} KB{quant_info})"
            )

        except Exception as e:
            logging.warning(f"Failed to cache textures: {e}")

    def _compute_cache_key(self, textures_data: list) -> str:
        """Compute a hash key for the textures data."""
        hash_input = []
        for tex in textures_data:
            hash_input.append(tex.get("resourcePath", ""))
            hash_input.append(str(tex.get("color", [])))
            tex_str = tex.get("texture", "")
            if tex_str:
                hash_input.append(tex_str[:100])

        content = "|".join(hash_input).encode("utf-8")
        return hashlib.sha256(content).hexdigest()[:16]

    def _get_cache_path(self, map_id: str, cache_key: str) -> Path:
        """Get the cache file path for a map."""
        return self.cache_dir / f"{map_id}_{cache_key}.npz"

    def _get_meta_path(self, map_id: str) -> Path:
        """Get the metadata file path for a map."""
        return self.cache_dir / f"{map_id}_meta.json"

    def _load_images_from_cache(
        self, cache_path: Path, num_textures: int
    ) -> List[Optional[np.ndarray]]:
        """Load images from compressed numpy cache."""
        images = []
        with np.load(cache_path, allow_pickle=False) as data:
            for i in range(num_textures):
                key = f"tex_{i}"
                images.append(data[key] if key in data else None)
        return images

    def _prepare_images_for_cache(
        self, images: List[Optional[np.ndarray]]
    ) -> Tuple[dict, int]:
        """Quantize and prepare images for caching."""
        save_dict = {}
        quantized_count = 0

        for i, img in enumerate(images):
            if img is not None:
                quantized = quantize_texture(img, quality=85)
                save_dict[f"tex_{i}"] = quantized
                if quantized is not img:
                    quantized_count += 1

        return save_dict, quantized_count

    def _cleanup_old_cache_files(self, map_id: str, current_cache_path: Path) -> None:
        """Remove old cache files for this map."""
        for old_file in self.cache_dir.glob(f"{map_id}_*.npz"):
            if old_file != current_cache_path:
                old_file.unlink()

    def _save_metadata(
        self,
        meta_path: Path,
        cache_key: str,
        num_textures: int,
        texture_info: List[dict],
    ) -> None:
        """Save cache metadata."""
        meta = {
            "cache_key": cache_key,
            "num_textures": num_textures,
            "texture_info": texture_info,
            "quantized": IMAGEQUANT_AVAILABLE,
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f)
