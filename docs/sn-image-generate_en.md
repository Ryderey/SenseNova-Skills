# SN Image & Visualization Guide

English | [简体中文](sn-image-generate.md)

This repository contains only `sn-image-base`, `sn-image-doctor`, `sn-infographic`, `sn-image-imitate`, and `sn-image-resume`.

## Defaults

- `sensenova-u1.5-lite`: primary generation and editing model.
- `sensenova-u1-fast`: recoverable text-to-image fallback only; no image input.
- `watermark=false`, `prompt_extend=true`, `response_format=b64_json`; save immediately.
- No default `SN_CHAT_MODEL`; the host Agent plans and reviews first.

Model calls follow the account plan and credit rules. `watermark=false` is free only during the current public beta and is documented to become a premium paid feature afterward.

Open the official [SenseNova API documentation](https://platform.sensenova.cn/docs) and find the `SenseNova U1.5 Lite` or `SenseNova U1 Fast` section by its heading. The documentation site's deep links are not reliable on a cold load.

## Configure and diagnose

```dotenv
SENSENOVA_API_KEY=your-key
SN_IMAGE_GEN_BASE_URL=https://token.sensenova.cn/v1
SN_IMAGE_GEN_MODEL=sensenova-u1.5-lite
SN_IMAGE_GEN_FALLBACK_MODEL=sensenova-u1-fast
```

The default setup needs only `SENSENOVA_API_KEY`. Set an override only when a capability uses a different credential:

The runtime uses existing process values first, then the file selected by `SN_ENV_FILE`, then the nearest `.env` found from the current working directory upward. Verbose Doctor output reports the Python executable and environment-file path without exposing the key.

| Variable | Purpose | Resolution order |
| --- | --- | --- |
| `SENSENOVA_API_KEY` | Default shared key for every capability | Shared fallback |
| `SN_IMAGE_GEN_API_KEY` | Image generation and editing | `--api-key` > this variable > shared key |
| `SN_CHAT_API_KEY` | Optional key shared by text and vision adapters | `--api-key` > direct capability key > this variable > shared key |
| `SN_TEXT_API_KEY` | Text adapter only | `--api-key` > this variable > chat key > shared key |
| `SN_VISION_API_KEY` | Vision adapter only | `--api-key` > this variable > chat key > shared key |

The following commands assume you have created and activated a virtual environment using the [installation guide](../INSTALL.md), and `python` refers to the interpreter used to install dependencies. If it is not activated, use that interpreter's absolute path instead. The Agent host must use the same interpreter.

```bash
python -m pip install -r skills/sn-image-base/requirements.txt
python skills/sn-image-doctor/scripts/check_environment.py --verbose
```

The host must use the same Python interpreter that passes this check. Doctor validates offline configuration; add `--require-edit` for native editing workflows.

## Generate

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-generate \
  --prompt "Product architecture infographic with accurate labels" \
  --image-size 2k \
  --aspect-ratio 16:9 \
  --save-path result.png \
  --output-format json
```

Sizes: official `2k` / `4k`, repository compatibility preset `1k`, or `WIDTHxHEIGHT`. `1k` is mapped to valid explicit dimensions rather than sent as an API constant. U1.5 2K 16:9 / 9:16 uses the official recommended `2720x1536` / `1536x2720`; Fast uses its fixed `2752x1536` / `1536x2752` buckets. Explicit dimensions must be multiples of 32, 512-4096 per side, and at most 3:1. PNG/JPEG/WEBP are supported; after a Fast fallback, the runtime transcodes the downloaded result to the requested format.

URL responses are downloaded immediately: U1.5 generation/edit URLs expire after 24 hours and U1 Fast URLs after 1 hour. The default Base64 path has no URL-expiry risk.

Use `--model`, `--fallback-model`, and `--no-fallback` for control. Only 404, 429, and retry-exhausted 5xx may fall back. Bad/safety requests, 401/403, and file errors never do.

For a long prompt, save UTF-8 text and pass `--prompt-path prompt.txt`; it is mutually exclusive with `--prompt`. Prefer the file form for infographics, resumes, and punctuation-heavy copy.

## Edit

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-edit \
  --prompt "Keep the composition, correct the title, improve hierarchy" \
  --images result.png https://example.com/reference.webp \
  --image-size auto \
  --save-path revised.png \
  --output-format json
```

Local images, public URLs, and Data URLs are validated, bounded to 64 MiB / 40 million decoded pixels, normalized to PNG/JPEG when needed, and sent as Data URLs. Multiple references and continued editing are supported. Editing uses U1.5 and never falls back to U1 Fast.

## JSON fields

Success preserves `status`, `output`, and `message`, adding `model`, `operation`, `retry_count`, `fallback_used`, and `fallback_reason`. Failures include `error_type` and `error`, plus `http_status` when available.

## Troubleshooting

- 401/403: key or permission problem; no fallback.
- 400/safety: fix the request; no fallback.
- 429: generation may fall back; editing cannot.
- 5xx: U1.5 retries first; generation may fall back after exhaustion.
- Edit failure: ensure the model is not U1 Fast and every local/remote reference is readable.
- External text/vision says model missing: pass `--model` or set `SN_TEXT_MODEL` / `SN_VISION_MODEL`; the skill will not select one.
