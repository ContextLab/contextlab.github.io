#!/usr/bin/env python3
"""Add hand-drawn borders to poster thumbnail images.

Takes PNG images and adds randomly selected borders from an SVG template,
producing output images suitable for the publications page.

Usage:
    python add_poster_borders.py <input_dir> <output_dir> [--border-svg <path>]
"""
import argparse
import random
import subprocess
import tempfile
from pathlib import Path
from PIL import Image
import numpy as np
import io


# Border regions in the SVG (10 borders in a 2x5 grid)
# Each tuple is (x, y, width, height) in SVG coordinates
BORDER_REGIONS = [
    (0, 0, 412.84, 413.86),       # Border 1
    (520, 0, 412.84, 413.86),     # Border 2
    (0, 520, 412.84, 413.86),     # Border 3
    (520, 520, 412.84, 413.86),   # Border 4
    (0, 1040, 412.84, 413.86),    # Border 5
    (520, 1040, 412.84, 413.86),  # Border 6
    (0, 1560, 412.84, 413.86),    # Border 7
    (520, 1560, 412.84, 413.86),  # Border 8
    (0, 2080, 412.84, 413.86),    # Border 9
    (520, 2080, 412.84, 413.86),  # Border 10
]

# Output dimensions (matches Abstracts_Thumbnails*.png)
OUTPUT_SIZE = 500

# Transparent margin around content (matches Abstracts_Thumbnails*.png)
# Content area is approximately 418x419 centered in 500x500
MARGIN = 41

# The content area size (where border + poster go)
CONTENT_SIZE = OUTPUT_SIZE - (2 * MARGIN)  # ~418px

# Border inset - how much the border overlaps the poster edges
# Poster extends to middle of border lines (half the line thickness)
BORDER_INSET = 6


def extract_border_from_svg(svg_path: Path, region_idx: int, output_size: int) -> Image.Image:
    """Extract a single border region from the SVG and render it as PNG.

    Args:
        svg_path: Path to the SVG file containing borders
        region_idx: Index of the border region to extract (0-9)
        output_size: Size of output image (square)

    Returns:
        PIL Image with transparent background and green border
    """
    x, y, w, h = BORDER_REGIONS[region_idx]

    # Use rsvg-convert or Inkscape to render just this region
    # We'll render the full SVG at higher resolution then crop

    # Calculate scale to make border fit output size
    scale = output_size / max(w, h)

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Try using rsvg-convert (from librsvg)
        # Render at scale with the region we want
        full_width = 932.84 * scale
        full_height = 2493.86 * scale

        result = subprocess.run([
            'rsvg-convert',
            '-w', str(int(full_width)),
            '-h', str(int(full_height)),
            '-o', tmp_path,
            str(svg_path)
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"rsvg-convert failed: {result.stderr}")

        # Load and crop to the border region
        full_img = Image.open(tmp_path)

        # Calculate crop coordinates (scaled)
        crop_x = int(x * scale)
        crop_y = int(y * scale)
        crop_w = int(w * scale)
        crop_h = int(h * scale)

        border_img = full_img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))

        # Resize to exact output size
        border_img = border_img.resize((output_size, output_size), Image.Resampling.LANCZOS)

        # Ensure RGBA mode
        if border_img.mode != 'RGBA':
            border_img = border_img.convert('RGBA')

        return border_img

    finally:
        Path(tmp_path).unlink(missing_ok=True)


def flood_fill_outside_border(img: Image.Image, tolerance: int = 50) -> Image.Image:
    """Flood fill from corners, making transparent and white/near-white pixels transparent.

    This removes any white background that leaked outside the border frame.
    The fill propagates through both already-transparent pixels and white pixels.

    Args:
        img: RGBA image to modify
        tolerance: How close to white a pixel must be to be considered "white"

    Returns:
        Modified image with outside areas made transparent
    """
    img = img.copy()
    arr = np.array(img)
    h, w = arr.shape[:2]

    visited = np.zeros((h, w), dtype=bool)

    # Start from all four corners
    stack = [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)]

    while stack:
        cx, cy = stack.pop()
        if cx < 0 or cx >= w or cy < 0 or cy >= h:
            continue
        if visited[cy, cx]:
            continue

        alpha = arr[cy, cx, 3]
        pixel_rgb = arr[cy, cx, :3]

        # Check if pixel is already transparent OR is white/near-white
        is_transparent = alpha < 128
        is_white = all(c >= 255 - tolerance for c in pixel_rgb)

        if is_transparent or is_white:
            visited[cy, cx] = True
            arr[cy, cx, 3] = 0  # Make transparent
            stack.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])

    return Image.fromarray(arr)


