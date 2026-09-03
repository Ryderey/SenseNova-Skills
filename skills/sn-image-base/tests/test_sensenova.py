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
from sn_image_base.configs import Configs, is_valid_base_url
from sn_image_base.generation import OpenAIImageGenerationClient
from sn_image_base.generation.core import unique_output_path
from sn_image_base.generation.sensenova import (
    DEFAULT_HTTP_REQUEST_TIMEOUT,
    DEFAULT_MODEL,
    FAST_MODEL,
    SensenovaText2ImageClient,
    download_image,
    save_base64_image,
)
from sn_image_base.image_utils import (
    normalize_for_model,
    read_image_source,
    require_public_http_url,
    save_image_bytes,
)
from sn_image_base.llm.anthropic_adapter import (
    ANTHROPIC_VERSION,
    AnthropicMessagesAdapter,
)


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def webp_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buffer, format="WEBP")
    return buffer.getvalue()


def data_url(raw: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


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
        self.assertEqual(configs.SN_IMAGE_GEN_MODEL_TYPE, "sensenova")
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
        self.assertEqual(configs.SENSENOVA_API_KEY, "sk-secret-value-1234")
        self.assertEqual(configs.SN_IMAGE_GEN_API_KEY, "sk-secret-value-1234")
        self.assertEqual(configs.SN_CHAT_API_KEY, "sk-secret-value-1234")
        self.assertEqual(configs.SN_TEXT_API_KEY, "sk-secret-value-1234")
        self.assertEqual(configs.SN_VISION_API_KEY, "sk-secret-value-1234")
        self.assertNotIn("sk-secret-value-1234", rendered)
        self.assertIn("******", rendered)

    def test_capability_keys_override_shared_key(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SENSENOVA_API_KEY": "shared-key",
                "SN_IMAGE_GEN_API_KEY": "image-key",
                "SN_CHAT_API_KEY": "chat-key",
                "SN_TEXT_API_KEY": "text-key",
                "SN_VISION_API_KEY": "vision-key",
            },
            clear=True,
        ):
            configs = Configs()
        self.assertEqual(configs.SENSENOVA_API_KEY, "shared-key")
        self.assertEqual(configs.SN_IMAGE_GEN_API_KEY, "image-key")
        self.assertEqual(configs.SN_CHAT_API_KEY, "chat-key")
        self.assertEqual(configs.SN_TEXT_API_KEY, "text-key")
        self.assertEqual(configs.SN_VISION_API_KEY, "vision-key")

    def test_blank_capability_keys_fall_back_to_shared_key(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SENSENOVA_API_KEY": "shared-key",
                "SN_IMAGE_GEN_API_KEY": "",
                "SN_CHAT_API_KEY": "",
                "SN_TEXT_API_KEY": "",
                "SN_VISION_API_KEY": "",
            },
            clear=True,
        ):
            configs = Configs()
        self.assertEqual(configs.SN_IMAGE_GEN_API_KEY, "shared-key")
        self.assertEqual(configs.SN_CHAT_API_KEY, "shared-key")
        self.assertEqual(configs.SN_TEXT_API_KEY, "shared-key")
        self.assertEqual(configs.SN_VISION_API_KEY, "shared-key")

    def test_runtime_types_and_base_urls_are_validated(self) -> None:
        self.assertTrue(is_valid_base_url("https://api.example.com/v1"))
        self.assertTrue(is_valid_base_url("http://localhost:8000/v1"))
        for value in (
            "ftp://example.com",
            "file://server/share",
            "https://user:secret@example.com/v1",
            "https://example.com/v1?token=secret",
        ):
            with self.subTest(value=value):
                self.assertFalse(is_valid_base_url(value))

        with patch.dict(
            os.environ,
            {"SENSENOVA_API_KEY": "shared-key", "SN_TEXT_TYPE": "unknown-protocol"},
            clear=True,
        ):
            errors, _warnings = Configs().validate_configs()
        self.assertTrue(any(field == "SN_TEXT_TYPE" for field, _message in errors))

        with patch.dict(
            os.environ,
            {
                "SENSENOVA_API_KEY": "shared-key",
                "SN_TEXT_BASE_URL": "https://user:top-secret@example.test/v1",
            },
            clear=True,
        ):
            errors, _warnings = Configs().validate_configs()
        self.assertNotIn("top-secret", repr(errors))


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
        with self.assertRaisesRegex(ValueError, "aspect-ratio"):
            self.client._resolve_size("auto", "16:9", allow_auto=True)

    def test_fast_uses_all_eleven_official_2k_buckets(self) -> None:
        expected = {
            "2:3": "1664x2496",
            "3:2": "2496x1664",
            "3:4": "1760x2368",
            "4:3": "2368x1760",
            "4:5": "1824x2272",
            "5:4": "2272x1824",
            "1:1": "2048x2048",
            "16:9": "2752x1536",
            "9:16": "1536x2752",
            "21:9": "3072x1376",
            "9:21": "1344x3136",
        }
        for ratio, size in expected.items():
            with self.subTest(ratio=ratio):
                self.assertEqual(
                    self.client._resolve_size("2K", ratio, fast=True), size
                )

    def test_u15_uses_official_recommended_widescreen_2k_sizes(self) -> None:
        self.assertEqual(self.client._resolve_size("2K", "16:9"), "2720x1536")
        self.assertEqual(self.client._resolve_size("2K", "9:16"), "1536x2720")

    def test_local_data_and_remote_images_become_validated_data_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "reference.png"
            image_path.write_bytes(png_bytes())
            value = self.client.image_to_data_url(image_path)
        self.assertTrue(value.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(value.split(",", 1)[1]), png_bytes())

        encoded = data_url(png_bytes())
        self.assertEqual(self.client.image_to_data_url(encoded), encoded)

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(
                str(request.url), "https://93.184.216.34/reference.png"
            )
            self.assertEqual(request.headers["host"], "example.test")
            self.assertEqual(request.extensions["sni_hostname"], "example.test")
            return httpx.Response(
                200,
                content=png_bytes(),
                headers={"content-length": str(len(png_bytes()))},
                request=request,
            )

        remote = "https://example.test/reference.png"
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with (
            patch(
                "sn_image_base.image_utils.httpx.Client", return_value=client
            ) as client_factory,
            patch(
                "sn_image_base.image_utils.socket.getaddrinfo",
                return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
            ),
        ):
            normalized = self.client.image_to_data_url(remote)
        client_factory.assert_called_once_with(
            timeout=30.0, follow_redirects=False, trust_env=False
        )
        self.assertTrue(normalized.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(normalized.split(",", 1)[1]), png_bytes())

    def test_remote_images_reject_private_destinations_before_request(self) -> None:
        with (
            patch(
                "sn_image_base.image_utils.socket.getaddrinfo",
                return_value=[(2, 1, 6, "", ("127.0.0.1", 80))],
            ),
            patch("sn_image_base.image_utils.httpx.Client") as client,
            self.assertRaisesRegex(ValueError, "public"),
        ):
            read_image_source("http://localhost/reference.png")
        client.assert_not_called()

    def test_public_url_resolution_binds_the_connection_to_the_verified_ip(self) -> None:
        with patch(
            "sn_image_base.image_utils.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 8443))],
        ):
            target, headers, extensions = require_public_http_url(
                "https://example.test:8443/reference.png?version=1"
            )
        self.assertEqual(
            target, "https://93.184.216.34:8443/reference.png?version=1"
        )
        self.assertEqual(headers, {"Host": "example.test:8443"})
        self.assertEqual(extensions, {"sni_hostname": "example.test"})

    def test_remote_images_revalidate_redirect_targets(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                302,
                headers={"location": "http://[::1]/private.png"},
                request=request,
            )

        def resolve(host: str, port: int, **_kwargs):
            address = "93.184.216.34" if host == "example.test" else "::1"
            return [(2, 1, 6, "", (address, port))]

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with (
            patch("sn_image_base.image_utils.socket.getaddrinfo", side_effect=resolve),
            patch("sn_image_base.image_utils.httpx.Client", return_value=client),
            self.assertRaisesRegex(ValueError, "public"),
        ):
            read_image_source("https://example.test/reference.png")

    def test_b64_json_is_saved_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.png"
            saved = save_base64_image(base64.b64encode(png_bytes()).decode(), path)
            self.assertEqual(saved, path)
            with Image.open(saved) as image:
                self.assertEqual(image.size, (32, 32))

    def test_webp_is_normalized_for_model_input(self) -> None:
        mime, raw = normalize_for_model(webp_bytes())
        self.assertEqual(mime, "image/png")
        with Image.open(io.BytesIO(raw)) as image:
            self.assertEqual(image.format, "PNG")

    def test_image_limits_and_format_correct_suffix_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "too-large.png"
            source.write_bytes(png_bytes())
            with (
                patch("sn_image_base.image_utils.MAX_IMAGE_BYTES", 8),
                self.assertRaisesRegex(ValueError, "exceeds"),
            ):
                read_image_source(source)

            saved = save_image_bytes(png_bytes(), Path(temp_dir) / "result.jpg")
            self.assertEqual(saved.suffix, ".png")
            self.assertTrue(saved.is_file())

            converted = save_image_bytes(
                png_bytes(), Path(temp_dir) / "converted.webp", "webp"
            )
            self.assertEqual(converted.suffix, ".webp")
            with Image.open(converted) as image:
                self.assertEqual(image.format, "WEBP")

            with (
                patch("sn_image_base.image_utils.MAX_IMAGE_PIXELS", 100),
                self.assertRaisesRegex(ValueError, "pixel limit"),
            ):
                normalize_for_model(png_bytes())

            with (
                patch("sn_image_base.image_utils.MAX_IMAGE_BYTES", 8),
                patch("sn_image_base.image_utils.base64.b64decode") as decode,
                self.assertRaisesRegex(ValueError, "exceeds"),
            ):
                read_image_source("data:image/png;base64," + "A" * 100)
            decode.assert_not_called()

    def test_default_output_paths_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = unique_output_path(root, "t2i", ".png")
            second = unique_output_path(root, "t2i", ".png")
        self.assertNotEqual(first, second)
        self.assertEqual(first.suffix, ".png")


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

    async def test_model_url_download_uses_the_verified_ip_and_original_sni(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(
                str(request.url), "https://93.184.216.34/generated.png"
            )
            self.assertEqual(request.headers["host"], "cdn.example.test")
            self.assertEqual(request.extensions["sni_hostname"], "cdn.example.test")
            return httpx.Response(200, content=png_bytes(), request=request)

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch(
                "sn_image_base.image_utils.socket.getaddrinfo",
                return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
            ),
            patch(
                "sn_image_base.generation.sensenova.httpx.AsyncClient",
                return_value=async_client,
            ) as client_factory,
        ):
            saved = await download_image(
                "https://cdn.example.test/generated.png",
                Path(temp_dir) / "download.png",
            )
            self.assertTrue(saved.is_file())
        client_factory.assert_called_once_with(
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT,
            follow_redirects=False,
            trust_env=False,
        )

    async def test_edit_accepts_multiple_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reference = Path(temp_dir) / "reference.png"
            reference.write_bytes(png_bytes())
            output = Path(temp_dir) / "edited.png"
            result = await self.client.edit(
                "replace the title",
                [reference, data_url(png_bytes())],
                output_path=output,
            )
            self.assertEqual(result["status"], "ok")
        payload = self.requests[0]
        self.assertEqual(len(payload["images"]), 2)
        self.assertTrue(
            payload["images"][0]["image_url"].startswith("data:image/png;base64,")
        )
        self.assertTrue(
            payload["images"][1]["image_url"].startswith("data:image/png;base64,")
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

    def test_legacy_generation_flags_fail_instead_of_being_ignored(self) -> None:
        args = sn_agent_runner.build_parser().parse_args(
            [
                "sn-image-generate",
                "--prompt",
                "draw",
                "--negative-prompt",
                "blur",
                "--seed",
                "7",
                "--unet-name",
                "legacy",
                "--poll-interval",
                "1",
            ]
        )
        with self.assertRaisesRegex(ValueError, "--negative-prompt.*--poll-interval"):
            sn_agent_runner._reject_unsupported_generation_options(args)

    def test_runner_normalizes_optional_backend_metadata(self) -> None:
        result = sn_agent_runner._normalize_image_result(
            {"status": "ok", "output": "image.png"},
            model="configured-model",
            operation="generate",
        )
        self.assertEqual(result["model"], "configured-model")
        self.assertEqual(result["operation"], "generate")
        self.assertEqual(result["retry_count"], 0)
        self.assertFalse(result["fallback_used"])
        self.assertIsNone(result["fallback_reason"])

    def test_openai_backend_receives_timeout_and_tls_settings(self) -> None:
        client = OpenAIImageGenerationClient(
            api_key="test-key",
            base_url="https://example.test/v1",
            model="image-model",
            timeout=12.5,
            ssl_verify=False,
        )
        self.assertEqual(client._timeout, 12.5)
        self.assertFalse(client._ssl_verify)


class RunnerGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_generation_fallback_preserves_requested_output_options(self) -> None:
        args = sn_agent_runner.build_parser().parse_args(
            [
                "sn-image-generate",
                "--prompt",
                "draw",
                "--image-format",
                "webp",
                "--response-format",
                "url",
                "--no-prompt-extend",
                "--save-path",
                "out.webp",
            ]
        )
        client = AsyncMock()
        client.generate.side_effect = [
            {
                "status": "failed",
                "operation": "generate",
                "http_status": 429,
                "error_type": "RateLimitError",
                "fallback_eligible": True,
            },
            {"status": "ok", "output": "out.webp"},
        ]
        with (
            patch.object(
                sn_agent_runner.global_configs,
                "SN_IMAGE_GEN_MODEL_TYPE",
                "sensenova",
            ),
            patch.object(sn_agent_runner.global_configs, "SN_IMAGE_GEN_API_KEY", "test-key"),
            patch.object(
                sn_agent_runner.global_configs,
                "SN_IMAGE_GEN_BASE_URL",
                "https://example.test/v1",
            ),
            patch.object(
                sn_agent_runner.global_configs,
                "SN_IMAGE_GEN_MODEL",
                DEFAULT_MODEL,
            ),
            patch.object(
                sn_agent_runner.global_configs,
                "SN_IMAGE_GEN_FALLBACK_MODEL",
                FAST_MODEL,
            ),
            patch.object(
                sn_agent_runner,
                "SensenovaText2ImageClient",
                return_value=client,
            ),
        ):
            result, exit_code = await sn_agent_runner.run_image_generate(args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(result["fallback_used"])
        fallback_options = client.generate.await_args_list[1].kwargs
        self.assertEqual(fallback_options["output_format"], "webp")
        self.assertEqual(fallback_options["response_format"], "url")
        self.assertFalse(fallback_options["prompt_extend"])

    async def test_edit_rejects_non_sensenova_generation_backend(self) -> None:
        args = sn_agent_runner.build_parser().parse_args(
            ["sn-image-edit", "--prompt", "edit", "--images", "reference.png"]
        )
        with (
            patch.object(
                sn_agent_runner.global_configs,
                "SN_IMAGE_GEN_MODEL_TYPE",
                "openai-image",
            ),
            self.assertRaisesRegex(Exception, "SenseNova"),
        ):
            await sn_agent_runner.run_image_edit(args)


class AnthropicContractTests(unittest.TestCase):
    def test_system_prompt_and_version_use_messages_wire_contract(self) -> None:
        adapter = AnthropicMessagesAdapter(
            endpoint_url="https://example.test/v1/messages",
            api_key="test-key",
            model="claude-test",
        )
        payload = adapter._build_payload("user text", "system text", None)
        self.assertEqual(payload["system"], "system text")
        self.assertEqual(
            payload["messages"], [{"role": "user", "content": "user text"}]
        )
        self.assertEqual(adapter._headers["anthropic-version"], ANTHROPIC_VERSION)


if __name__ == "__main__":
    unittest.main()
