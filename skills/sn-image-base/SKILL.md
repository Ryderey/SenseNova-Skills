---
name: sn-image-base
description: Shared SenseNova U1.6 runtime for generation and native image editing. Use directly for “SenseNova 技能” requests to combine, merge, or collage multiple supplied images, including 图片合成、多图合成、图片融合、多图融合、融图或拼图; also use it as the backend for other SenseNova image skills.
metadata:
  project: SenseNova-Skills
  tier: 0
  category: image-runtime
  user_visible: false
---

# sn-image-base

Use `scripts/sn_agent_runner.py` as the stable CLI. It preserves the original `sn-image-generate`, `sn-image-recognize`, and `sn-text-optimize` contracts and adds `sn-image-edit`.

## Runtime paths

Resolve `BASE_SKILL_DIR` as the absolute directory containing this `SKILL.md`. Resolve `RUNNER` as `BASE_SKILL_DIR/scripts/sn_agent_runner.py`, `MANAGER` as `BASE_SKILL_DIR/scripts/sn_task_files.py`, and `REQUIREMENTS` as `BASE_SKILL_DIR/requirements.txt`. Resolve `PYTHON` as the same interpreter that passes `sn-image-doctor`; prefer the repository `.venv` interpreter when it exists and has the required packages. Use absolute paths regardless of the current working directory, and never assume the host inherited a previously activated shell environment. On PowerShell, invoke a quoted executable path with the call operator (`& "<absolute PYTHON path>" ...`); on POSIX shells, execute the quoted path directly. These are logical path names, not environment variables; never ask the user to configure them.

## Runtime policy

- Default image model: `sensenova-u1.6-lite`.
- Generation-only fallback: off by default (`SN_IMAGE_GEN_FALLBACK_MODEL` is empty). Set it or `--fallback-model` explicitly to enable it; `sensenova-u1.5-fast` / `sensenova-u1-fast` are retired and kept only for legacy compatibility.
- Default output location: when `--save-path` is omitted, generated and edited images are saved to `SN_IMAGE_OUTPUT_DIR`, or `~/Pictures/SenseNova` by default; an explicit `--save-path` keeps its exact meaning.
- Default output: no watermark, prompt extension enabled, text self-correction enabled (`self_correction=true` sent explicitly), `b64_json` saved immediately. SenseNova documents `watermark=false` as free during public beta and a premium paid feature afterward; disclose that cost boundary when it is relevant to production use.
- Never select a chat/text/vision model implicitly. The host Agent should plan prompts, inspect images, and judge quality with its own capabilities.
- Use `sn-text-optimize` or `sn-image-recognize` only when the caller explicitly passes `--model`, or configures `SN_TEXT_MODEL` / `SN_VISION_MODEL` (or shared `SN_CHAT_MODEL`). Missing models are errors with configuration guidance.
- Keep `nano-banana` and `openai-image` backends available only through explicit `SN_IMAGE_GEN_MODEL_TYPE` and model configuration.
- Keep task intermediates — assembled prompt files, analysis or blueprint JSON, and non-final candidates — in a task directory created by the manager (`MANAGER begin`, under `tempfile.gettempdir()/sensenova-tasks/<task-id>`; the root is per-user and owner-only on POSIX); never write them into the user's project or the skill directories. Deliver with `MANAGER publish`, which copies the selected image to its formal location and then removes the whole task directory; run `MANAGER abort` when the task fails or the user cancels. Never delete files a user supplied or the target of an explicit `--save-path`.

Install dependencies once:

```bash
"<absolute PYTHON path>" -B -m pip install -r "<absolute REQUIREMENTS path>"
```

## Task files and delivery

`MANAGER` owns the lifecycle of per-task temporary files; run every command with `-B` as well:

