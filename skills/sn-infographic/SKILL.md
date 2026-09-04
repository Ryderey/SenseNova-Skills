---
name: sn-infographic
description: Create publication-ready infographics and visual explanations with content-aware layout/style selection, prompt expansion, 1-15 user-bounded rounds, visual review, U1.5 generation/editing, and ranked results. Use for 信息图, infographic, visual summary, diagram, or data visualization requests.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: image-visualization
  priority: 9
  user_visible: true
---

# sn-infographic

This is a complete scene skill built on `sn-image-base`. Preserve the prompt library, 87 layouts, 66 styles, quality rubric, multi-round review, ranking, and Chinese/English examples.

## Runtime dependency

Resolve `INFOGRAPHIC_SKILL_DIR` as the absolute directory containing this `SKILL.md` and `POLICY` as `INFOGRAPHIC_SKILL_DIR/scripts/infographic_policy.py`. Before rendering, read the sibling [`sn-image-base`](../sn-image-base/SKILL.md) skill and use its absolute `RUNNER`, model defaults, fallback policy, and output contract in the commands below. These paths are independent of the current working directory.

## Inputs

| Parameter | Default | Rules |
|---|---|---|
| `user_prompt` | required | Facts and content to visualize |
| `max_rounds` | `1` | Integer 1-15; values above 8 must be explicitly requested |
| `output_mode` | `friendly` | `friendly` returns best image; `verbose` returns ranking and all images |
| `prompts_expand_mode` | `auto` | `auto`, `force`, or `disable` |
| `aspect_ratio` | inferred, fallback `16:9` | See `references/runtime-parameters.md` |
| `image_size` | `2k` | `2k`, `4k`, or explicit valid dimensions |
| `layout` | automatic | Any existing filename under `references/layouts/` |
| `style` | automatic | Any existing filename under `references/styles/` |

Parse explicit `key=value` directives first, then natural-language values. Run `python "<absolute POLICY path>" rounds` with the requested value, or with no value for the default, to clamp the budget. Never raise the default or a user-supplied budget automatically; values above 8 are accepted only when the user explicitly requests them. Never ask for a size when 2K is reasonable; ask about ratio only when competing choices materially change the composition. When high-risk CJK density is detected and `max_rounds` remains 1, disclose that one round is unlikely to produce exact text rather than silently spending more quota. Even 15 rounds may not remove every malformed glyph from a dense CJK image.

## Agent-first rule

Use the current host Agent to analyze content, expand prompts, inspect generated images, and judge quality. Do not require `SN_CHAT_MODEL`, `SN_TEXT_MODEL`, or `SN_VISION_MODEL`. Use `sn-text-optimize` / `sn-image-recognize` only when an external model was explicitly configured or requested.

## Workflow

1. Normalize the request and create a task-specific temporary directory.
2. Evaluate prompt completeness with `references/evaluation-standard.md`:
   - `disable`: use the original prompt.
   - `force`: expand it.
   - `auto`: expand unless every required check passes and at least 60% of optional checks pass.
3. Analyze structure, tone, audience, language, key facts, density, and canvas using `references/analysis-framework.md`. Produce a fact ledger containing every supplied number, date, proper noun, quotation, and other claim that the final image must preserve, plus a required-text inventory with a stable ID for every exact field. Write it to `$TEMP_DIR/analysis.json`, run `python "<absolute POLICY path>" density "$TEMP_DIR/analysis.json"`, and copy the returned `required_text_unit_count`, `cjk_character_count`, and `text_density_risk` into the analysis. Presentation copy may be shortened or reorganized, but every factual claim must remain traceable to this ledger.
4. Select layout and style with `references/layout-style-selection.md`:
   - valid explicit user choices win except for the documented high-risk CJK density safeguard;
   - otherwise use deterministic relevance scoring over content, audience, canvas, and density;
   - never randomly sample;
   - read only the selected layout/style definitions when assembling the prompt.
5. Build the final prompt from `references/base-prompt.md`, `references/prompts-expand-system.md`, `references/prompt-writing-rules.md`, `references/structured-content-template.md`, and the selected definitions. Apply the CJK density gate before finalizing the layout. If it changes an explicit layout, tell the user which internal columns or rows will change before rendering; proceed with text accuracy unless they explicitly prioritize layout fidelity. Preserve the fact ledger, requested language, concrete labels, visual hierarchy, no-watermark requirement, and ample readable type. Add organizational headings only when they make no new factual claim, and add every intended heading to the required-text inventory before review.
6. Generate round 1 with U1.5:

   ```bash
   python "<absolute RUNNER path>" sn-image-generate \
     --prompt "$EXPANDED_PROMPT" \
     --image-size "$IMAGE_SIZE" \
     --aspect-ratio "$ASPECT_RATIO" \
     --save-path "$TEMP_DIR/round_1.png" \
     --output-format json
   ```

   The base runtime handles the allowed U1 Fast fallback for this initial text-to-image request.
