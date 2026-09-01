# Install the Image & Visualization Skills

[简体中文](INSTALL_CN.md)

## Requirements

- Git
- Python 3.9+
- An Agent Skills-compatible host, or direct CLI use
- A SenseNova API key with image access

## Clone and install

```bash
git clone --branch refactor/image-viz --single-branch https://github.com/Ryderey/SenseNova-Skills.git
cd SenseNova-Skills
python -m venv .venv
```

Activate the environment:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the only runtime dependency set:

```bash
python -m pip install -r skills/sn-image-base/requirements.txt
```

## Configure

Copy `.env.example` to `.env` and set the key. `.env` is ignored by Git.

```dotenv
SENSENOVA_API_KEY=your-key
```

This shared key is enough for the default setup. Optional overrides let a capability use a different credential:

- `SN_IMAGE_GEN_API_KEY`: image generation and editing.
- `SN_CHAT_API_KEY`: shared fallback for explicitly configured text and vision adapters.
- `SN_TEXT_API_KEY`: text adapter only; overrides `SN_CHAT_API_KEY`.
- `SN_VISION_API_KEY`: vision adapter only; overrides `SN_CHAT_API_KEY`.

Key resolution is `--api-key` > direct capability key > `SN_CHAT_API_KEY` where applicable > `SENSENOVA_API_KEY`. Leave every override empty when all capabilities use the same SenseNova key.

The image defaults are already:

```dotenv
SN_IMAGE_GEN_BASE_URL=https://token.sensenova.cn/v1
SN_IMAGE_GEN_MODEL=sensenova-u1.5-lite
SN_IMAGE_GEN_FALLBACK_MODEL=sensenova-u1-fast
```

Do not set `SN_CHAT_MODEL` unless you explicitly want the low-level external text/vision adapters. The current Agent should normally plan prompts and review images itself.

## Validate

```bash
python skills/sn-image-doctor/scripts/check_environment.py --verbose
```

Then run one local generation command or ask the host Agent to create an infographic.

## Install into an Agent Skills host

Copy or symlink exactly the five directories under `skills/` into the host's skills directory:

- `sn-image-base`
- `sn-image-doctor`
- `sn-infographic`
- `sn-image-imitate`
- `sn-image-resume`

Restart or reload the host so it discovers updated `SKILL.md` files. No PPT, search, research, data-analysis, or Workbench runtime is required by this branch.

## Optional external adapters

To preserve compatibility with an explicitly chosen text/vision provider, configure its key, base URL, model, and protocol. Model names have no built-in default:

```dotenv
SN_TEXT_MODEL=your-text-model
SN_VISION_MODEL=your-vision-model
SN_CHAT_TYPE=openai-completions
```

## Troubleshooting

- 401/403: check the key and account authorization; the runtime will not hide it with fallback.
- 400 or safety error: fix the prompt/parameters; no fallback occurs.
- 404/429/retry-exhausted 5xx during text-to-image: the default runtime may use U1 Fast and records why.
- Editing failure: U1 Fast does not support image input, so editing never falls back.
- Invalid size: use multiples of 32, 512-4096 pixels per side, and at most 3:1.

See [the image guide](docs/sn-image-generate_en.md) for commands and output fields.
