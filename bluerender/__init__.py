"""
BlueMap 3D Renderer - Renders hires tiles directly without a browser.

Parses PRBM (BlueMap's 3D geometry format) and renders using OpenGL or software.
Supports texture sampling from textures.json for accurate block rendering.
"""

from bluerender.rendering import BlueMap3DRenderer
from bluerender.core import PRBMGeometry, TextureInfo, TextureAtlas
from bluerender.io import parse_prbm

__all__ = [
    "BlueMap3DRenderer",
    "PRBMGeometry",
    "TextureInfo",
    "TextureAtlas",
    "parse_prbm",
]
