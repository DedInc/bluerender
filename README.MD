# BlueRender

A headless Python renderer for [BlueMap](https://github.com/BlueMap-Minecraft/BlueMap) tiles. It fetches map data from a running BlueMap HTTP server and renders 3D or 2D images without requiring a web browser.

It supports OpenGL rendering via ModernGL with fallbacks to software rasterization (Numba or pure NumPy) for environments without a display server.

![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Requirements

- Python 3.8+
- Access to a BlueMap server (local or remote) via HTTP

## Installation

Clone the repository:

```bash
git clone https://github.com/your-repo/bluerender.git
cd bluerender
```

Install core dependencies:

```bash
pip install numpy pillow requests
```

### Optional Backends

The renderer selects a backend based on available libraries:

1.  **OpenGL (Recommended):** Requires `moderngl`. Fastest, supports all shader features.
    ```bash
    pip install moderngl
    ```
2.  **JIT Software (Fast CPU):** Requires `numba`. ~20-50x faster than pure Python. Good for headless servers.
    ```bash
    pip install numba
    ```
3.  **Texture Compression:** `imagequant` reduces cache size significantly compared to PIL.
    ```bash
    pip install imagequant
    ```

*If no optional packages are installed, the script defaults to the pure NumPy software renderer (slowest).*

## Usage

### CLI

The entry point is `blue.py`.

```bash
python blue.py <url> <map_id> <x> <z> <output_file> [flags]
```

**Basic capture:**
```bash
python blue.py http://localhost:8100/ world 283 240 render.png
```

**Arguments:**

*   `url`: Base URL of the BlueMap server.
*   `map_id`: Map identifier configured in BlueMap (e.g., `world`, `world_nether`).
*   `x`, `z`: Center coordinates.
*   `output_file`: Path for the resulting PNG.

**Options:**

| Flag | Description | Default |
| :--- | :--- | :--- |
| `-r`, `--radius` | Number of tile layers to load around center. | 3 |
| `-W`, `--width` | Output width. | 1920 |
| `-H`, `--height` | Output height. | 1080 |
| `-d`, `--distance` | Camera distance from target. | 200.0 |
| `-a`, `--angle` | Vertical camera angle (0=top-down, 90=side). | 45.0 |
| `--rotation` | Horizontal rotation (degrees). | 45.0 |
| `--ortho` | Enable orthographic projection. | False |
| `--software` | Force software rendering (disables ModernGL). | False |
| `--benchmark` | Print timing statistics. | False |

### Python API

```python
from bluerender import BlueMap3DRenderer

# Initialize
renderer = BlueMap3DRenderer(base_url="http://localhost:8100/")

# Render
image = renderer.capture(
    map_id="world",
    center_x=283,
    center_z=240,
    radius=3,
    width=1920,
    height=1080,
    camera_distance=200,
    camera_angle=45,
    camera_rotation=45,
    perspective=True
)

image.save("output.png")
```

## Architecture

### Rendering Backends

The system implements a unified pipeline with swappable rasterizers.

1.  **GPU Renderer (`gpu_renderer.py`)**:
    *   Uses `moderngl` for OpenGL 3.3+ context.
    *   Implements shaders for distance-based fog, ambient occlusion (AO), and sun/block lighting.
    *   Handles vertex buffers directly from parsed PRBM data.

2.  **Software Renderer (`software_renderer.py` / `fast_software_renderer.py`)**:
    *   Used when `moderngl` is missing or `--software` is passed.
    *   If `numba` is installed, JIT compiles the rasterization loop (barycentric coordinates, depth buffering).
    *   If `numba` is missing, falls back to `numpy` vectorization.
    *   *Note: First run with Numba incurs a compilation overhead (2-3s).*

### PRBM Parsing

BlueMap uses a custom binary format (Packed Renderable Binary Mesh). This library includes a parser (`prbm.py`) that reads:
*   Vertex attributes: Position, Normal, Color, UV, AO, Sunlight, Blocklight.
*   Material groups: Maps triangle ranges to texture indices.

### Caching

Texture atlases are downloaded once and cached to disk to reduce network load and decoding time.

*   **Location:** `~/.cache/bluerender/textures/` (Linux/Mac) or `AppData` (Windows).
*   **Format:** Compressed NumPy archives (`.npz`) containing pre-processed arrays.
*   **Invalidation:** SHA-256 hash check against the server's texture config.

## Performance

Benchmarks run on Intel i5-10400 / UHD Graphics 630. Times include data fetching, parsing, and rendering.

| Backend | Resolution | Radius | Time (Avg) |
| :--- | :--- | :--- | :--- |
| **OpenGL** | 1920x1080 | 3 | 1.30s |
| **OpenGL** | 3840x2160 | 5 | 2.34s |
| **Numba** | 1920x1080 | 3 | 1.23s |
| **Numba** | 800x600 | 1 | 0.53s |
| **Pure Python** | 800x600 | 1 | 6.50s |

*Note: The Numba backend is comparable to integrated graphics for simple scenes but lacks advanced shader support.*
