"""
Tile loading and coordinate conversion.
"""

import logging
from typing import List, Tuple

from bluerender.core import TileGeometry
from bluerender.io import BlueMapClient


class TileLoader:
    """Loads and manages BlueMap tiles."""

    def __init__(self, client: BlueMapClient):
        self._client = client

    def load_tiles_around_center(
        self,
        map_id: str,
        center_x: float,
        center_z: float,
        radius: int,
    ) -> List[TileGeometry]:
        """
        Load tiles around a center point using parallel fetching.

        Args:
            map_id: Map identifier
            center_x: World X coordinate
            center_z: World Z coordinate
            radius: Number of tiles to load in each direction

        Returns:
            List of loaded tile geometries
        """
        tile_size, translate = self._client.get_tile_config(map_id)

        tile_x, tile_z = self._world_to_tile_coords(
            center_x, center_z, tile_size, translate
        )

        logging.info(f"Center ({center_x}, {center_z}) -> tile ({tile_x}, {tile_z})")
        logging.info(f"Loading tiles in radius {radius}...")

        tile_coords = self._generate_tile_grid(tile_x, tile_z, radius)
        results = self._client.fetch_tiles_parallel(map_id, tile_coords)

        geometries = self._build_geometries(results, tile_size, translate)

        logging.info(f"Loaded {len(geometries)} tiles")
        return geometries

    def _world_to_tile_coords(
        self,
        world_x: float,
        world_z: float,
        tile_size: Tuple[int, int],
        translate: Tuple[int, int],
    ) -> Tuple[int, int]:
        """Convert world coordinates to tile coordinates."""
        tile_x = int((world_x - translate[0]) / tile_size[0])
        tile_z = int((world_z - translate[1]) / tile_size[1])
        return tile_x, tile_z

    def _generate_tile_grid(
        self, center_x: int, center_z: int, radius: int
    ) -> List[Tuple[int, int]]:
        """Generate list of tile coordinates in a grid around center."""
        return [
            (center_x + dx, center_z + dz)
            for dx in range(-radius, radius + 1)
            for dz in range(-radius, radius + 1)
        ]

    def _build_geometries(
        self,
        results: List[Tuple[int, int, any]],
        tile_size: Tuple[int, int],
        translate: Tuple[int, int],
    ) -> List[TileGeometry]:
        """Build TileGeometry objects from fetch results."""
        geometries = []

        for tx, tz, geom in results:
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

        return geometries
