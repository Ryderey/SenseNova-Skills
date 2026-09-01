from __future__ import annotations

import asyncio
import base64
import binascii
import mimetypes
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from PIL import Image
from typing_extensions import override

from sn_image_base.configs import global_configs, is_valid_base_url
from sn_image_base.exceptions import InvalidBaseUrlError, MissingApiKeyError
from sn_image_base.generation.core import ensure_output_path
from sn_image_base.generation.core.client_base import (
    DEFAULT_HTTP_REQUEST_TIMEOUT,
    DEFAULT_MAX_CONNECTIONS,
    T2IBaseClient,
)
from sn_image_base.utils.error_utils import U1HttpErrorBase

DEFAULT_RESOLUTION = "2K"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_MODEL = "sensenova-u1.5-lite"
FAST_MODEL = "sensenova-u1-fast"
OUTPUT_DIR = Path(tempfile.gettempdir()) / "sensenova-image"

IMAGE_GEN_ENDPOINT = "/images/generations"
IMAGE_EDIT_ENDPOINT = "/images/edits"
_EXPLICIT_SIZE = re.compile(r"^(\d{3,4})[xX](\d{3,4})$")
_FORMAT_SUFFIX = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}


class SensenovaText2ImageClient(T2IBaseClient):
    """Small async client for SenseNova U1.5 generation and native editing."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        *,
        model: str | None = None,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        timeout: float = DEFAULT_HTTP_REQUEST_TIMEOUT,
        ssl_verify: bool = True,
        **kwargs: Any,
    ) -> None:
        api_key = api_key or global_configs.SN_IMAGE_GEN_API_KEY
        if not api_key:
            raise MissingApiKeyError(global_configs.get_env_var_help("SN_IMAGE_GEN_API_KEY"))
        base_url = base_url or global_configs.SN_IMAGE_GEN_BASE_URL
        if not base_url:
            raise InvalidBaseUrlError(global_configs.get_env_var_help("SN_IMAGE_GEN_BASE_URL"))
        if not is_valid_base_url(base_url):
            raise InvalidBaseUrlError(f"Invalid image API base URL: {base_url}")
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_connections=max_connections,
            timeout=timeout,
            ssl_verify=ssl_verify,
            **kwargs,
        )

    @override
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        *,
        model: str | None = None,
        image_size: str = DEFAULT_RESOLUTION,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        output_path: Path | None = None,
        output_format: Literal["png", "jpeg", "webp"] = "png",
        response_format: Literal["b64_json", "url"] = "b64_json",
        watermark: bool = False,
        prompt_extend: bool = True,
        max_retries: int = 2,
        **_kwargs: Any,
    ) -> dict:
        """Generate once with U1.5 (or explicitly selected model) and save immediately."""
        selected_model = model or self.model or global_configs.SN_IMAGE_GEN_MODEL or DEFAULT_MODEL
        size = self._resolve_size(image_size, aspect_ratio, fast=selected_model == FAST_MODEL)
        payload = self.build_payload(
            prompt=prompt,
            model=selected_model,
            size=size,
            output_format=output_format,
            response_format=response_format,
            watermark=watermark,
            prompt_extend=prompt_extend,
        )
        output_path = self._default_output_path(output_path, "t2i", output_format)
        return await self._request_and_save(
            endpoint=IMAGE_GEN_ENDPOINT,
            payload=payload,
            output_path=output_path,
            output_format=output_format,
            model=selected_model,
            operation="generate",
            max_retries=max_retries,
        )

    async def edit(
        self,
        prompt: str,
        images: list[str | Path],
        *,
        model: str | None = None,
        image_size: str = "auto",
        aspect_ratio: str | None = None,
        output_path: Path | None = None,
        response_format: Literal["b64_json", "url"] = "b64_json",
        watermark: bool = False,
        prompt_extend: bool = True,
        max_retries: int = 2,
    ) -> dict:
        """Edit one or more local/remote reference images with U1.5."""
        selected_model = model or self.model or global_configs.SN_IMAGE_GEN_MODEL or DEFAULT_MODEL
        if selected_model == FAST_MODEL:
            raise ValueError(
                f"{FAST_MODEL} does not accept image input; use {DEFAULT_MODEL} for edits."
            )
        if not images:
            raise ValueError("At least one reference image is required.")
        size = self._resolve_size(image_size, aspect_ratio, allow_auto=True)
        image_inputs = [{"image_url": self.image_to_data_url(image)} for image in images]
        payload: dict[str, Any] = {
            "model": selected_model,
            "prompt": prompt,
            "images": image_inputs,
            "size": size,
            "n": 1,
            "watermark": watermark,
            "prompt_extend": prompt_extend,
            "response_format": response_format,
        }
        output_path = self._default_output_path(output_path, "edit", "png")
        return await self._request_and_save(
            endpoint=IMAGE_EDIT_ENDPOINT,
            payload=payload,
            output_path=output_path,
            output_format="png",
            model=selected_model,
            operation="edit",
            max_retries=max_retries,
        )

    async def _request_and_save(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        output_path: Path,
        output_format: str,
        model: str,
        operation: str,
        max_retries: int,
    ) -> dict:
        client = await self._get_client()
        attempt = 0
        while True:
            try:
                response = await client.post(self.get_api_url(endpoint=endpoint), json=payload)
                data = self.parse_response(response)
                break
            except U1HttpErrorBase as exc:
                # Only 5xx receives same-model retries. 404/429 are surfaced so
                # the generation runner can make its deliberately narrow fallback decision.
                if exc.code is not None and 500 <= exc.code <= 599 and attempt < max_retries:
                    await asyncio.sleep(min(2**attempt, 4))
                    attempt += 1
                    continue
                return self._error_result(exc, model, operation, attempt)
            except httpx.HTTPError as exc:
                return {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "model": model,
                    "operation": operation,
                    "retry_count": attempt,
                    "fallback_eligible": False,
                }

        try:
            saved = await self._save_response(data, output_path, output_format)
        except (OSError, ValueError, binascii.Error, httpx.HTTPError) as exc:
            return {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "model": model,
                "operation": operation,
                "retry_count": attempt,
                "fallback_eligible": False,
            }
        return {
            "status": "ok",
            "output": str(saved),
            "message": "Image edited successfully"
            if operation == "edit"
            else "Image generated successfully",
            "model": model,
            "operation": operation,
            "retry_count": attempt,
            "fallback_used": False,
        }

    @staticmethod
    def _error_result(exc: U1HttpErrorBase, model: str, operation: str, retries: int) -> dict:
        code = exc.code
        fallback_eligible = operation == "generate" and (
            code in {404, 429} or (code is not None and 500 <= code <= 599)
        )
        detail = f"; {exc.detail}" if exc.detail else ""
        return {
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": f"HTTP {code}: {exc.message}{detail}",
            "http_status": code,
            "model": model,
            "operation": operation,
            "retry_count": retries,
            "fallback_eligible": fallback_eligible,
        }

    @staticmethod
    def _default_output_path(path: Path | None, prefix: str, output_format: str) -> Path:
        suffix = _FORMAT_SUFFIX.get(output_format, ".png")
        if path is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            path = OUTPUT_DIR / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}{suffix}"
        elif path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            path = path.with_suffix(suffix)
        return ensure_output_path(path)

    async def _save_response(self, data: dict, output_path: Path, output_format: str) -> Path:
        if data["images_b64"]:
            return save_base64_image(data["images_b64"][-1], output_path)
        if data["images_urls"]:
            return await download_image(data["images_urls"][-1], output_path, self._timeout)
        raise ValueError("No image data returned by the model.")

    @property
    @override
    def api_key(self) -> str:
        value = self._api_key or global_configs.SN_IMAGE_GEN_API_KEY
        if not value:
            raise MissingApiKeyError(global_configs.get_env_var_help("SN_IMAGE_GEN_API_KEY"))
        return value

    @property
    @override
    def base_url(self) -> str:
        value = self._base_url or global_configs.SN_IMAGE_GEN_BASE_URL
        if not value or not is_valid_base_url(value):
            raise InvalidBaseUrlError(f"Invalid image API base URL: {value}")
        return value

    @override
    def get_api_url(self, _model: str | None = None, *, endpoint: str = IMAGE_GEN_ENDPOINT) -> str:
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    @override
    def build_payload(
        self,
        prompt: str,
        model: str,
        *,
        size: str | None = None,
        output_format: Literal["png", "jpeg", "webp"] = "png",
        response_format: Literal["b64_json", "url"] = "b64_json",
        watermark: bool = False,
        prompt_extend: bool = True,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        # U1 Fast has a smaller schema and returns a temporary URL. Do not send
        # U1.5-only fields that the Fast endpoint does not document.
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "watermark": watermark,
        }
        if model != FAST_MODEL:
            payload.update(
                output_format=output_format,
                response_format=response_format,
                prompt_extend=prompt_extend,
            )
        return payload

    @property
    @override
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    @classmethod
    def _resolve_size(
        cls,
        resolution: str | None = None,
        aspect_ratio: str | None = None,
        *,
        allow_auto: bool = False,
        fast: bool = False,
    ) -> str | None:
        value = (resolution or DEFAULT_RESOLUTION).strip()
        if value.lower() == "auto":
            if allow_auto:
                return "auto"
            raise ValueError("size='auto' is only supported for image editing.")
        explicit = _EXPLICIT_SIZE.fullmatch(value)
        if explicit:
            width, height = map(int, explicit.groups())
            cls._validate_dimensions(width, height)
            if fast:
                return cls._nearest_bucket(width / height, FAST_BUCKETS_2K)
            return f"{width}x{height}"

        ratio = cls._parse_ratio(aspect_ratio or "1:1")
        preset = value.upper()
        if fast:
            return cls._nearest_bucket(ratio, FAST_BUCKETS_2K)
        if preset == "1K":
            return cls._nearest_bucket(ratio, BUCKETS_1K)
        if preset == "2K":
            return cls._nearest_bucket(ratio, U15_BUCKETS_2K)
        if preset == "4K":
            if ratio >= 1:
                width = 4096
                height = max(512, round((4096 / ratio) / 32) * 32)
            else:
                height = 4096
                width = max(512, round((4096 * ratio) / 32) * 32)
            cls._validate_dimensions(width, height)
            return f"{width}x{height}"
        raise ValueError("image-size must be 1K, 2K, 4K, auto (edit only), or WIDTHxHEIGHT.")

    @staticmethod
    def _parse_ratio(value: str) -> float:
        try:
            left, separator, right = value.strip().partition(":")
            if not separator:
                raise ValueError
            ratio = int(left) / int(right)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"Invalid aspect ratio: {value!r}") from exc
        if not 1 / 3 <= ratio <= 3:
            raise ValueError("Aspect ratio must not exceed 3:1 in either direction.")
        return ratio

    @staticmethod
    def _validate_dimensions(width: int, height: int) -> None:
        if not (512 <= width <= 4096 and 512 <= height <= 4096):
            raise ValueError("Image dimensions must each be between 512 and 4096 pixels.")
        if width % 32 or height % 32:
            raise ValueError("Image dimensions must be multiples of 32 pixels.")
        ratio = width / height
        if not 1 / 3 <= ratio <= 3:
            raise ValueError("Image dimensions must not exceed a 3:1 aspect ratio.")

    @staticmethod
    def _nearest_bucket(ratio: float, buckets: dict[str, tuple[int, int]]) -> str:
        width, height = min(buckets.values(), key=lambda pair: abs(pair[0] / pair[1] - ratio))
        return f"{width}x{height}"

    @staticmethod
    def image_to_data_url(image: str | Path) -> str:
        value = str(image)
        if value.startswith(("https://", "http://", "data:image/")):
            return value
        path = Path(value).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Reference image not found: {path}")
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if not mime_type.startswith("image/"):
            raise ValueError(f"Reference file is not a supported image: {path}")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @override
    def parse_response(self, response: httpx.Response) -> dict:
        raw = super().parse_response(response)
        urls: list[str] = []
        encoded: list[str] = []
        for item in raw.get("data", []):
            if isinstance(item, dict):
                if isinstance(item.get("url"), str) and item["url"]:
                    urls.append(item["url"])
                if isinstance(item.get("b64_json"), str) and item["b64_json"]:
                    encoded.append(item["b64_json"])
        return {"images_urls": urls, "images_b64": encoded}


def save_base64_image(value: str, save_path: Path) -> Path:
    """Decode, validate and atomically store an API b64_json image."""
    if ";base64," in value:
        value = value.split(";base64,", 1)[1]
    raw = base64.b64decode(value, validate=True)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=save_path.parent, prefix=f".{save_path.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary.write(raw)
            temporary.flush()
            os.fsync(temporary.fileno())
            temp_path = Path(temporary.name)
        _validate_image_file(temp_path)
        temp_path.replace(save_path)
        return save_path
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


async def download_image(
    url: str,
    save_path: Path,
    timeout: float = DEFAULT_HTTP_REQUEST_TIMEOUT,
) -> Path:
    """Download a temporary model URL, validate it and atomically store it."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=save_path.parent, prefix=f".{save_path.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        temporary.write(chunk)
            temporary.flush()
            os.fsync(temporary.fileno())
        _validate_image_file(temp_path)
        temp_path.replace(save_path)
        return save_path
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _validate_image_file(image_path: Path) -> None:
    with Image.open(image_path) as image:
        image.verify()
    with Image.open(image_path) as image:
        image.load()


BUCKETS_1K: dict[str, tuple[int, int]] = {
    "2:3": (1088, 1632),
    "3:2": (1632, 1088),
    "3:4": (1152, 1536),
    "4:3": (1536, 1152),
    "4:5": (1184, 1472),
    "5:4": (1472, 1184),
    "1:1": (1344, 1344),
    "16:9": (1792, 992),
    "9:16": (992, 1792),
    "21:9": (2048, 864),
    "9:21": (864, 2048),
}
FAST_BUCKETS_2K: dict[str, tuple[int, int]] = {
    "2:3": (1664, 2496),
    "3:2": (2496, 1664),
    "3:4": (1760, 2368),
    "4:3": (2368, 1760),
    "4:5": (1824, 2272),
    "5:4": (2272, 1824),
    "1:1": (2048, 2048),
    "16:9": (2752, 1536),
    "9:16": (1536, 2752),
    "21:9": (3072, 1376),
    "9:21": (1344, 3136),
}
U15_BUCKETS_2K: dict[str, tuple[int, int]] = {
    **FAST_BUCKETS_2K,
    "16:9": (2720, 1536),
    "9:16": (1536, 2720),
}
