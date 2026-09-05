# sn-image-base

The `python` command below assumes you have created and activated a virtual environment using the [installation guide](../../INSTALL.md). Otherwise, use that environment's interpreter by absolute path. Dependency installation, Doctor, and the Agent host must use the same interpreter.

Low-level runtime for `sensenova-u1.5-lite` generation and native editing. Default output is watermark-free and saved immediately from `b64_json`; generation can narrowly fall back to `sensenova-u1-fast`.

From this skill directory, install with `python -m pip install -r requirements.txt`, set `SENSENOVA_API_KEY`, then see [SKILL.md](SKILL.md) and [references/api_spec.md](references/api_spec.md). Agents invoking it from elsewhere should use the same Python interpreter that passes Doctor plus an absolute script path. Prefer a UTF-8 `--prompt-path` for long or punctuation-heavy prompts.

The runtime uses process values first, then `SN_ENV_FILE`, then the nearest `.env` found from the current working directory upward.

No text or vision model is selected by default. External adapters remain available only through explicit model configuration.
