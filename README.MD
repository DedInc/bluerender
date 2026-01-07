# 🔵 BlueRender

<div align="center">

**A powerful, high-performance 3D renderer for BlueMap tiles — no browser required.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*Render stunning Minecraft world images directly from your BlueMap server with GPU acceleration*

</div>

---

## 🌟 Features

### 🚀 High-Performance Rendering
- **GPU-Accelerated** — Blazing-fast OpenGL rendering via ModernGL
- **Numba JIT Acceleration** — Software renderer optimized with Numba just-in-time compilation
- **Multi-Tier Fallback** — Fast software → Standard software → Always works
- **Parallel Tile Loading** — Efficient HTTP client with session caching
- **Persistent Texture Cache** — Decoded textures cached to disk with smart invalidation
- **Persistent Texture Cache** — Decoded textures cached to disk with smart invalidation

### 🎨 Accurate Visual Fidelity
- **Authentic Textures** — Loads textures directly from BlueMap's `textures.json`
- **Per-Block Materials** — Proper material groups with individual texture sampling
- **Ambient Occlusion** — Smooth AO matching BlueMap's browser rendering
- **Dynamic Lighting** — Sunlight, blocklight, and ambient light support

### 📸 Flexible Camera System
- **Perspective & Orthographic** — Both projection modes supported
- **Spherical Controls** — Distance, angle, and rotation parameters
- **Customizable FOV** — Fine-tune your field of view

### 🛠️ Developer-Friendly
- **Clean API** — Simple Python interface for integration
- **CLI Ready** — Full command-line interface for automation
- **Modular Architecture** — Well-organized codebase with clear separation

---

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- A running BlueMap server

### Install Dependencies

```bash
pip install numpy pillow requests moderngl numba imagequant
```

#### Optional Dependencies

| Package | Purpose | Impact if Missing |
|---------|---------|-------------------|
| `moderngl` | GPU rendering via OpenGL | Falls back to software renderer |
| `numba` | JIT compilation for fast software rendering | Falls back to standard (slower) software renderer |
| `imagequant` | High-quality texture compression for cache | Falls back to PIL quantization (lower quality) |

> 💡 **Note:** BlueRender gracefully degrades based on available dependencies:
> 1. **Best**: GPU rendering (requires `moderngl`)
> 2. **Fast**: Numba-accelerated software rendering (requires `numba`)
> 3. **Fallback**: Pure Python software rendering (always works)

### Clone the Repository

```bash
git clone https://github.com/your-repo/bluerender.git
cd bluerender
```

---

## 🚀 Quick Start

### Command Line

Capture a 3D view with a single command:

```bash
python blue.py http://localhost:8100/ world 283 240 lal.png
```

This captures:
- **Server**: `http://localhost:8100/`
- **Map**: `world`
- **Coordinates**: X=283, Z=240
- **Output**: `lal.png`

### Python API

```python
from bluerender import BlueMap3DRenderer

# Initialize renderer
renderer = BlueMap3DRenderer("http://localhost:8100/")

# Capture a 3D view
image = renderer.capture(
    map_id="world",
    center_x=283,
    center_z=240,
    output_path="render.png"
)
```

---

## 📖 Usage Guide

### CLI Reference

```
python blue.py <url> <map> <x> <z> <output> [options]
```

#### Required Arguments

| Argument | Description |
|----------|-------------|
| `url` | BlueMap server URL (e.g., `http://localhost:8100/`) |
| `map` | Map ID (e.g., `world`, `nether`, `end`) |
| `x` | Center X coordinate in world space |
| `z` | Center Z coordinate in world space |
| `output` | Output image path (e.g., `render.png`) |

#### Optional Arguments

| Option | Default | Description |
|--------|---------|-------------|
| `-r, --radius` | 3 | Tile radius to load (higher = more area) |
| `-W, --width` | 1920 | Output image width in pixels |
| `-H, --height` | 1080 | Output image height in pixels |
| `-d, --distance` | 200.0 | Camera distance from center |
| `-a, --angle` | 45.0 | Camera vertical angle (0=top-down, 90=horizontal) |
| `--rotation` | 45.0 | Camera horizontal rotation (0=north) |
| `--fov` | 60.0 | Field of view in degrees |
| `--sunlight` | 1.0 | Sunlight strength (0.0-1.0) |
| `--ambient` | 0.2 | Ambient light level (0.0-1.0) |
| `--ortho` | — | Use orthographic projection |
| `--software` | — | Force software rendering (fast mode if Numba available) |
| `--force-slow` | — | Force standard software rendering (bypass Numba optimization) |
| `-v, --verbose` | — | Enable verbose logging |
| `--benchmark` | — | Show timing benchmarks and performance breakdown |

### CLI Examples

**High-resolution panoramic shot:**
```bash
python blue.py http://localhost:8100/ world 0 0 panorama.png -W 3840 -H 2160 -r 5 -d 500
```