def add_border_to_image(
    poster_img: Image.Image,
    border_img: Image.Image,
    content_size: int = CONTENT_SIZE,
    margin: int = MARGIN,
    output_size: int = OUTPUT_SIZE,
    border_inset: int = BORDER_INSET
) -> Image.Image:
    """Composite a poster image with a border overlay.

    The poster is sized to fit inside the border frame, with the border
    overlapping the poster edges slightly.
    Output has transparent margins matching Abstracts_Thumbnails*.png format.

    Args:
        poster_img: The poster image
        border_img: The border image (with transparency)
        content_size: Size of the content area (border + poster)
        margin: Transparent margin around content
        output_size: Final output size
        border_inset: How much the border overlaps poster edges

    Returns:
        Composited image with poster inside border, transparent margins
    """
    # Resize border to match content size
    border_resized = border_img.resize((content_size, content_size), Image.Resampling.LANCZOS)

    # Calculate poster area (smaller than content to fit inside border frame)
    poster_area_size = content_size - (2 * border_inset)

    # Resize poster to fit within the poster area
    poster_aspect = poster_img.width / poster_img.height

    if poster_aspect > 1:
        # Wider than tall - fit to width
        new_width = poster_area_size
        new_height = int(poster_area_size / poster_aspect)
    else:
        # Taller than wide or square - fit to height
        new_height = poster_area_size
        new_width = int(poster_area_size * poster_aspect)

    poster_resized = poster_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Create content area with white background
    content = Image.new('RGBA', (content_size, content_size), (255, 255, 255, 255))

    # Center the poster in content area
    paste_x = (content_size - new_width) // 2
    paste_y = (content_size - new_height) // 2

    # Paste poster
    if poster_resized.mode == 'RGBA':
        content.paste(poster_resized, (paste_x, paste_y), poster_resized)
    else:
        content.paste(poster_resized, (paste_x, paste_y))

    # Overlay the border on top (border overlaps poster edges)
    content = Image.alpha_composite(content, border_resized)

    # Create final output with transparent margins
    output = Image.new('RGBA', (output_size, output_size), (0, 0, 0, 0))

    # Paste content centered in output
    output.paste(content, (margin, margin), content)

    # Flood fill from corners to make outside areas transparent
    # This removes any white that leaked outside the border
    output = flood_fill_outside_border(output, tolerance=50)

    return output


def process_images(
    input_dir: Path,
    output_dir: Path,
    svg_path: Path,
    output_size: int = OUTPUT_SIZE
) -> None:
    """Process all PNG images in input directory, adding borders.

    Args:
        input_dir: Directory containing input PNG files
        output_dir: Directory to save output files
        svg_path: Path to SVG file with border designs
        output_size: Size of output images (square)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-render all borders
    print(f"Loading {len(BORDER_REGIONS)} border designs...")
    borders = []
    for i in range(len(BORDER_REGIONS)):
        try:
            border = extract_border_from_svg(svg_path, i, output_size)
            borders.append(border)
            print(f"  Loaded border {i + 1}")
        except Exception as e:
            print(f"  Warning: Failed to load border {i + 1}: {e}")

    if not borders:
        raise RuntimeError("No borders could be loaded!")

    # Process each PNG in input directory
    png_files = list(input_dir.glob('*.png'))
    print(f"\nProcessing {len(png_files)} images...")

    for png_path in png_files:
        print(f"  Processing {png_path.name}...")

        # Load poster image
        poster = Image.open(png_path)
        if poster.mode != 'RGBA':
            poster = poster.convert('RGBA')

        # Select random border
        border = random.choice(borders)

        # Composite
        result = add_border_to_image(poster, border)

        # Save as RGBA to preserve transparent margins
        output_path = output_dir / png_path.name
        result.save(output_path, 'PNG', optimize=True)
        print(f"    Saved to {output_path}")

    print(f"\nDone! Processed {len(png_files)} images.")


def main():
    parser = argparse.ArgumentParser(
        description='Add hand-drawn borders to poster thumbnail images'
    )
    parser.add_argument(
        'input_dir',
        type=Path,
        help='Directory containing input PNG files'
    )
    parser.add_argument(
        'output_dir',
        type=Path,
        help='Directory to save output files'
    )
    parser.add_argument(
        '--border-svg',
        type=Path,
        default=Path(__file__).parent.parent / 'images' / 'templates' / 'WebsiteDoodles_Posters_v1.svg',
        help='Path to SVG file with border designs'
    )
    parser.add_argument(
        '--output-size',
        type=int,
        default=OUTPUT_SIZE,
        help=f'Output image size in pixels (default: {OUTPUT_SIZE})'
    )

    args = parser.parse_args()

    if not args.input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {args.input_dir}")

    if not args.border_svg.exists():
        raise FileNotFoundError(f"Border SVG not found: {args.border_svg}")

    process_images(args.input_dir, args.output_dir, args.border_svg, args.output_size)


if __name__ == '__main__':
    main()
