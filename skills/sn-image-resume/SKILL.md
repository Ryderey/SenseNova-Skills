---
name: sn-image-resume
description: Render supplied career facts as a fact-preserving resume image with SenseNova. Use for “SenseNova 技能” requests whose final deliverable is 简历图、简历海报、求职海报、视觉简历、作品集简历, resume poster, visual resume, or portfolio resume. Text-only resume writing and conventional document formatting use a document workflow.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: image-visualization
  priority: 8
  user_visible: true
---

# sn-image-resume

This skill preserves the complete resume-to-layout mapping and the two visual modes in `prompts/resume.md`. It must never invent credentials, dates, employers, degrees, metrics, contacts, awards, or projects.

## Runtime dependency

Before rendering, read the sibling [`sn-image-base`](../sn-image-base/SKILL.md) skill and use its absolute `PYTHON`, `RUNNER`, model defaults, fallback policy, and output contract in the commands below.

## Inputs

| Parameter | Default | Meaning |
|---|---|---|
| `resume_content` | required | User-provided resume facts |
| `portrait_image` | none | Optional supplied portrait; never synthesize an identifiable face when absent |
| `style` | inferred professional direction | Palette, tone, profession aesthetic |
| `layout_mode` | inferred, fallback `content-first` | `content-first` for readable resume information; `portfolio` for explicitly creative/editorial portfolio requests |
| `aspect_ratio` | `9:16` | Tall resume layout; dense content may use `9:21`; all base-supported ratios remain valid |
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
2. Read all of `prompts/resume.md`. Resolve `layout_mode` from the requested deliverable and content density: use `portfolio` only for an explicitly creative, editorial, or portfolio-style request; otherwise use `content-first`. Apply the selected mode's structure plus the shared language, fact, typography, and style rules.
3. Use the fact ledger to compose a complete generation prompt and save it as UTF-8 text in `$TEMP_DIR/resume_prompt.txt`. Explicitly instruct U1.5 to reproduce exact supplied strings, avoid pseudo-text, leave absent facts out, use large legible typography, omit QR codes, and render without a watermark. When `portrait_image` is absent, use an abstract typographic or profession-related visual anchor instead of inventing a human face.
4. When `portrait_image` is absent, generate with U1.5:

   ```bash
   "<absolute PYTHON path>" "<absolute RUNNER path>" sn-image-generate \
     --prompt-path "$TEMP_DIR/resume_prompt.txt" \
     --image-size "$IMAGE_SIZE" \
     --aspect-ratio "$ASPECT_RATIO" \
     --save-path "$TEMP_DIR/resume.png" \
     --output-format json
   ```

   When `portrait_image` is supplied, use native editing so the provided identity reference participates directly:

   ```bash
   "<absolute PYTHON path>" "<absolute RUNNER path>" sn-image-edit \
     --prompt-path "$TEMP_DIR/resume_prompt.txt" \
     --images "$PORTRAIT_IMAGE" \
     --image-size "$IMAGE_SIZE" \
     --aspect-ratio "$ASPECT_RATIO" \
     --save-path "$TEMP_DIR/resume.png" \
     --output-format json
   ```

5. If the Agent supports visual input, inspect the image against the fact ledger and selected layout rules. Check exact text, missing/invented facts, spelling, hierarchy, clipping, alignment, and legibility. Set `quality_passed=true` only when no fact or required-text issue remains and the page is readable.
6. For each bounded correction, save the exact correction prompt as UTF-8 text in `$TEMP_DIR/resume_correction_${ROUND}.txt`, then edit the previous image with U1.5:

   ```bash
   "<absolute PYTHON path>" "<absolute RUNNER path>" sn-image-edit \
     --prompt-path "$TEMP_DIR/resume_correction_${ROUND}.txt" \
     --images "$CURRENT_IMAGE" \
     --image-size auto \
     --save-path "$TEMP_DIR/resume_revision_${ROUND}.png" \
     --output-format json
   ```

   Each correction must identify the exact text/location and desired final state. Editing never falls back to U1 Fast.
7. Retain the best verified candidate after every round, ranking exact fact preservation and legibility before layout/style. Return that candidate rather than automatically returning the last edit. If visual inspection is unavailable, return the generated image with `visual_review_performed=false`; do not pretend it was reviewed.

## Result contract

Preserve the original core fields; model and review fields are additive:

```json
{
  "status": "ok",
  "need_main_agent_send": true,
  "output_mode": "friendly",
  "layout_mode": "content-first",
  "image": "/absolute/path/resume_revision_1.png",
  "generation_prompt": "included in verbose mode",
  "model": "sensenova-u1.5-lite",
  "fallback_used": false,
  "visual_review_performed": true,
  "quality_passed": true,
  "corrections": [
    {"round": 1, "issues": ["..."], "image": "/absolute/path/resume_revision_1.png"}
  ],
  "timing": {
    "total_elapsed_seconds": 25.12,
    "image_generation": {"elapsed_seconds": 19.89, "model": "sensenova-u1.5-lite"}
  }
}
```

`friendly` returns a short summary and the single final image. When `quality_passed=false`, it must name the unresolved fact, text, or legibility findings. `verbose` also returns the fact ledger, selected layout mode, applied style, prompt, size/ratio, generation and correction provenance, review findings, timings, and final path.