```bash
"<absolute PYTHON path>" -B "<absolute MANAGER path>" begin -o json
"<absolute PYTHON path>" -B "<absolute MANAGER path>" publish "<task dir>" "<selected image>" --final-path "<target>" -o json
"<absolute PYTHON path>" -B "<absolute MANAGER path>" abort "<task dir>" -o json
"<absolute PYTHON path>" -B "<absolute MANAGER path>" gc -o json
```

- `begin` collects expired task directories, then creates a unique guarded directory under the task root (`tempfile.gettempdir()/sensenova-tasks/`, or a per-user `sensenova-tasks-<uid>` with owner-only permissions on POSIX) and prints its absolute path. Write only your task's own intermediates into it.
- `publish` verifies the selected image, copies it atomically to the formal location (an explicit `--final-path`, otherwise the formal output directory with a unique name), removes the whole task directory, and prints the formal path to deliver. On failure it keeps the task directory and the original image so the call can be retried.
- `abort` removes the whole task directory after a failure or cancellation. Report a deletion failure instead of claiming the files were cleaned up.
- `gc` is also run automatically by `begin`; it collects this tool's directories under the dedicated root only after 48 hours of inactivity — the newest of the matching marker's creation time and the modification time of every entry in the directory, so both creating and rewriting files keeps a task alive (`SN_TASK_RETENTION_HOURS` overrides the window). A task left untouched for the whole window is treated as abandoned. Locks live in the sibling `.locks` directory and are held across the whole check-and-delete step, so `gc`, `publish`, and `abort` never interleave on the same task: whoever holds the lock first wins, and the others fail fast or skip; orphaned lock files are swept. Linked, recent, and out-of-root entries are skipped, and a task root or `.locks` directory that is itself a symlink, junction, or reparse point is rejected before anything is scanned, created, or removed. Users' own files and explicit `--save-path` targets are never touched.

## Generate

```bash
"<absolute PYTHON path>" -B "<absolute RUNNER path>" sn-image-generate \
  --prompt "A clean bilingual product architecture infographic" \
  --image-size 2k \
  --aspect-ratio 16:9 \
  --save-path output.png \
  --output-format json
```

Important options:

| Option | Default | Meaning |
|---|---|---|
| `--prompt` / `--prompt-path` | required | Inline prompt or UTF-8 prompt file; prefer the file form for long or multiline copy |
| `--model` | `SN_IMAGE_GEN_MODEL` / `sensenova-u1.6-lite` | Primary image model |
| `--fallback-model` | `SN_IMAGE_GEN_FALLBACK_MODEL` / empty (off) | Text-to-image fallback; explicit configuration only |
| `--no-fallback` | false | Disable automatic fallback |
| `--image-size` | `2k` | Official `2k`/`4k`, local compatibility preset `1k` mapped to explicit dimensions, or `WIDTHxHEIGHT` |
| `--aspect-ratio` | `16:9` | Supported ratio, up to 3:1 either direction |
| `--watermark` / `--no-watermark` | false | Watermark control; the server default is `true`, so `false` is sent explicitly |
| `--self-correction` / `--no-self-correction` | true | Text self-correction, sent explicitly as `self_correction` |
| `--prompt-extend` / `--no-prompt-extend` | true | U1.6 prompt extension |
| `--response-format` | `b64_json` | U1.6 response transport (`b64_json` or `url`) |
| `--image-format` | `png` | U1.6 output (`png`, `jpeg`, `webp`) |

Explicit dimensions must be multiples of 32, each between 512 and 4096 pixels, and no wider/taller than 3:1. The server-side `size` default is `auto`; this runtime sends the official `2k`/`4k` constants or explicit dimensions for generation by default and also accepts `auto` (server chooses; cannot combine with `--aspect-ratio`, presets default to 16:9), and `1k` is a local preset mapped to explicit dimensions. An explicitly configured fallback preserves the requested resolution.

When URL transport is selected, download immediately: U1.6 Lite generation and edit URLs expire after 24 hours. The default `b64_json` path is not subject to URL expiry.

