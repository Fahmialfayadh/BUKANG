import io
from PIL import Image, ImageOps

def compress_image(image_input, max_size: int = 1080, quality: int = 80) -> bytes:
    """
    Compresses input image (file-like object or bytes) to max dimension max_size,
    fixes EXIF rotation from mobile cameras, converts to RGB JPEG format,
    and returns compressed JPEG bytes.
    """
    if isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input))
    else:
        img = Image.open(image_input)

    # 1. Correct EXIF orientation (mobile camera photos often store orientation in EXIF tags)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # 2. Resize maintaining aspect ratio
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    # 3. Convert RGBA/P to RGB for standard JPEG compatibility
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # 4. Save to buffer with specified JPEG quality
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

def get_image_size_kb(image_bytes: bytes) -> float:
    """Returns size of image bytes in KB."""
    return round(len(image_bytes) / 1024.0, 2)
