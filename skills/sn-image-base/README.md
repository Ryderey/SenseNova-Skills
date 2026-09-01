# sn-image-base

Low-level runtime for `sensenova-u1.5-lite` generation and native editing. Default output is watermark-free and saved immediately from `b64_json`; generation can narrowly fall back to `sensenova-u1-fast`.

From this skill directory, install with `python -m pip install -r requirements.txt`, set `SENSENOVA_API_KEY`, then see [SKILL.md](SKILL.md) and [references/api_spec.md](references/api_spec.md). Agents invoking it from elsewhere should resolve the skill directory and use absolute paths.

No text or vision model is selected by default. External adapters remain available only through explicit model configuration.
