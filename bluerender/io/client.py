"""
BlueMap HTTP client for fetching tiles and settings.
"""

import gzip
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests

from bluerender.core import Endpoints, RenderDefaults, BlueMapDefaults
from bluerender.core import PRBMGeometry, TextureAtlas
from .parser import parse_prbm
from .textures import TextureLoader


class BlueMapClient:
    """HTTP client for BlueMap server communication."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._texture_loader = TextureLoader()
        self._texture_cache: Dict[str, TextureAtlas] = {}
        self._maps: Dict[str, dict] = {}
        self._map_settings_cache: Dict[str, dict] = {}

        self._load_server_settings()

    @property
    def maps(self) -> Dict[str, dict]:
        """Available maps on the server."""
        return self._maps

    def _load_server_settings(self) -> None:
        """Load server-level settings."""
        try:
            url = self.base_url + Endpoints.SETTINGS
            r = self.session.get(url)
            r.raise_for_status()
            settings = r.json()

            maps_list = settings.get("maps", [])
            if maps_list and isinstance(maps_list[0], str):
                # BlueMap 5.x format: just map IDs
                self._maps = {m: {"id": m} for m in maps_list}
            else:
                # Older format: list of map objects
                self._maps = {m["id"]: m for m in maps_list}

        except Exception as e:
            logging.warning(f"Could not load settings: {e}")
            self._maps = {}

    def get_map_settings(self, map_id: str) -> dict:
        """
        Load map-specific settings (cached).

        Args:
            map_id: The map identifier

        Returns:
            Map settings dictionary
        """
        if map_id in self._map_settings_cache:
            return self._map_settings_cache[map_id]

        try:
            url = self.base_url + Endpoints.MAP_SETTINGS.format(map_id=map_id)
            r = self.session.get(url)
            r.raise_for_status()
            settings = r.json()
            self._map_settings_cache[map_id] = settings
            return settings
        except Exception as e:
            logging.warning(f"Could not load map settings: {e}")
            return {}

    def get_tile_config(self, map_id: str) -> tuple[tuple[int, int], tuple[int, int]]:
        """
        Get tile size and translation for a map.

        Returns:
            Tuple of (tile_size, translate)
        """
        settings = self.get_map_settings(map_id)
        hires = settings.get("hires", {})

        tile_size = tuple(hires.get("tileSize", BlueMapDefaults.TILE_SIZE))
        translate = tuple(hires.get("translate", BlueMapDefaults.TRANSLATE))

        return tile_size, translate

    def fetch_tile(
        self, map_id: str, tile_x: int, tile_z: int
    ) -> Optional[PRBMGeometry]:
        """
        Fetch and parse a hires tile.

        Args:
            map_id: Map identifier
            tile_x, tile_z: Tile coordinates

        Returns:
            Parsed geometry or None if tile doesn't exist
        """
        path = _coords_to_path(tile_x, tile_z)
        url = self.base_url + Endpoints.TILE.format(map_id=map_id, path=path)

        try:
            r = self.session.get(url, timeout=RenderDefaults.REQUEST_TIMEOUT)
            if r.status_code == 204:
                return None  # No tile at this location
            r.raise_for_status()

            data = _decompress_if_needed(r.content)
            return parse_prbm(data)

        except Exception as e:
            logging.debug(f"Tile {tile_x},{tile_z} failed: {e}")
            return None

    def fetch_tiles_parallel(
        self,
        map_id: str,
        tile_coords: List[Tuple[int, int]],
        max_workers: int = 8,
    ) -> List[Tuple[int, int, Optional[PRBMGeometry]]]:
        """
        Fetch multiple tiles in parallel.

        Args:
            map_id: Map identifier
            tile_coords: List of (tile_x, tile_z) coordinates
            max_workers: Maximum concurrent requests

        Returns:
            List of (tile_x, tile_z, geometry) tuples
        """
        results = []

        def fetch_one(coords):
            tx, tz = coords
            geom = self.fetch_tile(map_id, tx, tz)
            return (tx, tz, geom)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_one, c): c for c in tile_coords}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    coords = futures[future]
                    logging.debug(f"Tile {coords} failed: {e}")
                    results.append((coords[0], coords[1], None))

        return results

    def get_textures(self, map_id: str) -> TextureAtlas:
        """
        Load textures for a map (cached both in memory and on disk).

        Args:
            map_id: Map identifier

        Returns:
            TextureAtlas with loaded textures
        """
        if map_id in self._texture_cache:
            return self._texture_cache[map_id]

        logging.info(f"Loading textures for map {map_id}...")

        try:
            # Try to load from disk cache first (skips network request)
            atlas = self._texture_loader.load_atlas_cached_only(map_id)
            if atlas is not None:
                self._texture_cache[map_id] = atlas
                return atlas

            # No cache, fetch from network
            url = self.base_url + Endpoints.TEXTURES.format(map_id=map_id)
            r = self.session.get(url)
            r.raise_for_status()
            textures_data = r.json()

            atlas = self._texture_loader.load_atlas(textures_data, map_id=map_id)
            self._texture_cache[map_id] = atlas
            return atlas

        except Exception as e:
            logging.warning(f"Could not load textures.json: {e}")
            return TextureAtlas()


def _coords_to_path(x: int, z: int) -> str:
    """Generate tile path from coordinates."""
    return f"{_format_coord(x, 'x')}/{_format_coord(z, 'z')}"


def _format_coord(c: int, prefix: str) -> str:
    """Format coordinate for path."""
    if c < 0:
        sign = "-"
        c = abs(c)
    else:
        sign = ""

    s = str(c)
    if len(s) == 1:
        return f"{prefix}{sign}{s}"

    parts = [s[-1]]
    s = s[:-1]
    while s:
        parts.insert(0, s[-1])
        s = s[:-1]

    return f"{prefix}{sign}{'/'.join(parts)}"


def _decompress_if_needed(data: bytes) -> bytes:
    """Decompress gzip data if needed."""
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    return data
