"""
Centralized configuration constants and default values.
"""

from typing import Tuple
import logging

# =============================================================================
# Logging Configuration
# =============================================================================

SUPPRESSED_LOGGERS = (
    "PIL",
    "PIL.PngImagePlugin",
    "urllib3",
    "requests",
)


def configure_logging(verbose: bool = False) -> None:
    """Configure logging with appropriate levels."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    for logger_name in SUPPRESSED_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


# =============================================================================
# PRBM Format Constants
# =============================================================================

PRBM_SUPPORTED_VERSION = 1
PRBM_HEADER_SIZE = 8
PRBM_GROUP_SIZE = 12
PRBM_END_MARKER = -1

# Type mapping from PRBM spec
PRBM_TYPE_MAP = {
    1: "float32",  # Float32
    3: "int8",  # Int8
    4: "int16",  # Int16
    6: "int32",  # Int32
    7: "uint8",  # Uint8
    8: "uint16",  # Uint16
    10: "uint32",  # Uint32
}


# =============================================================================
# Rendering Defaults
# =============================================================================


class RenderDefaults:
    """Default rendering parameters."""

    WIDTH: int = 1920
    HEIGHT: int = 1080
    TILE_RADIUS: int = 3
    CAMERA_DISTANCE: float = 200.0
    CAMERA_ANGLE: float = 45.0
    CAMERA_ROTATION: float = 45.0
    FOV: float = 60.0
    SUNLIGHT_STRENGTH: float = 1.0
    AMBIENT_LIGHT: float = 0.2
    VOID_COLOR: Tuple[int, int, int] = (20, 20, 30)

    # Clipping planes
    NEAR_PLANE: float = 0.1
    FAR_PLANE: float = 10000.0

    # Network
    REQUEST_TIMEOUT: int = 10


class BlueMapDefaults:
    """Default BlueMap tile settings."""

    TILE_SIZE: Tuple[int, int] = (32, 32)
    TRANSLATE: Tuple[int, int] = (0, 0)


# =============================================================================
# API Endpoints (relative paths)
# =============================================================================


class Endpoints:
    """BlueMap API endpoint templates."""

    SETTINGS = "/settings.json"
    MAP_SETTINGS = "/maps/{map_id}/settings.json"
    TEXTURES = "/maps/{map_id}/textures.json"
    TILE = "/maps/{map_id}/tiles/0/{path}.prbm"


# =============================================================================
# Colors
# =============================================================================

MISSING_TEXTURE_COLOR: Tuple[float, float, float, float] = (
    1.0,
    0.0,
    1.0,
    1.0,
)  # Magenta
