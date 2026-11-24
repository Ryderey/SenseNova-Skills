# SN Image & Visualization Guide

English | [简体中文](sn-image-generate.md)

This repository contains only `sn-image-base`, `sn-image-doctor`, `sn-infographic`, `sn-image-imitate`, and `sn-image-resume`.

## Defaults

- `sensenova-u1.6-lite`: primary generation and editing model.
- Automatic fallback is off by default; set `SN_IMAGE_GEN_FALLBACK_MODEL` or `--fallback-model` explicitly. `sensenova-u1.5-fast` / `sensenova-u1-fast` are retired and unsupported; migrate to `sensenova-u1.6-lite`.
- `watermark=false`, `prompt_extend=true`, `self_correction=true`, `response_format=b64_json`; save immediately.
- No default `SN_CHAT_MODEL`; the host Agent plans and reviews first.

Model calls follow the account plan and credit rules. `watermark=false` is free only during the current public beta and is documented to become a premium paid feature afterward.

Open the official [SenseNova API documentation](https://platform.sensenova.cn/docs) and find the `SenseNova U1.6 Lite` section by its heading (the only image model in the current overview). The documentation site's deep links are not reliable on a cold load.

## Configure and diagnose

```dotenv
SENSENOVA_API_KEY=your-key
SN_IMAGE_GEN_BASE_URL=https://token.sensenova.cn/v1
SN_IMAGE_GEN_MODEL=sensenova-u1.6-lite
# Optional fallback; empty by default means automatic fallback is off. u1.5-fast / u1-fast are retired and unsupported.
SN_IMAGE_GEN_FALLBACK_MODEL=
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

The host must use the same Python interpreter that passes this check. Doctor validates local configuration offline and can also check the repository Release; add `--require-edit` for native editing workflows.

## Generate

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-generate \
  --prompt "Product architecture infographic with accurate labels" \
  --image-size 2k \
  --aspect-ratio 16:9 \
  --save-path result.png \
  --output-format json
```

The server-side `size` default is `auto` (adapts to the primary image when editing; the server chooses the resolution for generation); this runtime sends `2k` for generation by default and also accepts `--image-size auto` (cannot combine with `--aspect-ratio`; presets default to 16:9). Sizes: official constants `2k` / `4k`, repository compatibility preset `1k`, or `WIDTHxHEIGHT`. `1k` is not a server constant and is mapped to valid explicit dimensions. U1.6 2K 16:9 / 9:16 uses the official recommended `2720x1536` / `1536x2720`. Explicit dimensions must be multiples of 32, 512-4096 per side, and at most 3:1. PNG/JPEG/WEBP are supported; an explicitly configured fallback preserves size, format, and response transport.

URL responses are downloaded immediately: U1.6 Lite generation and edit URLs expire after 24 hours. The default Base64 path has no URL-expiry risk.

Use `--model`, `--fallback-model`, and `--no-fallback` for control. Automatic fallback is off by default; once a fallback model is set explicitly, only 404, 429, and retry-exhausted 5xx may fall back. Bad/safety requests, 401/403, and file errors never do.

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

Local images, public URLs, and Data URLs are validated, bounded to 64 MiB / 40 million decoded pixels, normalized to PNG/JPEG when needed, and sent as Data URLs. Multiple references and continued editing are supported. Editing defaults to U1.6 Lite with at most 5 references, the first being the primary image edited. Retired U1.5 IDs are unsupported; use `sensenova-u1.6-lite`. Editing never falls back automatically.

## JSON fields

Success preserves `status`, `output`, and `message`, adding `model`, `operation`, `retry_count`, `fallback_used`, and `fallback_reason`. Failures include `error_type` and `error`, plus `http_status` when available.

## Model migration (U1.5 to U1.6)

SenseNova has announced the retirement of `sensenova-u1.5-lite`, `sensenova-u1.5-fast`, and `sensenova-u1-fast`. They are unsupported by this repository. Any transitional platform routing is not a compatibility guarantee; the release manifest marks these IDs retired and the update checker blocks them. This repository defaults to `sensenova-u1.6-lite`, and automatic fallback is off by default.

- Change `SN_IMAGE_GEN_MODEL` to `sensenova-u1.6-lite` yourself and review any explicit `SN_IMAGE_GEN_FALLBACK_MODEL`, `--model`, or `--fallback-model` value.
- Do not configure retired U1.5/U1 IDs as primary, fallback, text, or vision models; the update check stops affected commands with exit code 3.
- After migrating, re-check the effective model names and endpoints with Doctor: `python skills/sn-image-doctor/scripts/check_environment.py --verbose`.

## Troubleshooting

- 401/403: key or permission problem; no fallback.
- 400/safety: fix the request; no fallback.
- 429: generation may fall back; editing cannot.
- 5xx: U1.6 retries first; generation falls back after exhaustion only when a fallback model is configured explicitly.
- Edit failure: ensure every local/remote reference is readable and there are at most 5 references (the first is the primary image).
- External text/vision says model missing: pass `--model` or set `SN_TEXT_MODEL` / `SN_VISION_MODEL`; the skill will not select one.
