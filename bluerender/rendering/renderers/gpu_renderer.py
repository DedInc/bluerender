"""
GPU renderer using ModernGL.

Optimized for batch rendering with material grouping.
"""

import logging
from typing import Dict, List, Optional, Any

from PIL import Image

from bluerender.core import TileGeometry, CameraConfig, RenderSettings, TextureAtlas
from ..utils.math_utils import create_mvp_matrix
from ..rasterization.shaders import VERTEX_SHADER, FRAGMENT_SHADER
from ..core.batching import batch_geometry_by_material, BatchedVertexData

try:
    import moderngl

    MODERNGL_AVAILABLE = True
except ImportError:
    moderngl = None
    MODERNGL_AVAILABLE = False


class GPURenderer:
    """
    OpenGL-based renderer using ModernGL.

    Optimized with batched rendering - all geometry with the same material
    is merged and drawn in a single call.
    """

    def __init__(self):
        self.ctx: Optional[Any] = None
        self.prog: Optional[Any] = None
        self._initialized = False
        self._gpu_textures: Dict[int, Any] = {}

    @property
    def available(self) -> bool:
        return MODERNGL_AVAILABLE

    def initialize(self) -> bool:
        """Initialize OpenGL context and shaders."""
        if self._initialized:
            return True

        if not MODERNGL_AVAILABLE:
            logging.warning("ModernGL not available")
            return False

        try:
            self.ctx = moderngl.create_standalone_context()
            self.prog = self.ctx.program(
                vertex_shader=VERTEX_SHADER,
                fragment_shader=FRAGMENT_SHADER,
            )
            self._initialized = True
            logging.info("GPU rendering initialized")
            return True
        except Exception as e:
            logging.warning(f"GPU init failed: {e}")
            return False

    def render(
        self,
        geometries: List[TileGeometry],
        camera: CameraConfig,
        settings: RenderSettings,
        texture_atlas: Optional[TextureAtlas] = None,
    ) -> Image.Image:
        """Render scene using GPU with batched geometry."""
        if not self._initialized:
            raise RuntimeError("GPU renderer not initialized")

        fbo = self._create_framebuffer(settings)
        self._setup_render_state(camera, settings)
        self._ensure_textures_uploaded(texture_atlas)

        try:
            batched = batch_geometry_by_material(geometries)
            self._render_batched(batched)
            return self._read_framebuffer(fbo, settings)
        finally:
            fbo.release()

    def _render_batched(self, batched: Dict[int, BatchedVertexData]) -> None:
        """Render all batched geometry with one draw call per material."""
        for mat_idx, vertex_data in batched.items():
            self._bind_texture(mat_idx)
            self._draw_batched(vertex_data)

    def _bind_texture(self, mat_idx: int) -> None:
        """Bind texture for material or disable texturing."""
        if mat_idx >= 0 and mat_idx in self._gpu_textures:
            gpu_tex = self._gpu_textures[mat_idx]
            if gpu_tex is not None:
                gpu_tex.use(0)
                self.prog["textureImage"].value = 0
                self.prog["useTexture"].value = True
            else:
                self.prog["useTexture"].value = False
        else:
            self.prog["useTexture"].value = False

    def _draw_batched(self, vertex_data: BatchedVertexData) -> None:
        """Create VAO and draw batched vertices."""
        buffers = self._create_buffers(vertex_data)
        vao = self.ctx.vertex_array(
            self.prog,
            [
                (buffers["position"], "3f", "in_position"),
                (buffers["normal"], "3f", "in_normal"),
                (buffers["color"], "3f", "in_color"),
                (buffers["uv"], "2f", "in_uv"),
                (buffers["ao"], "1f", "in_ao"),
                (buffers["sunlight"], "1f", "in_sunlight"),
                (buffers["blocklight"], "1f", "in_blocklight"),
            ],
        )

        vao.render()

        vao.release()
        for buf in buffers.values():
            buf.release()

    def _create_buffers(self, vertex_data: BatchedVertexData) -> Dict[str, Any]:
        """Create GPU buffers from vertex data."""
        return {
            "position": self.ctx.buffer(vertex_data.positions.tobytes()),
            "normal": self.ctx.buffer(vertex_data.normals.tobytes()),
            "color": self.ctx.buffer(vertex_data.colors.tobytes()),
            "uv": self.ctx.buffer(vertex_data.uvs.tobytes()),
            "ao": self.ctx.buffer(vertex_data.ao.tobytes()),
            "sunlight": self.ctx.buffer(vertex_data.sunlight.tobytes()),
            "blocklight": self.ctx.buffer(vertex_data.blocklight.tobytes()),
        }

    def _ensure_textures_uploaded(self, texture_atlas: Optional[TextureAtlas]) -> None:
        """Upload all textures to GPU (cached across renders)."""
        if texture_atlas is None:
            return

        for i, tex_info in enumerate(texture_atlas.textures):
            if i in self._gpu_textures:
                continue

            if tex_info.image is not None:
                tex = self.ctx.texture(
                    (tex_info.image.shape[1], tex_info.image.shape[0]),
                    4,
                    tex_info.image.tobytes(),
                )
                tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
                tex.repeat_x = True
                tex.repeat_y = True
                self._gpu_textures[i] = tex
            else:
                self._gpu_textures[i] = None

    def _create_framebuffer(self, settings: RenderSettings) -> Any:
        """Create and bind framebuffer."""
        fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.texture((settings.width, settings.height), 4)],
            depth_attachment=self.ctx.depth_texture((settings.width, settings.height)),
        )
        fbo.use()
        fbo.clear(*settings.void_color_normalized, 1.0, 1.0)
        return fbo

    def _setup_render_state(
        self, camera: CameraConfig, settings: RenderSettings
    ) -> None:
        """Configure OpenGL state and uniforms."""
        mvp = create_mvp_matrix(camera, settings)

        self.prog["mvp"].write(mvp.T.tobytes())
        self.prog["sunlightStrength"].value = settings.sunlight_strength
        self.prog["ambientLight"].value = settings.ambient_light
        self.prog["cameraDistance"].value = camera.distance

        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

    def _read_framebuffer(self, fbo: Any, settings: RenderSettings) -> Image.Image:
        """Read framebuffer to PIL Image."""
        data = fbo.read(components=3)
        image = Image.frombytes("RGB", (settings.width, settings.height), data)
        return image.transpose(Image.FLIP_TOP_BOTTOM)
