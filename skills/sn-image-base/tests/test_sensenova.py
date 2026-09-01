from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import sn_agent_runner
from sn_image_base.configs import Configs
from sn_image_base.generation.sensenova import (
    DEFAULT_MODEL,
    FAST_MODEL,
    SensenovaText2ImageClient,
    save_base64_image,
)


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(buffer, format="PNG")
    return buffer.getvalue()


class ConfigurationTests(unittest.TestCase):
    def test_image_defaults_and_no_chat_model_default(self) -> None:
        keys = [
            "SN_IMAGE_GEN_MODEL",
            "SN_IMAGE_GEN_FALLBACK_MODEL",
            "SN_CHAT_MODEL",
            "SN_TEXT_MODEL",
            "SN_VISION_MODEL",
        ]
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            configs = Configs()
        self.assertEqual(configs.SN_IMAGE_GEN_MODEL, DEFAULT_MODEL)
        self.assertEqual(configs.SN_IMAGE_GEN_FALLBACK_MODEL, FAST_MODEL)
        self.assertEqual(configs.SN_CHAT_MODEL, "")
        self.assertEqual(configs.SN_TEXT_MODEL, "")
        self.assertEqual(configs.SN_VISION_MODEL, "")

    def test_config_string_masks_api_key(self) -> None:
        with patch.dict(
            os.environ, {"SENSENOVA_API_KEY": "sk-secret-value-1234"}, clear=True
        ):
            configs = Configs()
            rendered = configs.to_string()
        self.assertEqual(configs.SN_IMAGE_GEN_API_KEY, "sk-secret-value-1234")
        self.assertEqual(configs.SN_CHAT_API_KEY, "sk-secret-value-1234")
        self.assertEqual(configs.SN_TEXT_API_KEY, "sk-secret-value-1234")
        self.assertEqual(configs.SN_VISION_API_KEY, "sk-secret-value-1234")
        self.assertNotIn("sk-secret-value-1234", rendered)
        self.assertIn("******", rendered)

    def test_legacy_key_variables_are_not_read(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SN_API_KEY": "legacy-shared-key",
                "SN_IMAGE_GEN_API_KEY": "legacy-image-key",
                "SN_CHAT_API_KEY": "legacy-chat-key",
                "SN_TEXT_API_KEY": "legacy-text-key",
                "SN_VISION_API_KEY": "legacy-vision-key",
            },
            clear=True,
        ):
            configs = Configs()
        self.assertEqual(configs.SN_IMAGE_GEN_API_KEY, "")
        self.assertEqual(configs.SN_CHAT_API_KEY, "")
        self.assertEqual(configs.SN_TEXT_API_KEY, "")
        self.assertEqual(configs.SN_VISION_API_KEY, "")


class SensenovaPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = SensenovaText2ImageClient(
            api_key="test-key", base_url="https://example.test/v1", model=DEFAULT_MODEL
        )

    def test_u15_payload_defaults(self) -> None:
        payload = self.client.build_payload("draw", DEFAULT_MODEL, size="2048x2048")
        self.assertEqual(payload["response_format"], "b64_json")
        self.assertEqual(payload["output_format"], "png")
        self.assertTrue(payload["prompt_extend"])
        self.assertFalse(payload["watermark"])
        self.assertEqual(payload["n"], 1)

    def test_fast_payload_omits_u15_only_fields(self) -> None:
        payload = self.client.build_payload("draw", FAST_MODEL, size="2048x2048")
        self.assertNotIn("response_format", payload)
        self.assertNotIn("output_format", payload)
        self.assertNotIn("prompt_extend", payload)
        self.assertFalse(payload["watermark"])

    def test_sizes_and_dimension_validation(self) -> None:
        self.assertEqual(self.client._resolve_size("2K", "1:1"), "2048x2048")
        self.assertEqual(self.client._resolve_size("4096x2048", "1:1"), "4096x2048")
        self.assertEqual(self.client._resolve_size("4K", "1:1"), "4096x4096")
        self.assertEqual(
            self.client._resolve_size("4K", "16:9", fast=True), "2752x1536"
        )
        with self.assertRaisesRegex(ValueError, "multiples of 32"):
            self.client._resolve_size("1025x1024", "1:1")
        with self.assertRaisesRegex(ValueError, "between 512 and 4096"):
            self.client._resolve_size("480x1024", "1:1")
        with self.assertRaisesRegex(ValueError, "3:1"):
            self.client._resolve_size("4096x512", "1:1")

    def test_local_image_becomes_data_url_and_remote_url_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "reference.png"
            image_path.write_bytes(png_bytes())
            value = self.client.image_to_data_url(image_path)
        self.assertTrue(value.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(value.split(",", 1)[1]), png_bytes())
        remote = "https://example.test/reference.png"
        self.assertEqual(self.client.image_to_data_url(remote), remote)

    def test_b64_json_is_saved_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.png"
            saved = save_base64_image(base64.b64encode(png_bytes()).decode(), path)
            self.assertEqual(saved, path)
            with Image.open(saved) as image:
                self.assertEqual(image.size, (32, 32))


class SensenovaRequestTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.requests: list[dict] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(json.loads(request.content))
            return httpx.Response(
                200,
                request=request,
                json={"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]},
            )

        self.client = SensenovaText2ImageClient(
            api_key="test-key", base_url="https://example.test/v1", model=DEFAULT_MODEL
        )
        self.client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_generation_request_and_saved_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "generated.png"
            result = await self.client.generate(
                "draw", aspect_ratio="1:1", output_path=output
            )
            self.assertEqual(result["status"], "ok")
            self.assertTrue(output.is_file())
        payload = self.requests[0]
        self.assertEqual(payload["model"], DEFAULT_MODEL)
        self.assertEqual(payload["response_format"], "b64_json")
        self.assertFalse(payload["watermark"])

    async def test_edit_accepts_multiple_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reference = Path(temp_dir) / "reference.png"
            reference.write_bytes(png_bytes())
            output = Path(temp_dir) / "edited.png"
            result = await self.client.edit(
                "replace the title",
                [reference, "https://example.test/second.png"],
                output_path=output,
            )
            self.assertEqual(result["status"], "ok")
        payload = self.requests[0]
        self.assertEqual(len(payload["images"]), 2)
        self.assertTrue(
            payload["images"][0]["image_url"].startswith("data:image/png;base64,")
        )
        self.assertEqual(
            payload["images"][1]["image_url"], "https://example.test/second.png"
        )
        self.assertFalse(payload["watermark"])

    async def test_5xx_retries_same_model_before_success(self) -> None:
        attempts = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return httpx.Response(500, request=request, json={"error": "temporary"})
            return httpx.Response(
                200,
                request=request,
                json={"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]},
            )

        await self.client.aclose()
        self.client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch("sn_image_base.generation.sensenova.asyncio.sleep", new=AsyncMock()),
        ):
            result = await self.client.generate(
                "draw", output_path=Path(temp_dir) / "retry.png", max_retries=2
            )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["retry_count"], 2)
        self.assertEqual(attempts, 3)

    async def test_http_failure_metadata_matches_fallback_matrix(self) -> None:
        for status, eligible in (
            (400, False),
            (401, False),
            (403, False),
            (404, True),
            (429, True),
            (500, True),
        ):
            with self.subTest(status=status):

                async def handler(
                    request: httpx.Request, code: int = status
                ) -> httpx.Response:
                    return httpx.Response(
                        code, request=request, json={"error": "simulated"}
                    )

                await self.client.aclose()
                self.client._client = httpx.AsyncClient(
                    transport=httpx.MockTransport(handler)
                )
                with tempfile.TemporaryDirectory() as temp_dir:
                    result = await self.client.generate(
                        "draw",
                        output_path=Path(temp_dir) / "failed.png",
                        max_retries=0,
                    )
                self.assertEqual(result["http_status"], status)
                self.assertEqual(result["fallback_eligible"], eligible)

    async def test_edit_5xx_is_not_fallback_eligible(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, request=request, json={"error": "simulated"})

        await self.client.aclose()
        self.client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with tempfile.TemporaryDirectory() as temp_dir:
            reference = Path(temp_dir) / "reference.png"
            reference.write_bytes(png_bytes())
            result = await self.client.edit(
                "fix",
                [reference],
                output_path=Path(temp_dir) / "failed-edit.png",
                max_retries=0,
            )
        self.assertEqual(result["http_status"], 503)
        self.assertFalse(result["fallback_eligible"])


class FallbackMatrixTests(unittest.TestCase):
    def eligible(self, code: int, operation: str = "generate") -> dict:
        return {
            "status": "failed",
            "operation": operation,
            "http_status": code,
            "fallback_eligible": code in {404, 429} or 500 <= code <= 599,
        }

    def test_only_recoverable_generation_errors_fallback(self) -> None:
        for code in (404, 429, 500, 503, 599):
            with self.subTest(code=code):
                self.assertTrue(
                    sn_agent_runner.should_fallback_generation(
                        self.eligible(code), disabled=False, fallback_model=FAST_MODEL
                    )
                )
        for code in (400, 401, 403, 422):
            with self.subTest(code=code):
                result = self.eligible(code)
                result["fallback_eligible"] = False
                self.assertFalse(
                    sn_agent_runner.should_fallback_generation(
                        result, disabled=False, fallback_model=FAST_MODEL
                    )
                )

    def test_edit_and_no_fallback_flag_never_fallback(self) -> None:
        self.assertFalse(
            sn_agent_runner.should_fallback_generation(
                self.eligible(503, "edit"), disabled=False, fallback_model=FAST_MODEL
            )
        )
        self.assertFalse(
            sn_agent_runner.should_fallback_generation(
                self.eligible(503), disabled=True, fallback_model=FAST_MODEL
            )
        )


if __name__ == "__main__":
    unittest.main()
