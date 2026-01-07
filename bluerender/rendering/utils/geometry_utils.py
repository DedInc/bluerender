"""
Geometry transformation and texture preparation utilities.
"""

from typing import List, Optional, Set

import numpy as np

from bluerender.core import TileGeometry, RenderSettings, TextureAtlas


def transform_to_screen(
    positions: np.ndarray, mvp: np.ndarray, settings: RenderSettings
) -> tuple:
    """Transform vertices to screen space with perspective division."""
    ones = np.ones((len(positions), 1), dtype=np.float32)
    positions_h = np.hstack([positions, ones])

    clip = positions_h @ mvp.T

    w = clip[:, 3:4]
    w = np.where(np.abs(w) < 1e-10, 1e-10, w)
    inv_w = 1.0 / w

    ndc = clip[:, :3] * inv_w

    screen_x = (ndc[:, 0] + 1) * 0.5 * settings.width
    screen_y = (1 - ndc[:, 1]) * 0.5 * settings.height
    screen_z = ndc[:, 2]

    return (
        screen_x.astype(np.float32),
        screen_y.astype(np.float32),
        screen_z.astype(np.float32),
        inv_w.flatten().astype(np.float32),
    )


def prepare_textures(texture_atlas: TextureAtlas) -> tuple:
    """
    Pack textures into arrays and identify transparent materials.

    Returns:
        (texture_array, texture_sizes, transparent_materials)
    """
    max_h, max_w = 1, 1
    transparent_materials = set()

    for i, tex in enumerate(texture_atlas.textures):
        if tex.half_transparent:
            transparent_materials.add(i)

        if tex.image is not None:
            max_h = max(max_h, tex.image.shape[0])
            max_w = max(max_w, tex.image.shape[1])

    num_textures = len(texture_atlas.textures)
    texture_array = np.zeros((num_textures, max_h, max_w, 4), dtype=np.uint8)
    texture_sizes = np.zeros((num_textures, 2), dtype=np.int32)

    for i, tex in enumerate(texture_atlas.textures):
        if tex.image is not None:
            h, w = tex.image.shape[:2]
            texture_array[i, :h, :w, :] = tex.image
            texture_sizes[i] = [h, w]

    return texture_array, texture_sizes, transparent_materials


def collect_geometry_batch(
    geometries: List[TileGeometry],
    transparent_materials: Set[int],
    transparent_pass: bool,
) -> Optional[dict]:
    """
    Collects geometry for a specific pass (opaque or transparent).

    Args:
        geometries: List of tile geometries
        transparent_materials: Set of material indices that are transparent
        transparent_pass: True for transparent pass, False for opaque

    Returns:
        Dict of concatenated arrays, or None if empty
    """
    all_pos, all_norm, all_col, all_uv, all_ao = [], [], [], [], []
    all_sun, all_blk, all_mat = [], [], []

    count = 0

    for tile_geom in geometries:
        geom = tile_geom.geometry
        if geom.is_empty:
            continue

        if geom.groups:
            offset_geom = tile_geom.offset_geometry

            for group in geom.groups:
                is_trans = group.material_index in transparent_materials

                if is_trans == transparent_pass:
                    start_idx = group.start
                    end_idx = group.start + group.count

                    all_pos.append(offset_geom.position[start_idx:end_idx])
                    all_norm.append(offset_geom.normal[start_idx:end_idx])
                    all_col.append(offset_geom.color[start_idx:end_idx])
                    all_ao.append(offset_geom.ao[start_idx:end_idx])
                    all_sun.append(offset_geom.sunlight[start_idx:end_idx])
                    all_blk.append(offset_geom.blocklight[start_idx:end_idx])

                    if offset_geom.uv is not None:
                        all_uv.append(offset_geom.uv[start_idx:end_idx])
                    else:
                        all_uv.append(np.zeros((group.count, 2), dtype=np.float32))

                    m_idx = np.full(
                        group.count // 3, group.material_index, dtype=np.int32
                    )
                    all_mat.append(m_idx)

                    count += group.count
        else:
            # Untextured - assume opaque
            if not transparent_pass:
                offset_geom = tile_geom.offset_geometry
                all_pos.append(offset_geom.position)
                all_norm.append(offset_geom.normal)
                all_col.append(offset_geom.color)
                all_ao.append(offset_geom.ao)
                all_sun.append(offset_geom.sunlight)
                all_blk.append(offset_geom.blocklight)

                if offset_geom.uv is not None:
                    all_uv.append(offset_geom.uv)
                else:
                    all_uv.append(
                        np.zeros((len(offset_geom.position), 2), dtype=np.float32)
                    )

                all_mat.append(
                    np.full(len(offset_geom.position) // 3, -1, dtype=np.int32)
                )
                count += len(offset_geom.position)

    if count == 0:
        return None

    return {
        "pos": np.concatenate(all_pos).astype(np.float32),
        "norm": np.concatenate(all_norm).astype(np.float32),
        "col": np.concatenate(all_col).astype(np.float32),
        "uv": np.concatenate(all_uv).astype(np.float32),
        "ao": np.concatenate(all_ao).astype(np.float32),
        "sun": np.concatenate(all_sun).astype(np.float32),
        "blk": np.concatenate(all_blk).astype(np.float32),
        "mat": np.concatenate(all_mat).astype(np.int32),
    }


def calculate_lighting(
    sunlight: np.ndarray, blocklight: np.ndarray, settings: RenderSettings
) -> np.ndarray:
    """Calculate combined lighting from sun and block light."""
    light = np.maximum(
        sunlight, blocklight
    ) * settings.sunlight_strength + blocklight * (1 - settings.sunlight_strength)
    return settings.ambient_light + (1 - settings.ambient_light) * (light / 15.0)
