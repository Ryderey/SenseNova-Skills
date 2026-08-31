---
name: sn-image-resume
description: Turn provided resume content into a fact-preserving, designed portfolio-resume image with a fixed visual system, U1.5 generation, and optional U1.5 editing for text/hierarchy/layout corrections. Use for 简历图, resume poster, visual resume, or portfolio resume.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: image-visualization
  priority: 8
  user_visible: true
---

# sn-image-resume

This skill preserves the complete resume-to-layout mapping and fixed visual rules in `prompts/resume.md`. It must never invent credentials, dates, employers, degrees, metrics, contacts, awards, or projects.

## Inputs

| Parameter | Default | Meaning |
|---|---|---|
| `resume_content` | required | User-provided resume facts |
| `style` | inferred professional direction | Palette, tone, profession aesthetic |
| `aspect_ratio` | `9:16` | Tall portfolio layout; all base-supported ratios remain valid |
| `image_size` | `2k` | `2k`, `4k`, or valid explicit dimensions |
| `output_mode` | `friendly` | `friendly` or `verbose` |
| `max_corrections` | `2` | Additive option, 0-3 native-edit correction rounds |

## Agent-first rule

The current Agent should map content, write the image prompt, and visually review the result. Do not require or select a chat model. Use `sn-text-optimize` / `sn-image-recognize` only when an external model was explicitly configured or requested.

## Fact ledger

Before writing the prompt, extract a ledger of exact user facts grouped as identity/title, summary, contact, education, employment, projects, skills/tools, certifications/awards/publications, and languages. Mark missing groups as absent; do not fill them with plausible content.

Condensation is allowed only to fit the visual hierarchy. Preserve names, dates, numbers, titles, organizations, and contact strings verbatim. When content is too dense, prefer fewer words and a clear notice in verbose output over tiny unreadable text.

## Workflow

1. Validate that enough resume content exists for a meaningful page.
2. Read all of `prompts/resume.md`. Apply its fixed three-zone portfolio structure, language detection, content mapping, typography hierarchy, panel system, proportions, and style-translation rules.
3. Use the fact ledger to compose a complete generation prompt. Explicitly instruct U1.5 to reproduce exact supplied strings, avoid pseudo-text, leave absent facts out, use large legible typography, and render without a watermark.
4. Generate with U1.5:

   ```bash
   python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-generate \
     --prompt "$GENERATION_PROMPT" \
     --image-size "$IMAGE_SIZE" \
     --aspect-ratio "$ASPECT_RATIO" \
     --save-path "$TEMP_DIR/resume.png" \
     --output-format json
   ```

5. If the Agent supports visual input, inspect the image against the fact ledger and layout rules. Check exact text, missing/invented facts, spelling, hierarchy, clipping, alignment, and legibility.
6. For each bounded correction, edit the previous image with U1.5 instead of regenerating the whole page:

   ```bash
   python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-edit \
     --prompt "$CORRECTION_PROMPT" \
     --images "$CURRENT_IMAGE" \
     --image-size auto \
     --save-path "$TEMP_DIR/resume_revision_${ROUND}.png" \
     --output-format json
   ```

   Each correction must identify the exact text/location and desired final state. Editing never falls back to U1 Fast.
7. Return the last verified candidate. If visual inspection is unavailable, return the generated image with `visual_review_performed=false`; do not pretend it was reviewed.

## Result contract

Preserve the original core fields; model and review fields are additive:

```json
{
  "status": "ok",
  "need_main_agent_send": true,
  "output_mode": "friendly",
  "image": "/absolute/path/resume_revision_1.png",
  "generation_prompt": "included in verbose mode",
  "model": "sensenova-u1.5-lite",
  "fallback_used": false,
  "visual_review_performed": true,
  "corrections": [
    {"round": 1, "issues": ["..."], "image": "/absolute/path/resume_revision_1.png"}
  ],
  "timing": {
    "total_elapsed_seconds": 25.12,
    "image_generation": {"elapsed_seconds": 19.89, "model": "sensenova-u1.5-lite"}
  }
}
```

`friendly` returns a short summary and the single final image. `verbose` also returns the fact ledger, applied style, prompt, size/ratio, generation and correction provenance, review findings, timings, and final path.
