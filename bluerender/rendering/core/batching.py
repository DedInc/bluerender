"""
Geometry batching for efficient GPU rendering.

Groups geometry by material to minimize draw calls.
"""

from collections import defaultdict
from typing import Dict, List

import numpy as np

from bluerender.core import TileGeometry


class BatchedVertexData:
    """Batched vertex data for a single material."""

    __slots__ = (
        "positions",
        "normals",
        "colors",
        "uvs",
        "ao",
        "sunlight",
        "blocklight",
    )

    def __init__(
        self,
        positions: np.ndarray,
        normals: np.ndarray,
        colors: np.ndarray,
        uvs: np.ndarray,
        ao: np.ndarray,
        sunlight: np.ndarray,
        blocklight: np.ndarray,
    ):
        self.positions = positions
        self.normals = normals
        self.colors = colors
        self.uvs = uvs
        self.ao = ao
        self.sunlight = sunlight
        self.blocklight = blocklight


def batch_geometry_by_material(
    geometries: List[TileGeometry],
) -> Dict[int, BatchedVertexData]:
    """
    Batch all geometry by material index for efficient rendering.

    This merges all vertices with the same material across all tiles
    into single arrays, allowing one draw call per material instead
    of one per material per tile.

    Args:
        geometries: List of tile geometries

    Returns:
        Dict mapping material index to batched vertex data
    """
    material_verts: Dict[int, List[np.ndarray]] = defaultdict(list)
    material_normals: Dict[int, List[np.ndarray]] = defaultdict(list)
    material_colors: Dict[int, List[np.ndarray]] = defaultdict(list)
    material_uvs: Dict[int, List[np.ndarray]] = defaultdict(list)
    material_ao: Dict[int, List[np.ndarray]] = defaultdict(list)
    material_sunlight: Dict[int, List[np.ndarray]] = defaultdict(list)
    material_blocklight: Dict[int, List[np.ndarray]] = defaultdict(list)

    for tile_geom in geometries:
        geom = tile_geom.geometry
        if geom.is_empty:
            continue

        offset_geom = tile_geom.offset_geometry

        if geom.groups:
            for group in geom.groups:
                if group.count <= 0 or group.start >= len(geom.position):
                    continue

                end = min(group.start + group.count, len(geom.position))
                mat_idx = group.material_index

                material_verts[mat_idx].append(offset_geom.position[group.start : end])
                material_normals[mat_idx].append(offset_geom.normal[group.start : end])
                material_colors[mat_idx].append(offset_geom.color[group.start : end])
                material_uvs[mat_idx].append(offset_geom.uv[group.start : end])
                material_ao[mat_idx].append(offset_geom.ao[group.start : end])
                material_sunlight[mat_idx].append(
                    offset_geom.sunlight[group.start : end]
                )
                material_blocklight[mat_idx].append(
                    offset_geom.blocklight[group.start : end]
                )
        else:
            # No material groups - use material -1 for untextured
            material_verts[-1].append(offset_geom.position)
            material_normals[-1].append(offset_geom.normal)
            material_colors[-1].append(offset_geom.color)

            if offset_geom.uv is not None:
                material_uvs[-1].append(offset_geom.uv)
            else:
                material_uvs[-1].append(
                    np.zeros((len(offset_geom.position), 2), dtype=np.float32)
                )

            material_ao[-1].append(offset_geom.ao)
            material_sunlight[-1].append(offset_geom.sunlight)
            material_blocklight[-1].append(offset_geom.blocklight)

    # Concatenate into batched data
    batched = {}
    for mat_idx in material_verts:
        if not material_verts[mat_idx]:
            continue

        batched[mat_idx] = BatchedVertexData(
            positions=np.concatenate(material_verts[mat_idx]).astype(np.float32),
            normals=np.concatenate(material_normals[mat_idx]).astype(np.float32),
            colors=np.concatenate(material_colors[mat_idx]).astype(np.float32),
            uvs=np.concatenate(material_uvs[mat_idx]).astype(np.float32),
            ao=np.concatenate(material_ao[mat_idx]).astype(np.float32),
            sunlight=np.concatenate(material_sunlight[mat_idx]).astype(np.float32),
            blocklight=np.concatenate(material_blocklight[mat_idx]).astype(np.float32),
        )

    return batched
