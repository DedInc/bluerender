"""
OpenGL shader definitions for GPU rendering.
"""

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
