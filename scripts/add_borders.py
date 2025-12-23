#!/usr/bin/env python3
"""Add hand-drawn borders to images (posters, profile photos, etc.).

Takes image files and adds randomly selected borders from an SVG template.
Images are automatically cropped to square and resized if needed.

Usage:
    # Process individual files
    python add_borders.py image1.png image2.jpg output_dir/

    # Process directory of images
    python add_borders.py input_dir/ output_dir/

    # With face detection for smart cropping
    python add_borders.py photo.png output_dir/ --face
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

# Maximum dimension for input images (larger images are resized)
MAX_INPUT_DIMENSION = 1000


def resize_to_max_dimension(img: Image.Image, max_size: int = MAX_INPUT_DIMENSION) -> Image.Image:
    """Resize image so max dimension is max_size, preserving aspect ratio.

    If the image is already smaller than max_size in both dimensions,
    it is returned unchanged.

    Args:
        img: PIL Image to resize
        max_size: Maximum allowed dimension (default 1000px)

    Returns:
        Resized image (or original if already small enough)
    """
    width, height = img.size
    if max(width, height) <= max_size:
        return img

    if width > height:
        new_width = max_size
        new_height = int(height * (max_size / width))
    else:
        new_height = max_size
        new_width = int(width * (max_size / height))

    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def get_face_detector():
    """Get or create a mediapipe face detector (cached)."""
    if not hasattr(get_face_detector, '_detector'):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        import urllib.request
        import os

        # Download the face detection model if not present
        model_path = Path(__file__).parent / 'blaze_face_short_range.tflite'
        if not model_path.exists():
            url = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
            print(f"    Downloading face detection model...")
            urllib.request.urlretrieve(url, str(model_path))

        # Create face detector
        base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
        options = vision.FaceDetectorOptions(base_options=base_options)
        get_face_detector._detector = vision.FaceDetector.create_from_options(options)

    return get_face_detector._detector


def crop_to_square(img: Image.Image, use_face_detection: bool = False) -> Image.Image:
    """Crop image to square, centered on face (if requested) or image center.

    The crop size is the minimum of width and height (no upscaling).

    Args:
        img: PIL Image to crop
        use_face_detection: If True, use mediapipe to detect face and center
                           crop on it. Falls back to center if no face found.

    Returns:
        Square-cropped image
    """
    width, height = img.size
    if width == height:
        return img

    crop_size = min(width, height)

    # Default to center crop
    center_x, center_y = width // 2, height // 2

    if use_face_detection:
        try:
            import mediapipe as mp

            # Convert to RGB for mediapipe
            img_rgb = img.convert('RGB')

            # Save to temp file for mediapipe (it needs a file path or specific format)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                img_rgb.save(tmp.name)
                mp_image = mp.Image.create_from_file(tmp.name)

            try:
                detector = get_face_detector()
                result = detector.detect(mp_image)

                if result.detections:
                    # Get first face bounding box (in pixels)
                    bbox = result.detections[0].bounding_box
                    center_x = bbox.origin_x + bbox.width // 2
                    center_y = bbox.origin_y + bbox.height // 2
                    print(f"    Face detected at ({center_x}, {center_y})")
                else:
                    print("    No face detected, using center crop")
            finally:
                Path(tmp.name).unlink(missing_ok=True)

        except ImportError:
            print("    Warning: mediapipe not installed, using center crop")
        except Exception as e:
            print(f"    Warning: Face detection failed ({e}), using center crop")

    # Calculate crop bounds, ensuring we stay within image boundaries
    left = max(0, min(center_x - crop_size // 2, width - crop_size))
    top = max(0, min(center_y - crop_size // 2, height - crop_size))

    return img.crop((left, top, left + crop_size, top + crop_size))


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


def collect_image_files(inputs: list) -> list:
    """Collect all image files from a list of files and directories.

    Args:
        inputs: List of Path objects (files or directories)

    Returns:
        List of image file paths (PNG, JPG, JPEG)
    """
    image_extensions = {'.png', '.jpg', '.jpeg'}
    image_files = []

    for input_path in inputs:
        if input_path.is_file():
            if input_path.suffix.lower() in image_extensions:
                image_files.append(input_path)
            else:
                print(f"  Skipping non-image file: {input_path}")
        elif input_path.is_dir():
            for ext in image_extensions:
                image_files.extend(input_path.glob(f'*{ext}'))
                image_files.extend(input_path.glob(f'*{ext.upper()}'))

    # Remove duplicates and sort
    image_files = sorted(set(image_files))
    return image_files


def process_images(
    inputs: list,
    output_dir: Path,
    svg_path: Path,
    output_size: int = OUTPUT_SIZE,
    use_face_detection: bool = False
) -> None:
    """Process images, adding borders after optional crop and resize.

    Args:
        inputs: List of input files or directories
        output_dir: Directory to save output files
        svg_path: Path to SVG file with border designs
        output_size: Size of output images (square)
        use_face_detection: Use face detection for centering crops
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

    # Collect all image files from inputs
    image_files = collect_image_files(inputs)
    if not image_files:
        print("No image files found to process.")
        return

    print(f"\nProcessing {len(image_files)} images...")
    if use_face_detection:
        print("  (Face detection enabled)")

    for img_path in image_files:
        print(f"  Processing {img_path.name}...")

        # Load image
        img = Image.open(img_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        original_size = img.size

        # Step 1: Crop to square (with optional face detection)
        img = crop_to_square(img, use_face_detection=use_face_detection)
        if original_size[0] != original_size[1]:  # Was not square before
            print(f"    Cropped to {img.size[0]}x{img.size[1]}")

        # Step 2: Resize if larger than max dimension
        pre_resize = img.size
        img = resize_to_max_dimension(img)
        if img.size != pre_resize:
            print(f"    Resized to {img.size[0]}x{img.size[1]}")

        # Step 3: Select random border and composite
        border = random.choice(borders)
        result = add_border_to_image(img, border)

        # Save as PNG (output name based on input, always .png)
        output_name = img_path.stem + '.png'
        output_path = output_dir / output_name
        result.save(output_path, 'PNG', optimize=True)
        print(f"    Saved to {output_path}")

    print(f"\nDone! Processed {len(image_files)} images.")


def main():
    parser = argparse.ArgumentParser(
        description='Add hand-drawn borders to images (posters, profile photos, etc.)'
    )
    parser.add_argument(
        'inputs',
        type=Path,
        nargs='+',
        help='Input PNG/JPG files or directories containing images'
    )
    parser.add_argument(
        'output_dir',
        type=Path,
        help='Directory to save output files'
    )
    parser.add_argument(
        '--face',
        action='store_true',
        help='Use face detection to center crop on detected face'
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

    # Validate inputs exist
    for input_path in args.inputs:
        if not input_path.exists():
            raise FileNotFoundError(f"Input not found: {input_path}")

    if not args.border_svg.exists():
        raise FileNotFoundError(f"Border SVG not found: {args.border_svg}")

    process_images(
        args.inputs,
        args.output_dir,
        args.border_svg,
        args.output_size,
        use_face_detection=args.face
    )


if __name__ == '__main__':
    main()