**Top-down orthographic map:**
```bash
python blue.py http://localhost:8100/ world 100 -200 map.png --ortho -a 90 -r 4
```

**Dramatic low-angle sunset:**
```bash
python blue.py http://localhost:8100/ world 283 240 sunset.png -a 15 --rotation 270 --sunlight 0.7 --ambient 0.1
```

**Close-up detail render:**
```bash
python blue.py http://localhost:8100/ world 283 240 detail.png -r 1 -d 50 --fov 40
```

**Benchmark performance:**
```bash
python blue.py http://localhost:8100/ world 283 240 test.png --benchmark
```

---

## 🐍 Python API

### BlueMap3DRenderer

The main entry point for programmatic rendering.

```python
from bluerender import BlueMap3DRenderer

renderer = BlueMap3DRenderer(
    base_url="http://localhost:8100/",
    use_gpu=True  # Set False to force software rendering
)
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `maps` | `dict` | Available maps on the server |
| `use_gpu` | `bool` | Whether GPU rendering is active |

#### Methods

##### `capture()`

Renders a 3D view and returns a PIL Image.

```python
image = renderer.capture(
    map_id="world",           # Map to render
    center_x=283.0,           # World X coordinate
    center_z=240.0,           # World Z coordinate
    radius=3,                 # Tile radius
    width=1920,               # Image width
    height=1080,              # Image height
    camera_distance=200.0,    # Camera distance
    camera_angle=45.0,        # Vertical angle (degrees)
    camera_rotation=45.0,     # Horizontal rotation (degrees)
    fov=60.0,                 # Field of view
    sunlight_strength=1.0,    # Sun intensity
    ambient_light=0.2,        # Ambient intensity
    perspective=True,         # True=perspective, False=ortho
    output_path="output.png", # Optional save path
    void_color=(20, 20, 30),  # Background RGB
)
```

---

### Low-Level Components

For advanced use cases, you can access the internal components directly:

#### Geometry Parsing

```python
from bluerender import parse_prbm

# Parse raw PRBM data
with open("tile.prbm", "rb") as f:
    geometry = parse_prbm(f.read())

print(f"Vertices: {geometry.num_vertices}")
print(f"Triangles: {geometry.num_triangles}")
print(f"Material Groups: {len(geometry.groups)}")
```

#### Data Models

```python
from bluerender import PRBMGeometry, TextureAtlas, TextureInfo

# PRBMGeometry contains:
# - position: (N, 3) float32 vertex positions
# - normal: (N, 3) int8 vertex normals
# - color: (N, 3) uint8 vertex colors
# - uv: (N, 2) float32 texture coordinates
# - ao: (N,) uint8 ambient occlusion
# - blocklight: (N,) int8 block light levels
# - sunlight: (N,) int8 sun light levels
# - groups: List[MaterialGroup] for texture mapping
```

## 🔧 Technical Details
Rendering Backends

BlueRender supports three rendering backends with automatic fallback:

#### 1. GPU Renderer (`gpu_renderer.py`)
- **Requires**: `moderngl` package
- **Method**: OpenGL shaders with hardware acceleration
- **Best for**: Systems with OpenGL 3.3+ support
- **Performance**: Fastest for high resolutions and complex scenes

#### 2. Fast Software Renderer (`fast_software_renderer.py`)
- **Requires**: `numba` package  
- **Method**: Numba JIT-compiled rasterization
- **Best for**: Headless servers, Docker, systems without GPU/OpenGL
- **Performance**: Near-GPU speeds after initial JIT warmup
- **Warmup**: First render ~2-3s slower due to compilation, subsequent renders are fast

#### 3. Standard Software Renderer (`software_renderer.py`)
- **Requires**: Only `numpy` (always available)
- **Method**: Pure Python/NumPy rasterization
- **Best for**: Maximum compatibility
- **Performance**: Slowest but guaranteed to work everywhere

**Selection Priority:**
```python
if moderngl_available and not args.software:
    use GPU renderer
elif numba_available and not args.force_slow:
    use Fast Software renderer (JIT-compiled)
else:
    use Standard Software renderer (pure Python)
