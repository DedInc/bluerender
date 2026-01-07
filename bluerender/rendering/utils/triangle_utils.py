"""
Triangle rasterization utilities for software rendering.
"""


def is_triangle_visible(z0: float, z1: float, z2: float) -> bool:
    """Check if triangle is within view frustum."""
    if z0 < -1 or z1 < -1 or z2 < -1:
        return False
    if z0 > 1 or z1 > 1 or z2 > 1:
        return False
    return True


def triangle_bounds(
    x0: int, y0: int, x1: int, y1: int, x2: int, y2: int, width: int, height: int
) -> tuple[int, int, int, int] | None:
    """Calculate screen-space bounding box for triangle."""
    min_x = max(0, min(x0, x1, x2))
    max_x = min(width - 1, max(x0, x1, x2))
    min_y = max(0, min(y0, y1, y2))
    max_y = min(height - 1, max(y0, y1, y2))

    if min_x > max_x or min_y > max_y:
        return None

    return min_x, max_x, min_y, max_y


def point_in_triangle(
    px: int, py: int, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int
) -> bool:
    """Test if point is inside triangle using barycentric coordinates."""
    v0 = (x2 - x0, y2 - y0)
    v1 = (x1 - x0, y1 - y0)
    v2 = (px - x0, py - y0)

    dot00 = v0[0] * v0[0] + v0[1] * v0[1]
    dot01 = v0[0] * v1[0] + v0[1] * v1[1]
    dot02 = v0[0] * v2[0] + v0[1] * v2[1]
    dot11 = v1[0] * v1[0] + v1[1] * v1[1]
    dot12 = v1[0] * v2[0] + v1[1] * v2[1]

    denom = dot00 * dot11 - dot01 * dot01
    if abs(denom) < 1e-10:
        return False

    inv_denom = 1.0 / denom
    u = (dot11 * dot02 - dot01 * dot12) * inv_denom
    v = (dot00 * dot12 - dot01 * dot02) * inv_denom

    return u >= 0 and v >= 0 and u + v <= 1
