"""
Image Manager utilities for the Strands PPT generator.
Provides robust image download, caching, resizing, format normalization and placeholder generation.
"""
from typing import Optional, Tuple
import io
import requests

# Pillow import is optional at module load-time; functions will raise if not available
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None


def fetch_image_bytes(url: str, s3_client=None, timeout: int = 10) -> Optional[bytes]:
    """Fetch raw image bytes from S3 or HTTP. Returns bytes or None on failure.

    - Supports s3://bucket/key and standard HTTP(S) URLs.
    - Does not raise; returns None on any failure.
    """
    try:
        if not url:
            return None

        # S3 URL
        if url.startswith('s3://') and s3_client is not None:
            try:
                parts = url[5:].split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
                resp = s3_client.get_object(Bucket=bucket, Key=key)
                return resp['Body'].read()
            except Exception:
                # fall back to None
                return None

        # Handle typical s3.amazonaws.com URLs by trying HTTP GET
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            return None

        return None
    except Exception:
        return None


def get_image_size_from_bytes(img_bytes: bytes) -> Optional[Tuple[int, int]]:
    """Return (width, height) from raw image bytes using Pillow, or None if Pillow not available or image invalid."""
    if not img_bytes:
        return None
    if Image is None:
        return None

    try:
        bio = io.BytesIO(img_bytes)
        with Image.open(bio) as im:
            return im.width, im.height
    except Exception:
        return None


def resize_image_bytes(img_bytes: bytes, max_width: int, max_height: int, fmt: str = 'PNG') -> Optional[bytes]:
    """Resize image bytes to fit within max_width/max_height preserving aspect ratio and return bytes in `fmt`.
    Returns None if operation fails or Pillow is not available.
    """
    if not img_bytes or Image is None:
        return None
    try:
        bio = io.BytesIO(img_bytes)
        with Image.open(bio) as im:
            im = im.convert('RGB')
            w, h = im.size
            scale = min(max_width / w, max_height / h, 1.0)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            if scale < 1.0:
                im = im.resize((new_w, new_h), Image.LANCZOS)

            out = io.BytesIO()
            im.save(out, format=fmt)
            return out.getvalue()
    except Exception:
        return None


def create_placeholder_image(text: str = 'Image not available', size: Tuple[int, int] = (1280, 720),
                             bg_color: Tuple[int, int, int] = (245, 247, 250),
                             text_color: Tuple[int, int, int] = (108, 117, 125)) -> Optional[bytes]:
    """Create a simple, professional-looking placeholder PNG and return bytes.
    Requires Pillow.
    """
    if Image is None or ImageDraw is None:
        return None

    try:
        im = Image.new('RGB', size, color=bg_color)
        draw = ImageDraw.Draw(im)

        # Choose a default font if available
        try:
            font = ImageFont.truetype('DejaVuSans-Bold.ttf', 36)
        except Exception:
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None

        # compute text size robustly (Pillow 12 removed textsize)
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            except Exception:
                # fallback to font.getsize or older draw.textsize if available
                try:
                    w, h = font.getsize(text) if font else draw.textsize(text)
                except Exception:
                    try:
                        w, h = draw.textsize(text, font=font)
                    except Exception:
                        # last resort: estimate
                        w = int(size[0] * 0.6)
                        h = 36

            x = (size[0] - w) // 2
            y = (size[1] - h) // 2
            draw.text((x, y), text, fill=text_color, font=font)

        out = io.BytesIO()
        im.save(out, format='PNG')
        return out.getvalue()
    except Exception:
        return None