```

### Texture Caching System

BlueRender implements an intelligent persistent disk cache to dramatically speed up repeated renders:

#### How It Works

1. **First Run**: Textures are decoded from base64 PNG data (slow)
   - Textures are quantized using `imagequant` (pngquant algorithm) or PIL fallback
   - Saved as compressed numpy arrays (`.npz`) in `~/.cache/bluerender/textures/`
   - Cache key is a SHA-256 hash of texture data (automatic invalidation)

2. **Subsequent Runs**: Textures are loaded directly from cache (fast)
   - ~10-50x faster than decoding from base64 PNG
   - Cache automatically invalidated when BlueMap updates textures

#### Cache Benefits

- **Faster Startup**: First texture load ~2-5s → subsequent loads ~0.1-0.2s
- **Smaller Cache Size**: Quantization reduces cache file size by 40-60%
- **Automatic Management**: Old cache files cleaned up when textures change
- **No Configuration**: Works automatically, no user intervention needed

#### Cache Location

- **Linux/Mac**: `~/.cache/bluerender/textures/`
- **Windows**: `C:\Users\<username>\.cache\bluerender\textures\`

#### Quantization Quality

| Method | Quality | Compression | Availability |
|--------|---------|-------------|--------------|
| `imagequant` | Excellent (pngquant algorithm) | 40-60% smaller | Requires `pip install imagequant` |
| PIL fallback | Good (median cut) | 20-30% smaller | Always available |

### PRBM Format

BlueRender parses BlueMap's **PRBM** (Packed Renderable Binary Mesh) format — a variant of PRWM designed for web delivery:

- **Header (8 bytes)**: Version, flags, vertex/index counts
- **Attributes**: Position, normal, color, UV, AO, lighting data
- **Material Groups**: Texture assignments for triangle ranges

### Rendering Pipeline

1. **Tile Discovery** — Calculate tile coordinates from world position
2. **Data Fetching** — HTTP requests with gzip decompression
3. **Geometry Parsing** — PRBM binary → numpy arrays
4. **Texture Loading** — Base64 PNG → RGBA arrays
5. ****Numba JIT compilation** (fast software renderer only - adds ~2-3s on first run)
   - Initial cache population
3. **Subsequent runs benefit from**:
   - HTTP session caching and keep-alive connections
   - **JIT-compiled code** (Numba functions already compiled and cached)
   - Operating system disk/memory caches

**Numba JIT Warmup Example:**
```bash
# First run with fast software renderer (cold start)
python blue.py http://localhost:8100/ world 0 0 test1.png --software --benchmark
# Output: Total: 3.45s (includes ~2s Numba compilation)

# Second run (warmed up)
python blue.py http://localhost:8100/ world 0 0 test2.png --software --benchmark
# Output: Total: 1.23s (no compilation overhead)
```
The GPU renderer uses custom GLSL shaders that replicate BlueMap's browser rendering:

- **Directional AO** — Angle-based ambient occlusion
- **Distance-Aware Shading** — Smoother AO at close distances
- **Blended Lighting** — Sun/block light interpolation

---

## 🎯 Performance

BlueRender includes built-in timing analysis. Use the `--benchmark` flag to see detailed performance breakdowns:

```bash
python blue.py http://localhost:8100/ world 283 240 output.png --benchmark
```

This will show:
- **Total time**: End-to-end execution
- **Render time**: Actual rendering duration
- **Breakdown**: Tiles loading, texture loading, rendering, and image saving

### Running Benchmarks

⚠️ **Important**: For accurate performance measurements:

1. **Run multiple iterations** (3-5 times minimum) and calculate the average
2. **First run may be slower** due to:
   - HTTP session establishment
   - Numba JIT compilation (software rendering)
   - Initial cache population
3. **Subsequent runs benefit from**:
   - HTTP session caching and keep-alive connections
   - JIT-compiled code (already warmed up)
   - Operating system disk/memory caches

**Example benchmark workflow:**
```bash
# Run 1: Cold start
python blue.py http://localhost:8100/ world 283 240 test1.png --benchmark
```

### Example Performance Metrics

| Mode | Resolution | Tiles | Time* |
|------|------------|-------|-------|
| GPU | 1920×1080 | 49 (r=3) | 1.30s |
| GPU | 3840×2160 | 121 (r=5) | 2.34s |
| Software (Numba) | 1920×1080 | 49 (r=3) | 1.23s |
| Software (Numba) | 800×600 | 9 (r=1) | 0.53s |

*Average times from 5 runs (excluding first cold start). Results vary based on hardware, network latency, server response time, and Numba JIT availability.

**Benchmark Hardware:**
- **CPU:** Intel i5-10400 (12) @ 2.903GHz
- **GPU:** Intel(R) UHD Graphics 630
- **Network:** Local BlueMap server (minimal latency)

**Benchmark Methodology:**
- Each benchmark represents the average of 5 consecutive runs
- First "cold start" run excluded from averages
- HTTP session caching enabled (realistic production scenario)
- Times include tile fetching, parsing, rendering, and image saving

---

## 📄 License

This project is licensed under the MIT License.

---

## 🙏 Acknowledgments

- [BlueMap](https://github.com/BlueMap-Minecraft/BlueMap) — The amazing Minecraft mapping tool
- [ModernGL](https://github.com/moderngl/moderngl) — Modern OpenGL bindings for Python
- [Pillow](https://python-pillow.org/) — Python Imaging Library

---

<div align="center">

**Made with 💙 for the Minecraft community**

</div>
