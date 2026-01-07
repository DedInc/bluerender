"""
GPU renderer using ModernGL.
"""

import logging
from typing import Dict, List, Optional, Any

import numpy as np
from PIL import Image

from bluerender.core import (
    TileGeometry,
    CameraConfig,
    RenderSettings,
    TextureAtlas,
    MaterialGroup,
)
from .math_utils import create_mvp_matrix

# Optional ModernGL import
try:
    import moderngl

    MODERNGL_AVAILABLE = True
except ImportError:
    moderngl = None
    MODERNGL_AVAILABLE = False


# =============================================================================
# Shaders
# =============================================================================

VERTEX_SHADER = """
#version 330

uniform mat4 mvp;
uniform float sunlightStrength;
uniform float ambientLight;
uniform float cameraDistance;

in vec3 in_position;
in vec3 in_normal;
in vec3 in_color;
in vec2 in_uv;
in float in_ao;
in float in_sunlight;
in float in_blocklight;

out vec3 v_color;
out vec2 v_uv;
out float v_ao;
out float v_light;
out vec3 v_normal;

const vec2 lightDirection = normalize(vec2(1.0, 0.5));

void main() {
    gl_Position = mvp * vec4(in_position, 1.0);
    v_color = in_color / 255.0;
    v_uv = in_uv;
    v_normal = in_normal / 127.0;
    
    // Apply directional lighting to AO (matching BlueMap's vertex shader)
    float ao = in_ao / 255.0;
    if (v_normal.y != 0.0 || abs(abs(v_normal.x) - abs(v_normal.z)) != 0.0) {
        float distFac = smoothstep(1000.0, 50.0, cameraDistance);
        ao *= 1.0 - abs(dot(v_normal.xz, lightDirection)) * 0.4 * distFac;
        ao *= 1.0 - max(0.0, -v_normal.y) * 0.6 * distFac;
    }
    v_ao = ao;
    
    // Calculate light (matching BlueMap's formula)
    float light = mix(in_blocklight, max(in_sunlight, in_blocklight), sunlightStrength);
    v_light = mix(ambientLight, 1.0, light / 15.0);
}
"""

FRAGMENT_SHADER = """
#version 330

uniform sampler2D textureImage;
uniform bool useTexture;

in vec3 v_color;
in vec2 v_uv;
in float v_ao;
in float v_light;
in vec3 v_normal;

out vec4 fragColor;

void main() {
    vec4 texColor;
    if (useTexture) {
        texColor = texture(textureImage, v_uv);
        if (texColor.a <= 0.01) discard;
    } else {
        texColor = vec4(1.0, 1.0, 1.0, 1.0);
    }
    
    // Apply vertex color (tinting)
    vec3 color = texColor.rgb * v_color;
    
    // Apply AO
    color *= v_ao;
    
    // Apply lighting
    color *= v_light;
    
    fragColor = vec4(color, texColor.a);
}
"""


