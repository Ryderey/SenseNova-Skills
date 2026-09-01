---
name: sn-image-doctor
description: Diagnose the five-skill SenseNova image installation, Python dependencies, API key, U1.5/U1 Fast models, image endpoints, dimension rules, no-watermark default, and optional external text/vision adapters.
metadata:
  project: SenseNova-Skills
  tier: 0
  category: diagnostics
  user_visible: true
---

# sn-image-doctor

Run this before generation when installation or configuration is uncertain:

```bash
python scripts/check_environment.py --verbose
```

The check is offline and does not spend model quota. It validates:

1. Exactly these skills exist: `sn-image-base`, `sn-image-doctor`, `sn-infographic`, `sn-image-imitate`, `sn-image-resume`.
2. Python 3.9+ and the dependencies in `sn-image-base/requirements.txt`.
3. An image API key; the configured base URL; primary `sensenova-u1.5-lite`; fallback `sensenova-u1-fast`; `/images/generations` and `/images/edits`.
4. U1.5 defaults: `watermark=false`, `prompt_extend=true`, `response_format=b64_json`; valid 2K/4K sizing.
5. External text/vision models as optional. If none is set, report that the host Agent will plan and review; do not fail.

Exit code is 0 only when required image checks pass. Missing text/vision adapters never fail the doctor. Output masks secrets and must never print a complete API key.

To install dependencies:

```bash
python -m pip install -r ../sn-image-base/requirements.txt
```

Minimal image configuration:

```dotenv
SENSENOVA_API_KEY=your-key
SN_IMAGE_GEN_MODEL=sensenova-u1.5-lite
SN_IMAGE_GEN_FALLBACK_MODEL=sensenova-u1-fast
```

Do not add `SN_CHAT_MODEL` unless the user explicitly wants an external text/vision adapter.
