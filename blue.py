"""
BlueMap 3D Renderer - Renders hires tiles directly without a browser.
CLI entry point for BlueMap 3D capture.
"""

import argparse

from bluerender import (
    BlueMap3DRenderer,
    PRBMGeometry,
    TextureInfo,
    TextureAtlas,
    parse_prbm,
)
from bluerender.core import RenderDefaults, configure_logging

__all__ = [
    "BlueMap3DRenderer",
    "PRBMGeometry",
    "TextureInfo",
    "TextureAtlas",
    "parse_prbm",
    "main",
]


def main():
    """CLI for 3D BlueMap capture."""
    args = parse_args()
    configure_logging(args.verbose)

    renderer = BlueMap3DRenderer(args.url, use_gpu=not args.software)

    print_capture_info(args, renderer)

    renderer.capture(
        map_id=args.map,
        center_x=args.x,
        center_z=args.z,
        radius=args.radius,
        width=args.width,
        height=args.height,
        camera_distance=args.distance,
        camera_angle=args.angle,
        camera_rotation=args.rotation,
        fov=args.fov,
        sunlight_strength=args.sunlight,
        ambient_light=args.ambient,
        perspective=not args.ortho,
        output_path=args.output,
    )

    print(f"Done! Saved to {args.output}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Capture 3D BlueMap views directly (no browser required)"
    )

    # Required arguments
    parser.add_argument("url", help="BlueMap server URL")
    parser.add_argument("map", help="Map ID (e.g., world)")
    parser.add_argument("x", type=float, help="Center X coordinate")
    parser.add_argument("z", type=float, help="Center Z coordinate")
    parser.add_argument("output", help="Output image path")

    # Optional arguments
    parser.add_argument(
        "-r",
        "--radius",
        type=int,
        default=RenderDefaults.TILE_RADIUS,
        help=f"Tile radius to load (default: {RenderDefaults.TILE_RADIUS})",
    )
    parser.add_argument(
        "-W",
        "--width",
        type=int,
        default=RenderDefaults.WIDTH,
        help=f"Image width (default: {RenderDefaults.WIDTH})",
    )
    parser.add_argument(
        "-H",
        "--height",
        type=int,
        default=RenderDefaults.HEIGHT,
        help=f"Image height (default: {RenderDefaults.HEIGHT})",
    )
    parser.add_argument(
        "-d",
        "--distance",
        type=float,
        default=RenderDefaults.CAMERA_DISTANCE,
        help=f"Camera distance (default: {RenderDefaults.CAMERA_DISTANCE})",
    )
    parser.add_argument(
        "-a",
        "--angle",
        type=float,
        default=RenderDefaults.CAMERA_ANGLE,
        help=f"Camera vertical angle (default: {RenderDefaults.CAMERA_ANGLE})",
    )
    parser.add_argument(
        "--rotation",
        type=float,
        default=RenderDefaults.CAMERA_ROTATION,
        help=f"Camera horizontal rotation (default: {RenderDefaults.CAMERA_ROTATION})",
    )
    parser.add_argument(
        "--fov",
        type=float,
        default=RenderDefaults.FOV,
        help=f"Field of view (default: {RenderDefaults.FOV})",
    )
    parser.add_argument(
        "--sunlight",
        type=float,
        default=RenderDefaults.SUNLIGHT_STRENGTH,
        help=f"Sunlight strength 0-1 (default: {RenderDefaults.SUNLIGHT_STRENGTH})",
    )
    parser.add_argument(
        "--ambient",
        type=float,
        default=RenderDefaults.AMBIENT_LIGHT,
        help=f"Ambient light 0-1 (default: {RenderDefaults.AMBIENT_LIGHT})",
    )
    parser.add_argument(
        "--ortho",
        action="store_true",
        help="Use orthographic projection",
    )
    parser.add_argument(
        "--software",
        action="store_true",
        help="Force software rendering",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def print_capture_info(args: argparse.Namespace, renderer: BlueMap3DRenderer) -> None:
    """Print capture configuration summary."""
    print("Capturing 3D BlueMap view...")
    print(f"  Map: {args.map}")
    print(f"  Center: ({args.x}, {args.z})")
    print(f"  Radius: {args.radius} tiles")
    print(
        f"  Camera: distance={args.distance}, "
        f"angle={args.angle}°, rotation={args.rotation}°"
    )
    print(f"  Rendering: {'GPU' if renderer.use_gpu else 'Software'}")


if __name__ == "__main__":
    main()
