# sn-image-base CLI contract

Entrypoint: `python scripts/sn_agent_runner.py <command>`.

## `sn-image-generate`

Required: `--prompt`.

Compatibility parameters retained: `--negative-prompt`, `--image-size`, `--aspect-ratio`, `--seed`, `--unet-name`, `--api-key`, `--base-url`, `--poll-interval`, `--timeout`, `--insecure`, `--save-path`, `--output-format`.

Additive parameters: `--model`, `--fallback-model`, `--no-fallback`, `--watermark` / `--no-watermark`, `--prompt-extend` / `--no-prompt-extend`, `--response-format`, `--image-format`.

Default request is `POST /v1/images/generations` with model `sensenova-u1.5-lite`, `n=1`, `watermark=false`, `prompt_extend=true`, `response_format=b64_json`, and `output_format=png`.

## `sn-image-edit`

Required: `--prompt`, `--images` (one or more).

Optional: `--image-size` (`auto` default), `--aspect-ratio`, `--model`, `--api-key`, `--base-url`, `--timeout`, `--insecure`, watermark/prompt-extension booleans, `--response-format`, `--save-path`, `--output-format`.

Calls `POST /v1/images/edits`. Each `images` entry becomes `{ "image_url": ... }`; local files become Data URLs, public URLs/Data URLs pass through. U1 Fast is rejected.

## Optional compatibility commands

`sn-image-recognize` and `sn-text-optimize` preserve their prior CLI fields. Each requires an explicit model via CLI or environment. There is no built-in `SN_CHAT_MODEL`, `SN_TEXT_MODEL`, or `SN_VISION_MODEL` value.

## Output

Core success fields remain `status`, `output`, and `message` for image operations, or `status` and `result` for text/vision operations. Image operations add `model`, `operation`, `retry_count`, `fallback_used`, and `fallback_reason`. Failures add `error_type`, `error`, and `http_status` when available.

Credentials are resolved CLI > capability-specific environment > shared environment and must never be included in JSON output.
