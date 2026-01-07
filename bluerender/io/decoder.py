"""
Base64 PNG image decoder for BlueMap textures.
"""

import base64
import io
import logging
from typing import Optional

import numpy as np
from PIL import Image


class ImageDecoder:
    """Decodes base64-encoded PNG images."""

    BASE64_PREFIX = "data:image/png;base64,"

    def decode(self, texture_str: str, resource_path: str) -> Optional[np.ndarray]:
        """
        Decode base64 encoded PNG image.

        Args:
            texture_str: Base64-encoded PNG string
            resource_path: Resource path for logging

        Returns:
            RGBA numpy array or None if decoding fails
        """
        if not texture_str.startswith(self.BASE64_PREFIX):
            return None

        try:
            b64_data = texture_str[len(self.BASE64_PREFIX) :]
            img_bytes = base64.b64decode(b64_data)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            return np.array(img)
        except Exception as e:
            logging.debug(f"Failed to decode texture {resource_path}: {e}")
            return None
