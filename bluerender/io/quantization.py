"""
Image quantization utilities for texture compression.

Provides high-quality lossy compression using imagequant (pngquant algorithm)
with PIL fallback for environments without imagequant.
"""

import logging

import numpy as np
from PIL import Image

try:
    import imagequant

    IMAGEQUANT_AVAILABLE = True
except ImportError:
    IMAGEQUANT_AVAILABLE = False
    logging.debug("imagequant not available, using PIL quantization fallback")


def quantize_texture(image: np.ndarray, quality: int = 80) -> np.ndarray:
    """
    Quantize texture to reduce unique colors for better compression.

    Uses imagequant (pngquant algorithm) for high-quality lossy compression.
    Falls back to PIL's built-in quantization if imagequant unavailable.

    Args:
        image: RGBA numpy array (H, W, 4)
        quality: Quality level 0-100 (higher = better quality, less compression)

    Returns:
        Quantized RGBA numpy array
    """
    if image is None:
        return None

    h, w = image.shape[:2]

    # Skip very small textures (not worth quantizing)
    if h <= 4 or w <= 4:
        return image

    if IMAGEQUANT_AVAILABLE:
        return _quantize_imagequant(image, quality)
    return _quantize_pil(image)


def _quantize_imagequant(image: np.ndarray, quality: int = 80) -> np.ndarray:
    """Quantize using imagequant (pngquant algorithm)."""
    try:
        h, w = image.shape[:2]

        indices, palette = imagequant.quantize_raw_rgba_bytes(
            image.tobytes(),
            w,
            h,
            dithering_level=0.8,
            max_colors=256,
            min_quality=max(0, quality - 30),
            max_quality=quality,
        )

        indices_array = np.frombuffer(indices, dtype=np.uint8).reshape(h, w)
        palette_array = np.array(palette, dtype=np.uint8).reshape(-1, 4)
        output = palette_array[indices_array]

        return output

    except Exception as e:
        logging.debug(f"imagequant failed, using original: {e}")
        return image


def _quantize_pil(image: np.ndarray) -> np.ndarray:
    """Fallback quantization using PIL."""
    try:
        pil_img = Image.fromarray(image, mode="RGBA")
        rgb = pil_img.convert("RGB")
        alpha = pil_img.split()[3]

        rgb_quant = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        rgb_back = rgb_quant.convert("RGB")

        result = Image.merge("RGBA", (*rgb_back.split(), alpha))
        return np.array(result)

    except Exception as e:
        logging.debug(f"PIL quantization failed: {e}")
        return image
