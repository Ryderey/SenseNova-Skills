# sn-image-base CLI contract

Entrypoint from the `sn-image-base` skill directory: `python scripts/sn_agent_runner.py <command>`. From any other working directory, resolve the skill directory and invoke `scripts/sn_agent_runner.py` by its absolute path.

The current SenseNova image model is `sensenova-u1.6-lite`; it is the only image model in the official model overview. Endpoints (`/v1/images/generations`, `/v1/images/edits`) and Bearer authentication are unchanged.

## `sn-image-generate`

Required: exactly one of inline `--prompt` or UTF-8 `--prompt-path`.

Compatibility parameters retained: `--image-size`, `--aspect-ratio`, `--api-key`, `--base-url`, `--timeout`, `--insecure`, `--save-path`, `--output-format`. Legacy `--negative-prompt`, `--seed`, `--unet-name`, and `--poll-interval` flags are parsed but fail clearly because the current backends do not implement them; express visual constraints in `--prompt`.

Additive parameters: `--model`, `--fallback-model`, `--no-fallback`, `--watermark` / `--no-watermark`, `--self-correction` / `--no-self-correction`, `--prompt-extend` / `--no-prompt-extend`, `--response-format`, `--image-format`.

Default request is `POST /v1/images/generations` with model `sensenova-u1.6-lite`, `n=1`, `watermark=false`, `self_correction=true`, `prompt_extend=true`, `response_format=b64_json`, and `output_format=png`.

### Request fields

| Field | Server default | Sent by this runtime |
|---|---|---|
| `model` | — | `sensenova-u1.6-lite` |
| `size` | `auto` | `2k` for generation; official `2K`/`4K` constants or explicit `WIDTHxHEIGHT` |
| `watermark` | `true` | `false` explicitly (`--watermark` / `--no-watermark`) |
| `self_correction` | `true` | `true` explicitly (`--self-correction` / `--no-self-correction`) |
| `prompt_extend` | `true` | `true` explicitly |
| `response_format` | `b64_json` | `b64_json` explicitly |
| `output_format` | `png` | `png` explicitly |
| `n` | — | `1` |

`watermark` and `self_correction` are always sent explicitly so a server-side default change cannot silently alter output. `self_correction` is a U1.6 boolean that lets the model correct rendered text; disable it with `--no-self-correction` when exact prompt-only rendering or lower latency is preferred.

The explicit no-watermark default is a product choice. SenseNova documents `watermark=false` as free during public beta and a premium paid feature afterward; model usage otherwise follows the account plan and credit rules.

### Sizes

The server-side `size` default is `auto`: on edits it adapts to the primary image, and on generation the server chooses the resolution. Official named constants are `2K` and `4K`. Explicit `WIDTHxHEIGHT` values must be multiples of 32, each side between 512 and 4096 pixels, and at most 3:1. `2K` at 16:9 / 9:16 uses the official recommended `2720x1536` / `1536x2720`.

This runtime keeps `2k` as the generation default for determinism; `--image-size auto` is accepted for both generation and editing. `auto` cannot be combined with `--aspect-ratio`; for presets the ratio defaults to 16:9.

`1K` is a repository compatibility preset, not an official U1.6 resolution constant. The runtime maps it to a valid explicit `WIDTHxHEIGHT` that satisfies the constraints above.

### Fallback

`SN_IMAGE_GEN_FALLBACK_MODEL` is empty by default, so automatic fallback is off. Configure it (or pass `--fallback-model`) explicitly to enable generation-only fallback on 404, 429, or retry-exhausted 5xx; `--no-fallback` disables it for a single call. `sensenova-u1.5-fast` and `sensenova-u1-fast` are retired and unsupported by this bundle. Any transitional platform routing is not a compatibility guarantee; release metadata blocks these IDs and users must migrate to `sensenova-u1.6-lite`.

## `sn-image-edit`

Required: exactly one of inline `--prompt` or UTF-8 `--prompt-path`, plus `--images` (one or more).

Optional: `--image-size` (`auto` default), `--aspect-ratio`, `--model`, `--api-key`, `--base-url`, `--timeout`, `--insecure`, watermark/self-correction/prompt-extension booleans, `--response-format`, `--save-path`, `--output-format`.

Calls `POST /v1/images/edits`. At most 5 reference images are accepted and the first one is the primary image being edited; the rest are references. Each local file, public HTTP(S) URL, or Data URL is read through a 64 MiB / 40-million-pixel validation boundary, normalized to PNG/JPEG when needed, and emitted as `{ "image_url": "data:..." }`. Editing never falls back automatically. Retired U1.5 IDs are unsupported; use `sensenova-u1.6-lite`.

For `response_format=url`, the runtime downloads immediately. U1.6 Lite generation and edit URLs expire after 24 hours.

## `sn-check-update`

Forces a repository Release check and prints the installed/latest versions, release notes, and update path for Git, symlink, or copied installs. It does not call SenseNova model endpoints and does not require an image API key.

Exit code `0` means no required update blocks work (including current, unpublished, or unavailable checks). Exit code `3` means a required release, unsupported local version, or retired configured model blocks work; the reason is printed every time. Other runner commands perform the same cached check automatically before execution and also return `3` when blocked.

## Optional compatibility commands

`sn-image-recognize` and `sn-text-optimize` preserve their prior CLI fields. Each requires an explicit model via CLI or environment. There is no built-in `SN_CHAT_MODEL`, `SN_TEXT_MODEL`, or `SN_VISION_MODEL` value.

## Output

Core success fields remain `status`, `output`, and `message` for image operations, or `status` and `result` for text/vision operations. Image operations add `model`, `operation`, `retry_count`, `fallback_used`, and `fallback_reason`. Failures add `error_type`, `error`, and `http_status` when available.

Credentials are resolved CLI > capability-specific environment > shared environment and must never be included in JSON output.