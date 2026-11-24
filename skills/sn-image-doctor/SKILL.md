---
name: sn-image-doctor
description: Diagnose the five-skill SenseNova image installation, Python dependencies, API key, the U1.6 Lite model, image endpoints, dimension rules, no-watermark default, optional external text/vision adapters, and repository release updates.
metadata:
  project: SenseNova-Skills
  version: 1.1.0
  tier: 0
  category: diagnostics
  user_visible: true
---

# sn-image-doctor

## Runtime paths

Resolve `DOCTOR_SKILL_DIR` as the absolute directory containing this `SKILL.md`. Resolve `DOCTOR` as `DOCTOR_SKILL_DIR/scripts/check_environment.py` and `BASE_REQUIREMENTS` as the sibling `sn-image-base/requirements.txt`. Run it with the Python interpreter the host will use for image work; try the repository `.venv` interpreter first when present. Use absolute paths regardless of the current working directory. These are logical path names, not environment variables; never ask the user to configure them.

Run this before generation when installation or configuration is uncertain:

```bash
"<absolute PYTHON path>" -B "<absolute DOCTOR path>" --verbose
```

The local checks are offline and do not spend model quota. They validate:

1. These required skills exist and have matching readable `VERSION` files: `sn-image-base`, `sn-image-doctor`, `sn-infographic`, `sn-image-imitate`, `sn-image-resume`. Other installed skills are allowed.
2. Python 3.9+, its exact executable path, and the dependencies in `sn-image-base/requirements.txt`.
3. An image API key, configured backend/model names, a valid base URL, and the image endpoints. Custom model names are reported rather than rejected.
4. U1.6 defaults: `watermark=false`, `prompt_extend=true`, `response_format=b64_json`; valid 2K/4K sizing. Retired U1.5 IDs are unsupported; the legacy Base64 payload shape is validated only to keep diagnostics backward-compatible. Doctor reports the configured fallback but does not claim to enforce retirement offline; the repository update check enforces Release retirement metadata when enabled.
5. The loaded `.env` path, if any. `SN_ENV_FILE` selects an explicit file; otherwise lookup starts at the current working directory.
6. External text/vision models as optional. Incomplete optional adapters produce warnings and do not block image work. Use `--require-text` or `--require-vision` only when that adapter is required by the current task.

Exit code is 0 only when required image checks pass. Before imitation or another native editing workflow, add `--require-edit` to require the SenseNova editing backend. The local checks are offline and do not verify remote credentials or service availability. Output masks secrets and must never print a complete API key.

## Repository update check

After the local checks, Doctor checks the repository's latest published GitHub Release unless `--no-update-check` is set. The result is cached for 24 hours, sends no credentials or task content, and never calls SenseNova model endpoints. A network failure does not introduce a new failure, but a previously cached required update still blocks image work.

To force a fresh check without running the local diagnostics:

```bash
"<absolute PYTHON path>" -B "<absolute DOCTOR path>" --check-update
```

The output shows the installed and latest versions, release notes, and the update path for Git, symlink, or copied installs. Notices use `UPDATE INFO`, `UPDATE RECOMMENDED`, or `UPDATE REQUIRED`. Exit code 3 means a required repository update blocks image work and the reason is printed every time. Set `SN_SKILLS_NO_UPDATE_CHECK=1` to disable automatic checks; `--check-update` still forces one.

If the image API key check fails, follow `sn-image-base`'s **Credential discovery** order immediately: process environment, then Windows User/Machine persistent environment or Linux/macOS `~/.bashrc`, `~/.zshrc`, and project `.env`. Do not search unrelated config, JSON, or session files, and never print the key. After finding a persistent value, inject it and rerun the doctor in the same shell invocation, or restart the host so a new process inherits it.

To install dependencies:

```bash
"<absolute PYTHON path>" -B -m pip install -r "<absolute BASE_REQUIREMENTS path>"
```

Minimal image configuration:

```dotenv
SENSENOVA_API_KEY=your-key
SN_IMAGE_GEN_MODEL=sensenova-u1.6-lite
SN_IMAGE_GEN_FALLBACK_MODEL=
```

Do not add `SN_CHAT_MODEL` unless the user explicitly wants an external text/vision adapter.
