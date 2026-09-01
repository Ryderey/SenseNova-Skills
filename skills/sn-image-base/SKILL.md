---
name: sn-image-base
description: Low-level image runtime for SenseNova U1.5 generation and native editing, plus explicitly configured text/vision adapters. Use directly or as the shared backend for the other SenseNova image skills.
metadata:
  project: SenseNova-Skills
  tier: 0
  category: image-runtime
  user_visible: false
---

# sn-image-base

Use `scripts/sn_agent_runner.py` as the stable CLI. It preserves the original `sn-image-generate`, `sn-image-recognize`, and `sn-text-optimize` contracts and adds `sn-image-edit`.

## Runtime policy

- Default image model: `sensenova-u1.5-lite`.
- Default generation-only fallback: `sensenova-u1-fast`.
- Default output: no watermark, prompt extension enabled, `b64_json` saved immediately.
- Never select a chat/text/vision model implicitly. The host Agent should plan prompts, inspect images, and judge quality with its own capabilities.
- Use `sn-text-optimize` or `sn-image-recognize` only when the caller explicitly passes `--model`, or configures `SN_TEXT_MODEL` / `SN_VISION_MODEL` (or shared `SN_CHAT_MODEL`). Missing models are errors with configuration guidance.
- Keep `nano-banana` and `openai-image` backends available only through explicit `SN_IMAGE_GEN_MODEL_TYPE` and model configuration.

Install dependencies once:

```bash
python -m pip install -r requirements.txt
```

## Generate

```bash
python scripts/sn_agent_runner.py sn-image-generate \
  --prompt "A clean bilingual product architecture infographic" \
  --image-size 2k \
  --aspect-ratio 16:9 \
  --save-path output.png \
  --output-format json
```

Important options:

| Option | Default | Meaning |
|---|---|---|
| `--model` | `SN_IMAGE_GEN_MODEL` / `sensenova-u1.5-lite` | Primary image model |
| `--fallback-model` | `SN_IMAGE_GEN_FALLBACK_MODEL` / `sensenova-u1-fast` | Text-to-image fallback |
| `--no-fallback` | false | Disable automatic fallback |
| `--image-size` | `2k` | `1k`, `2k`, `4k`, or `WIDTHxHEIGHT` |
| `--aspect-ratio` | `16:9` | Supported ratio, up to 3:1 either direction |
| `--watermark` / `--no-watermark` | false | Watermark control |
| `--prompt-extend` / `--no-prompt-extend` | true | U1.5 prompt extension |
| `--response-format` | `b64_json` | U1.5 response transport (`b64_json` or `url`) |
| `--image-format` | `png` | U1.5 output (`png`, `jpeg`, `webp`) |

Explicit dimensions must be multiples of 32, each between 512 and 4096 pixels, and no wider/taller than 3:1. U1 Fast is limited to its official 2K buckets; a 4K or explicit U1.5 request is mapped to the nearest Fast bucket only when Fast is explicitly selected or used as fallback.

Automatic fallback applies only to text-to-image when the primary returns 404, 429, or a 5xx after same-model retries. Never fall back for 400/validation or safety errors, 401/403, local file errors, network errors without an HTTP response, or image editing. JSON always reports `model`, `fallback_used`, and `fallback_reason`.

## Edit

Use native U1.5 editing for local files, public URLs, Data URLs, multiple references, and continued editing of a prior result:

```bash
python scripts/sn_agent_runner.py sn-image-edit \
  --prompt "Keep the composition; correct the Chinese title and strengthen hierarchy" \
  --images first-round.png brand-reference.webp \
  --image-size auto \
  --save-path revised.png \
  --output-format json
```

Local images are converted to image Data URLs in memory. Public and existing Data URLs pass through unchanged. U1 Fast is rejected for editing because it does not accept image input. Editing never falls back.

## Optional external text and vision adapters

Prefer the host Agent. Invoke these compatibility tools only when an external runtime is explicitly configured:

```bash
python scripts/sn_agent_runner.py sn-text-optimize \
  --user-prompt "Rewrite this image prompt" \
  --model YOUR_TEXT_MODEL \
  --output-format json

python scripts/sn_agent_runner.py sn-image-recognize \
  --user-prompt "Review typography and factual accuracy" \
  --images output.png \
  --model YOUR_VISION_MODEL \
  --output-format json
```

Supported adapter protocols remain `openai-completions` and `anthropic-messages`. See `references/api_spec.md` for the full compatibility schema.

## Configuration

Resolution priority is CLI > capability-specific environment variable > shared environment variable. The minimal setup is `SENSENOVA_API_KEY`; use `SN_IMAGE_GEN_API_KEY`, `SN_CHAT_API_KEY`, `SN_TEXT_API_KEY`, or `SN_VISION_API_KEY` only when that capability needs a different credential. The official base URL, primary model, and fallback model already have image-specific defaults.

Never place credentials in prompts, command histories, logs, examples, or committed files. Prefer temporary environment injection or a local ignored `.env`.
