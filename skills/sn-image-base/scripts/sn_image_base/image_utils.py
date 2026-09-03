from __future__ import annotations

import base64
import binascii
import io
import os
import tempfile
from pathlib import Path

import httpx
from PIL import Image

MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MIME_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def _bounded(raw: bytes) -> bytes:
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MiB limit.")
    return raw


def read_image_source(source: str | bytes | Path) -> bytes:
    """Read a bounded local, Data URL, or HTTP(S) image source."""
    if isinstance(source, bytes):
        return _bounded(source)
    value = str(source)
    if value.startswith("data:image/"):
        marker = ";base64,"
        if marker not in value:
            raise ValueError("Image Data URL must use base64 encoding.")
        try:
            return _bounded(base64.b64decode(value.split(marker, 1)[1], validate=True))
        except binascii.Error as exc:
            raise ValueError("Image Data URL contains invalid base64 data.") from exc
    if value.startswith(("https://", "http://")):
        data = bytearray()
        with httpx.stream("GET", value, timeout=30.0, follow_redirects=True) as response:
            response.raise_for_status()
            if int(response.headers.get("content-length", "0") or 0) > MAX_IMAGE_BYTES:
                raise ValueError("Remote image exceeds the download limit.")
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_IMAGE_BYTES:
                    raise ValueError("Remote image exceeds the download limit.")
        return bytes(data)
    path = Path(value).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Image file not found: {path}")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MiB limit.")
    return path.read_bytes()


def validate_image_bytes(raw: bytes) -> str:
    """Validate encoded image bytes and return their MIME type."""
    _bounded(raw)
    with Image.open(io.BytesIO(raw)) as image:
        width, height = image.size
        image_format = (image.format or "").upper()
        if width * height > MAX_IMAGE_PIXELS:
            raise ValueError(f"Image exceeds the {MAX_IMAGE_PIXELS:,}-pixel limit.")
        image.verify()
    mime = Image.MIME.get(image_format)
    if mime not in MIME_SUFFIX:
        raise ValueError(f"Unsupported image format: {image_format or 'unknown'}")
    return mime


def normalize_for_model(raw: bytes) -> tuple[str, bytes]:
    """Keep PNG/JPEG inputs and convert other supported images to PNG."""
    mime = validate_image_bytes(raw)
    if mime in {"image/png", "image/jpeg"}:
        return mime, raw
    with Image.open(io.BytesIO(raw)) as image:
        buffer = io.BytesIO()
        image.convert("RGBA" if "A" in image.getbands() else "RGB").save(buffer, format="PNG")
    normalized = buffer.getvalue()
    validate_image_bytes(normalized)
    return "image/png", normalized


def save_image_bytes(raw: bytes, save_path: Path) -> Path:
    """Validate and atomically save image bytes with a format-correct suffix."""
    mime = validate_image_bytes(raw)
    final_path = save_path.with_suffix(MIME_SUFFIX[mime])
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=final_path.parent,
            prefix=f".{final_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(raw)
            temporary.flush()
            os.fsync(temporary.fileno())
            temp_path = Path(temporary.name)
        temp_path.replace(final_path)
        return final_path
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def validate_image_file(path: Path) -> str:
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MiB limit.")
    return validate_image_bytes(path.read_bytes())
