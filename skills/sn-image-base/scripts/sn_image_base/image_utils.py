from __future__ import annotations

import base64
import binascii
import io
import ipaddress
import os
import socket
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from PIL import Image

MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MIME_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
OUTPUT_FORMAT_MIME = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def _bounded(raw: bytes) -> bytes:
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MiB limit.")
    return raw


def decode_bounded_base64(value: str) -> bytes:
    """Reject oversized encoded input before allocating its decoded payload."""
    max_encoded_bytes = ((MAX_IMAGE_BYTES + 2) // 3) * 4
    if len(value) > max_encoded_bytes:
        raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MiB limit.")
    try:
        return _bounded(base64.b64decode(value, validate=True))
    except binascii.Error as exc:
        raise ValueError("Image contains invalid base64 data.") from exc


def require_public_http_url(value: str) -> tuple[str, dict[str, str], dict[str, str]]:
    """Resolve a public URL once and return an IP-bound request target."""
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Remote image must use a public HTTP(S) URL.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Remote image host could not be resolved.") from exc
    resolved = [ipaddress.ip_address(address[4][0]) for address in addresses]
    if not resolved or any(not address.is_global for address in resolved):
        raise ValueError("Remote image URL must resolve only to public IP addresses.")
    address = str(resolved[0])
    connect_host = f"[{address}]" if ":" in address else address
    original_host = parsed.hostname
    host_header = f"[{original_host}]" if ":" in original_host else original_host
    if parsed.port is not None:
        connect_host = f"{connect_host}:{parsed.port}"
        host_header = f"{host_header}:{parsed.port}"
    connect_url = urlunsplit(
        (parsed.scheme, connect_host, parsed.path, parsed.query, "")
    )
    return (
        connect_url,
        {"Host": host_header},
        {"sni_hostname": original_host},
    )


def read_image_source(source: str | bytes | Path) -> bytes:
    """Read a bounded local, Data URL, or HTTP(S) image source."""
    if isinstance(source, bytes):
        return _bounded(source)
    value = str(source)
    if value.startswith("data:image/"):
        marker = ";base64,"
        if marker not in value:
            raise ValueError("Image Data URL must use base64 encoding.")
        return decode_bounded_base64(value.split(marker, 1)[1])
    if value.startswith(("https://", "http://")):
        current_url = value
        for _redirect in range(6):
            connect_url, headers, extensions = require_public_http_url(current_url)
            data = bytearray()
            with httpx.Client(
                timeout=30.0, follow_redirects=False, trust_env=False
            ) as client:
                with client.stream(
                    "GET",
                    connect_url,
                    headers=headers,
                    extensions=extensions,
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            response.raise_for_status()
                        current_url = urljoin(current_url, location)
                        continue
                    response.raise_for_status()
                    if (
                        int(response.headers.get("content-length", "0") or 0)
                        > MAX_IMAGE_BYTES
                    ):
                        raise ValueError("Remote image exceeds the download limit.")
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_IMAGE_BYTES:
                            raise ValueError("Remote image exceeds the download limit.")
                    return bytes(data)
        raise ValueError("Remote image exceeded the redirect limit.")
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


def save_image_bytes(
    raw: bytes,
    save_path: Path,
    output_format: str | None = None,
) -> Path:
    """Validate, optionally transcode, and atomically save image bytes."""
    mime = validate_image_bytes(raw)
    if output_format is not None:
        requested_mime = OUTPUT_FORMAT_MIME.get(output_format)
        if requested_mime is None:
            raise ValueError(f"Unsupported output format: {output_format}")
        if mime != requested_mime:
            with Image.open(io.BytesIO(raw)) as image:
                has_alpha = "A" in image.getbands() or "transparency" in image.info
                mode = "RGBA" if has_alpha and output_format != "jpeg" else "RGB"
                converted = io.BytesIO()
                save_options = {"lossless": True} if output_format == "webp" else {}
                image.convert(mode).save(
                    converted,
                    format={"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[
                        output_format
                    ],
                    **save_options,
                )
            raw = converted.getvalue()
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
