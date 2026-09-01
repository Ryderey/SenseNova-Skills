---
name: sn-infographic
description: Create publication-ready infographics and visual explanations with content-aware layout/style selection, prompt expansion, 1-8 rounds, visual review, U1.5 native editing, and ranked results. Use for 信息图, infographic, visual summary, diagram, or data visualization requests.
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

Before rendering, read the sibling [`sn-image-base`](../sn-image-base/SKILL.md) skill and use its absolute `RUNNER`, model defaults, fallback policy, and output contract in the commands below.

## Inputs

| Parameter | Default | Rules |
|---|---|---|
| `user_prompt` | required | Facts and content to visualize |
| `max_rounds` | `1` | Integer 1-8 |
| `output_mode` | `friendly` | `friendly` returns best image; `verbose` returns ranking and all images |
| `prompts_expand_mode` | `auto` | `auto`, `force`, or `disable` |
| `aspect_ratio` | inferred, fallback `16:9` | See `references/runtime-parameters.md` |
| `image_size` | `2k` | `2k`, `4k`, or explicit valid dimensions |
| `layout` | automatic | Any existing filename under `references/layouts/` |
| `style` | automatic | Any existing filename under `references/styles/` |

Parse explicit `key=value` directives first, then natural-language values. Clamp rounds to 1-8. Never ask for a size when 2K is reasonable; ask about ratio only when competing choices materially change the composition.

## Agent-first rule

Use the current host Agent to analyze content, expand prompts, inspect generated images, and judge quality. Do not require `SN_CHAT_MODEL`, `SN_TEXT_MODEL`, or `SN_VISION_MODEL`. Use `sn-text-optimize` / `sn-image-recognize` only when an external model was explicitly configured or requested.

## Workflow

1. Normalize the request and create a task-specific temporary directory.
2. Evaluate prompt completeness with `references/evaluation-standard.md`:
   - `disable`: use the original prompt.
   - `force`: expand it.
   - `auto`: expand unless every required check passes and at least 60% of optional checks pass.
3. Analyze structure, tone, audience, language, key facts, density, and canvas using `references/analysis-framework.md`.
4. Select layout and style with `references/layout-style-selection.md`:
   - valid explicit user choices always win;
   - otherwise use deterministic relevance scoring over content, audience, canvas, and density;
   - never randomly sample;
   - read only the selected layout/style definitions when assembling the prompt.
5. Build the final prompt from `references/base-prompt.md`, `references/prompts-expand-system.md`, `references/prompt-writing-rules.md`, `references/structured-content-template.md`, and the selected definitions. Preserve exact facts, requested language, concrete labels, visual hierarchy, no-watermark requirement, and ample readable type.
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
7. When `max_rounds > 1`, inspect each image against `references/prompts-critic-system.md` and `references/evaluation-standard.md`. Score factual accuracy, text legibility, structural completeness, layout balance, connector clarity, visual hierarchy, style consistency, and absence of watermarks. Record every violation with an imperative correction.
8. For rounds 2-8, prefer native U1.5 editing of the best prior image to reduce layout drift:

   ```bash
   python "<absolute RUNNER path>" sn-image-edit \
     --prompt "$CORRECTION_PROMPT" \
     --images "$BEST_PRIOR_IMAGE" \
     --image-size auto \
     --save-path "$TEMP_DIR/round_${ROUND}.png" \
     --output-format json
   ```

   Editing never falls back to U1 Fast. If an edit fails, retry the edit once for a transient 5xx; if it still fails and rounds remain, make a fresh U1.5 generation with the corrected full prompt and record the mode as `regenerate`.
9. Stop early on a clean PASS or a score of at least 0.90 with no factual/text red-line violation. Otherwise finish the budget.
10. Rank all completed candidates by: factual accuracy and legibility first, then rubric score, then fewer violations, then later corrected round. Return the highest-quality result even if none passes; mark `quality_passed=false` in that case.

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
- `../../docs/sn-infographic-examples.md` and `../../docs/sn-infographic-examples_CN.md`: bilingual gallery