class GPURenderer:
    """
    OpenGL-based renderer using ModernGL.

    Falls back gracefully if GPU is unavailable.
    """

    def __init__(self):
        self.ctx: Optional[Any] = None
        self.prog: Optional[Any] = None
        self._initialized = False

    @property
    def available(self) -> bool:
        return MODERNGL_AVAILABLE

    def initialize(self) -> bool:
        """
        Initialize OpenGL context and shaders.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        if not MODERNGL_AVAILABLE:
            logging.warning("ModernGL not available")
            return False

        try:
            self.ctx = moderngl.create_standalone_context()
            self._create_shaders()
            self._initialized = True
            logging.info("GPU rendering initialized")
            return True
        except Exception as e:
            logging.warning(f"GPU init failed: {e}")
            return False

    def _create_shaders(self) -> None:
        """Compile shader program."""
        self.prog = self.ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )

    def render(
        self,
        geometries: List[TileGeometry],
        camera: CameraConfig,
        settings: RenderSettings,
        texture_atlas: Optional[TextureAtlas] = None,
    ) -> Image.Image:
        """
        Render scene using GPU.

        Args:
            geometries: List of tile geometries
            camera: Camera configuration
            settings: Render settings
            texture_atlas: Optional texture atlas

        Returns:
            Rendered PIL Image
        """
        if not self._initialized:
            raise RuntimeError("GPU renderer not initialized")

        fbo = self._create_framebuffer(settings)
        self._setup_render_state(camera, settings)

        gpu_textures: Dict[int, Any] = {}

        try:
            for tile_geom in geometries:
                self._render_geometry(tile_geom, texture_atlas, gpu_textures)

            return self._read_framebuffer(fbo, settings)
        finally:
            self._cleanup(fbo, gpu_textures)

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

    def _render_geometry(
        self,
        tile_geom: TileGeometry,
        texture_atlas: Optional[TextureAtlas],
        gpu_textures: Dict[int, Any],
    ) -> None:
        """Render a single tile geometry."""
        geom = tile_geom.geometry
        if geom.is_empty:
            return

        offset_geom = tile_geom.offset_geometry
        vertex_data = _prepare_vertex_data(offset_geom)

        if geom.groups and texture_atlas and len(texture_atlas) > 0:
            self._render_with_materials(
                offset_geom, vertex_data, geom.groups, texture_atlas, gpu_textures
            )
        else:
            self._render_without_materials(vertex_data)

    def _render_with_materials(
        self,
        geom,
        vertex_data: "_VertexData",
        groups: List[MaterialGroup],
        texture_atlas: TextureAtlas,
        gpu_textures: Dict[int, Any],
    ) -> None:
        """Render geometry with per-material textures."""
        for group in groups:
            if not self._is_valid_group(group, len(geom.position)):
                continue

            gpu_tex = self._get_or_create_texture(
                group.material_index, texture_atlas, gpu_textures
            )
            self._bind_texture(gpu_tex)

            group_data = vertex_data.slice(group.start, group.count)
            self._draw_vertices(group_data)

    def _render_without_materials(self, vertex_data: "_VertexData") -> None:
        """Render geometry with vertex colors only."""
        self.prog["useTexture"].value = False
        self._draw_vertices(vertex_data)

    def _is_valid_group(self, group: MaterialGroup, num_vertices: int) -> bool:
        """Check if material group is valid."""
        return group.count > 0 and group.start < num_vertices

    def _get_or_create_texture(
        self,
        material_index: int,
        texture_atlas: TextureAtlas,
        gpu_textures: Dict[int, Any],
    ) -> Optional[Any]:
        """Get cached GPU texture or create new one."""
        if material_index in gpu_textures:
            return gpu_textures[material_index]

        gpu_tex = None
        if material_index < len(texture_atlas):
            tex_info = texture_atlas.textures[material_index]
            if tex_info.image is not None:
                gpu_tex = self._create_gpu_texture(tex_info.image)

        gpu_textures[material_index] = gpu_tex
        return gpu_tex

    def _create_gpu_texture(self, image_data: np.ndarray) -> Any:
        """Create GPU texture from image data."""
        tex = self.ctx.texture(
            (image_data.shape[1], image_data.shape[0]),
            4,
            image_data.tobytes(),
        )
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        tex.repeat_x = True
        tex.repeat_y = True
        return tex

    def _bind_texture(self, gpu_tex: Optional[Any]) -> None:
        """Bind texture to shader."""
        if gpu_tex is not None:
            gpu_tex.use(0)
            self.prog["textureImage"].value = 0
            self.prog["useTexture"].value = True
        else:
            self.prog["useTexture"].value = False

    def _draw_vertices(self, vertex_data: "_VertexData") -> None:
        """Create VAO and draw vertices."""
        buffers = vertex_data.create_buffers(self.ctx)

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

        # Cleanup
        vao.release()
        for buf in buffers.values():
            buf.release()

    def _read_framebuffer(self, fbo: Any, settings: RenderSettings) -> Image.Image:
        """Read framebuffer to PIL Image."""
        data = fbo.read(components=3)
        image = Image.frombytes("RGB", (settings.width, settings.height), data)
        return image.transpose(Image.FLIP_TOP_BOTTOM)

    def _cleanup(self, fbo: Any, gpu_textures: Dict[int, Any]) -> None:
        """Release GPU resources."""
        for tex in gpu_textures.values():
            if tex is not None:
                tex.release()
        fbo.release()


class _VertexData:
    """Prepared vertex data for GPU upload."""

    def __init__(
        self,
        positions: np.ndarray,
        normals: np.ndarray,
        colors: np.ndarray,
        uvs: np.ndarray,
        ao: np.ndarray,
        sunlight: np.ndarray,
        blocklight: np.ndarray,
    ):
        self.positions = positions
        self.normals = normals
        self.colors = colors
        self.uvs = uvs
        self.ao = ao
        self.sunlight = sunlight
        self.blocklight = blocklight

    def slice(self, start: int, count: int) -> "_VertexData":
        """Extract a slice of vertex data."""
        end = min(start + count, len(self.positions))
        return _VertexData(
            positions=self.positions[start:end],
            normals=self.normals[start:end],
            colors=self.colors[start:end],
            uvs=self.uvs[start:end],
            ao=self.ao[start:end],
            sunlight=self.sunlight[start:end],
            blocklight=self.blocklight[start:end],
        )

    def create_buffers(self, ctx) -> Dict[str, Any]:
        """Create GPU buffers from vertex data."""
        return {
            "position": ctx.buffer(self.positions.astype(np.float32).tobytes()),
            "normal": ctx.buffer(self.normals.tobytes()),
            "color": ctx.buffer(self.colors.tobytes()),
            "uv": ctx.buffer(self.uvs.tobytes()),
            "ao": ctx.buffer(self.ao.tobytes()),
            "sunlight": ctx.buffer(self.sunlight.tobytes()),
            "blocklight": ctx.buffer(self.blocklight.tobytes()),
        }


def _prepare_vertex_data(geom) -> _VertexData:
    """Convert geometry to float32 for shaders."""
    uvs = (
        geom.uv
        if geom.uv is not None
        else np.zeros((len(geom.position), 2), dtype=np.float32)
    )

    return _VertexData(
        positions=geom.position.astype(np.float32),
        normals=geom.normal.astype(np.float32),
        colors=geom.color.astype(np.float32),
        uvs=uvs.astype(np.float32),
        ao=geom.ao.astype(np.float32),
        sunlight=geom.sunlight.astype(np.float32),
        blocklight=geom.blocklight.astype(np.float32),
    )
