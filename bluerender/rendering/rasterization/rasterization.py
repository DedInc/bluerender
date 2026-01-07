"""
Numba-accelerated rasterization kernels.

High-performance JIT-compiled functions for triangle rasterization
with perspective-correct texture mapping and alpha blending.
"""

import logging

import numpy as np

try:
    from numba import njit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    logging.warning("Numba not available")


if NUMBA_AVAILABLE:

    @njit(cache=True, fastmath=True)
    def _edge_function(
        ax: float, ay: float, bx: float, by: float, cx: float, cy: float
    ) -> float:
        """Compute edge function for point (cx, cy) against edge (ax, ay) -> (bx, by)."""
        return (cx - ax) * (by - ay) - (cy - ay) * (bx - ax)

    @njit(cache=True, fastmath=True, parallel=True)
    def rasterize_triangles(
        screen_x: np.ndarray,
        screen_y: np.ndarray,
        screen_z: np.ndarray,
        inv_w: np.ndarray,
        colors: np.ndarray,
        ao: np.ndarray,
        light: np.ndarray,
        normals: np.ndarray,
        uvs: np.ndarray,
        material_indices: np.ndarray,
        texture_data: np.ndarray,
        texture_sizes: np.ndarray,
        color_buffer: np.ndarray,
        depth_buffer: np.ndarray,
        width: int,
        height: int,
        write_depth: bool,
        blend_enabled: bool,
    ) -> None:
        """
        Unified Rasterizer with Perspective Correction, Clipping, and Blending control.
        """
        num_triangles = len(screen_x) // 3

        for tri in prange(num_triangles):
            i = tri * 3

            x0, y0, z0 = screen_x[i], screen_y[i], screen_z[i]
            x1, y1, z1 = screen_x[i + 1], screen_y[i + 1], screen_z[i + 1]
            x2, y2, z2 = screen_x[i + 2], screen_y[i + 2], screen_z[i + 2]

            area = _edge_function(x0, y0, x1, y1, x2, y2)
            if abs(area) < 1e-10:
                continue

            # Frustum clipping
            if z0 < -1 or z1 < -1 or z2 < -1:
                continue
            if z0 > 1 or z1 > 1 or z2 > 1:
                continue

            # Bounding box
            min_x = max(0, int(min(x0, x1, x2)))
            max_x = min(width - 1, int(max(x0, x1, x2)) + 1)
            min_y = max(0, int(min(y0, y1, y2)))
            max_y = min(height - 1, int(max(y0, y1, y2)) + 1)

            if min_x > max_x or min_y > max_y:
                continue

            inv_area = 1.0 / area
            w0_inv, w1_inv, w2_inv = inv_w[i], inv_w[i + 1], inv_w[i + 2]

            # Perspective-correct UV interpolation setup
            if uvs.size > 0:
                u0_p, v0_p = uvs[i, 0] * w0_inv, uvs[i, 1] * w0_inv
                u1_p, v1_p = uvs[i + 1, 0] * w1_inv, uvs[i + 1, 1] * w1_inv
                u2_p, v2_p = uvs[i + 2, 0] * w2_inv, uvs[i + 2, 1] * w2_inv
            else:
                u0_p, v0_p, u1_p, v1_p, u2_p, v2_p = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

            # Texture info
            has_texture = texture_sizes.shape[0] > 0
            if has_texture:
                mat_idx = material_indices[tri]
                tex_h = texture_sizes[mat_idx, 0]
                tex_w = texture_sizes[mat_idx, 1]
            else:
                tex_h, tex_w = 0, 0

            # Vertex attributes
            ao0, ao1, ao2 = ao[i], ao[i + 1], ao[i + 2]
            l0, l1, l2 = light[i], light[i + 1], light[i + 2]
            vc0, vc1, vc2 = colors[i], colors[i + 1], colors[i + 2]

            # Pixel loop
            for py in range(min_y, max_y + 1):
                for px in range(min_x, max_x + 1):
                    cx, cy = px + 0.5, py + 0.5

                    w0 = _edge_function(x1, y1, x2, y2, cx, cy)
                    w1 = _edge_function(x2, y2, x0, y0, cx, cy)
                    w2 = _edge_function(x0, y0, x1, y1, cx, cy)

                    if area > 0:
                        if w0 < 0 or w1 < 0 or w2 < 0:
                            continue
                    else:
                        if w0 > 0 or w1 > 0 or w2 > 0:
                            continue

                    b0 = w0 * inv_area
                    b1 = w1 * inv_area
                    b2 = w2 * inv_area

                    depth = b0 * z0 + b1 * z1 + b2 * z2
                    if depth >= depth_buffer[py, px]:
                        continue

                    # Texture sampling
                    t_r, t_g, t_b, t_a = 1.0, 1.0, 1.0, 1.0

                    if has_texture and tex_w > 0:
                        pixel_w_inv = b0 * w0_inv + b1 * w1_inv + b2 * w2_inv
                        u_persp = b0 * u0_p + b1 * u1_p + b2 * u2_p
                        v_persp = b0 * v0_p + b1 * v1_p + b2 * v2_p
                        u = u_persp / pixel_w_inv
                        v = v_persp / pixel_w_inv

                        tx = int((u % 1.0) * tex_w) % tex_w
                        ty = int((v % 1.0) * tex_h) % tex_h

                        t_r = texture_data[mat_idx, ty, tx, 0] / 255.0
                        t_g = texture_data[mat_idx, ty, tx, 1] / 255.0
                        t_b = texture_data[mat_idx, ty, tx, 2] / 255.0
                        t_a = texture_data[mat_idx, ty, tx, 3] / 255.0

                    if t_a < 0.1:
                        continue

                    # Lighting and shading
                    i_ao = b0 * ao0 + b1 * ao1 + b2 * ao2
                    i_l = b0 * l0 + b1 * l1 + b2 * l2

                    i_vr = b0 * vc0[0] + b1 * vc1[0] + b2 * vc2[0]
                    i_vg = b0 * vc0[1] + b1 * vc1[1] + b2 * vc2[1]
                    i_vb = b0 * vc0[2] + b1 * vc1[2] + b2 * vc2[2]

                    src_r = t_r * i_vr * i_ao * i_l
                    src_g = t_g * i_vg * i_ao * i_l
                    src_b = t_b * i_vb * i_ao * i_l

                    # Output merging
                    if not blend_enabled or t_a >= 0.99:
                        color_buffer[py, px, 0] = src_r
                        color_buffer[py, px, 1] = src_g
                        color_buffer[py, px, 2] = src_b
                        if write_depth:
                            depth_buffer[py, px] = depth
                    else:
                        dst_r = color_buffer[py, px, 0]
                        dst_g = color_buffer[py, px, 1]
                        dst_b = color_buffer[py, px, 2]

                        color_buffer[py, px, 0] = src_r * t_a + dst_r * (1.0 - t_a)
                        color_buffer[py, px, 1] = src_g * t_a + dst_g * (1.0 - t_a)
                        color_buffer[py, px, 2] = src_b * t_a + dst_b * (1.0 - t_a)

                        if write_depth:
                            depth_buffer[py, px] = depth
