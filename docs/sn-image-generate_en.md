# SN Image & Visualization Guide

English | [简体中文](sn-image-generate.md)

This repository contains only `sn-image-base`, `sn-image-doctor`, `sn-infographic`, `sn-image-imitate`, and `sn-image-resume`.

## Defaults

- `sensenova-u1.5-lite`: primary generation and editing model.
- `sensenova-u1-fast`: recoverable text-to-image fallback only; no image input.
- `watermark=false`, `prompt_extend=true`, `response_format=b64_json`; save immediately.
- No default `SN_CHAT_MODEL`; the host Agent plans and reviews first.

Official documentation: [U1.5 Lite](https://platform.sensenova.cn/docs#model-u1-5) / [U1 Fast](https://platform.sensenova.cn/docs#model-u1).

## Configure and diagnose

```dotenv
SN_API_KEY=your-key
SN_IMAGE_GEN_BASE_URL=https://token.sensenova.cn/v1
SN_IMAGE_GEN_MODEL=sensenova-u1.5-lite
SN_IMAGE_GEN_FALLBACK_MODEL=sensenova-u1-fast
```

```bash
python -m pip install -r skills/sn-image-base/requirements.txt
python skills/sn-image-doctor/scripts/check_environment.py --verbose
```

## Generate

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-generate \
  --prompt "Product architecture infographic with accurate labels" \
  --image-size 2k \
  --aspect-ratio 16:9 \
  --save-path result.png \
  --output-format json
```

Sizes: `1k`, `2k`, `4k`, or `WIDTHxHEIGHT`. Explicit dimensions must be multiples of 32, 512-4096 per side, and at most 3:1. PNG/JPEG/WEBP are supported.

Use `--model`, `--fallback-model`, and `--no-fallback` for control. Only 404, 429, and retry-exhausted 5xx may fall back. Bad/safety requests, 401/403, and file errors never do.

## Edit

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-edit \
  --prompt "Keep the composition, correct the title, improve hierarchy" \
  --images result.png https://example.com/reference.webp \
  --image-size auto \
  --save-path revised.png \
  --output-format json
```

Local images become Data URLs. Public URLs, Data URLs, multiple references, and continued editing are supported. Editing uses U1.5 and never falls back to U1 Fast.

## JSON fields

Success preserves `status`, `output`, and `message`, adding `model`, `operation`, `retry_count`, `fallback_used`, and `fallback_reason`. Failures include `error_type` and `error`, plus `http_status` when available.

## Troubleshooting

- 401/403: key or permission problem; no fallback.
- 400/safety: fix the request; no fallback.
- 429: generation may fall back; editing cannot.
- 5xx: U1.5 retries first; generation may fall back after exhaustion.
- Edit failure: ensure the model is not U1 Fast and every local/remote reference is readable.
- External text/vision says model missing: pass `--model` or set `SN_TEXT_MODEL` / `SN_VISION_MODEL`; the skill will not select one.