Automatic fallback applies only to text-to-image when the primary returns 404, 429, or a 5xx after same-model retries. Never fall back for 400/validation or safety errors, 401/403, local file errors, network errors without an HTTP response, or image editing. JSON always reports `model`, `fallback_used`, and `fallback_reason`.

## Edit

Use native U1.6 editing for local files, public URLs, Data URLs, multiple references, and continued editing of a prior result:

```bash
"<absolute PYTHON path>" -B "<absolute RUNNER path>" sn-image-edit \
  --prompt "Keep the composition; correct the Chinese title and strengthen hierarchy" \
  --images first-round.png brand-reference.webp \
  --image-size auto \
  --save-path revised.png \
  --output-format json
```

Local files, public HTTP(S) URLs, and existing Data URLs are read through the same bounded image validator, normalized to PNG/JPEG where needed, and sent as Data URLs. Inputs are limited to 64 MiB and 40 million decoded pixels. Editing accepts at most 5 reference images, and the first one is the primary image being edited. The retired `sensenova-u1.5-fast` can still be selected explicitly for legacy compatibility. Editing never falls back automatically.

Both image commands accept `--prompt-path <UTF-8 file>` instead of `--prompt`; the options are mutually exclusive. Prefer the file form for assembled infographic, resume, and correction prompts so shell quoting cannot alter Chinese text or line breaks.

## Optional external text and vision adapters

Prefer the host Agent. Invoke these compatibility tools only when an external runtime is explicitly configured:

```bash
"<absolute PYTHON path>" -B "<absolute RUNNER path>" sn-text-optimize \
  --user-prompt "Rewrite this image prompt" \
  --model YOUR_TEXT_MODEL \
  --output-format json

"<absolute PYTHON path>" -B "<absolute RUNNER path>" sn-image-recognize \
  --user-prompt "Review typography and factual accuracy" \
  --images output.png \
  --model YOUR_VISION_MODEL \
  --output-format json
```

Supported adapter protocols remain `openai-completions` and `anthropic-messages`. See `references/api_spec.md` for the full compatibility schema.

## Configuration

Resolution priority is CLI > capability-specific environment variable > shared environment variable. The minimal setup is `SENSENOVA_API_KEY`; use `SN_IMAGE_GEN_API_KEY`, `SN_CHAT_API_KEY`, `SN_TEXT_API_KEY`, or `SN_VISION_API_KEY` only when that capability needs a different credential. The official base URL and primary model already have image-specific defaults; the fallback model default is empty, so automatic fallback is off until configured.

Environment lookup order is: existing process values, the file named by `SN_ENV_FILE`, then the nearest `.env` found from the current working directory upward. File values never override existing process values. `sn-image-doctor --verbose` reports the selected Python executable and environment-file path without printing secrets.

### Credential discovery

When a required key is absent from the current process environment, check the host's normal persistent environment locations before searching any unrelated config, JSON, or session files:

- Windows: query the User environment first (`HKEY_CURRENT_USER\Environment`), then the Machine environment (`HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\Environment`). Prefer `[Environment]::GetEnvironmentVariable("SENSENOVA_API_KEY", "User")`, then `"Machine"`; assign a found value to `$env:SENSENOVA_API_KEY` and run the command in that same PowerShell invocation. Never print the value or use a registry command that exposes it in tool output.
- Linux/macOS: check whether `SENSENOVA_API_KEY` is declared in `~/.bashrc`, `~/.zshrc`, or the project `.env`, in that order. Search by variable name while returning filenames only, then load the trusted matching file and run the command in the same shell. Never print the matching line or value.

Apply the same platform lookup to a capability-specific key when one is expected. Stop after these locations unless the user identifies another credential store. A persistent value may be missing from an already-running Agent process; same-shell injection or restarting the host makes it available without copying the key into `--api-key`.

Never place credentials in prompts, command histories, logs, examples, or committed files. Prefer temporary environment injection or a local ignored `.env`.