7. Inspect every generated image, including round 1, with `references/prompts-critic-system.md`, supplying the candidate image, fact ledger, stable-ID required-text inventory, and final generation prompt. Require its character-level text audit; use its weighted score and red-line gates. This is structured visual inspection, not deterministic OCR, and must not be reported as OCR. `references/evaluation-standard.md` evaluates input-prompt completeness only and must not be used as an image-quality rubric.
8. When `max_rounds > 1` and the current candidate does not meet the stop gate, run `python "<absolute POLICY path>" correction --text-violations <count>` with any applicable `--localized-visual`, `--long-text`, `--large-cjk-rewrite`, `--repeated-entry-error`, or `--layout-topology-change` flags to choose the correction mode:

   - Use native U1.5 editing only for localized visual corrections or at most three short text-label corrections that do not change layout topology.
   - Regenerate from the complete corrected prompt for any large CJK rewrite, more than three text violations in any language or density class, a repeated entry that is missing/duplicated/extra, any long text replacement, or a change to columns, section flow, or other layout topology.

   For a localized edit:

   ```bash
   python "<absolute RUNNER path>" sn-image-edit \
     --prompt "$CORRECTION_PROMPT" \
     --images "$BEST_PRIOR_IMAGE" \
     --image-size auto \
     --save-path "$TEMP_DIR/round_${ROUND}.png" \
     --output-format json
   ```

   Editing never falls back to U1 Fast. If an edit fails, retry the edit once for a transient 5xx; if it still fails and rounds remain, regenerate. If an edit reduces `exact_match_count` or factual accuracy, or introduces a new text violation, abandon that edit branch and regenerate on the next round rather than editing it again. Record every mode as `edit` or `regenerate`.
9. Stop early when the critic returns `PASS`, `score >= 0.90`, and no factual, text-legibility, or watermark red line. Otherwise track whether each candidate improves `exact_match_count`, factual accuracy, or total score over the best prior candidate; run `python "<absolute POLICY path>" stagnation <non-improving-count>` and stop when it returns `true`. This rule never requires trying an inapplicable correction mode. Return the best candidate and never exceed `max_rounds`.
10. Rank all completed candidates by: exact required-text matches, factual accuracy, and legibility first, then rubric score, then fewer violations, then later corrected round. Return the highest-quality result even if none passes; mark `quality_passed=false` in that case.

## Result contract

Keep the original core fields and add provenance fields without removing anything:

```json
{
  "status": "ok",
  "need_main_agent_send": true,
  "output_mode": "friendly",
  "expanded_prompt": "...",
  "layout": "hub-spoke",
  "style": "corporate-memphis",
  "selection_reason": "...",
  "image": "/absolute/path/round_2.png",
  "quality_passed": true,
  "rounds": [
    {
      "round": 1,
      "image": "/absolute/path/round_1.png",
      "generation_mode": "generate",
      "model": "sensenova-u1.5-lite",
      "fallback_used": false,
      "score": 0.82,
      "result": "FAIL",
      "text_audit": {
        "expected_count": 12,
        "observed_count": 12,
        "exact_match_count": 12,
        "issues": []
      },
      "violations": [],
      "rank": 2
    }
  ]
}
```

In `friendly` mode, show a short summary plus only `image`. In `verbose` mode, include selected layout/style, model/fallback provenance, per-round timing, ordered scores/violations, prompts, and every image in rank order. Never expose credentials or Base64 payloads.

## Required resources

- `references/layouts/`: all 87 layout definitions
- `references/styles/`: all 66 style definitions
- `references/layout-style-selection.md`: content/audience/canvas selection
- `references/prompts-critic-system.md`: visual red-line review
- `references/evaluation-standard.md`: prompt completeness and quality criteria
- `references/runtime-parameters.md`: size and ratio inference
- `scripts/infographic_policy.py`: single source of truth for density, correction mode, round limits, and stagnation
- `../../docs/sn-infographic-examples.md` and `../../docs/sn-infographic-examples_CN.md`: bilingual gallery
