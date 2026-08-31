---
name: sn-image-imitate
description: Recreate a reference image's style and layout with new user content using U1.5 native editing, reference analysis, layout-locked rewriting, bounded visual review, and best-candidate ranking. Use for 风格模仿, style imitation, or “按这张图重做”.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: image-visualization
  priority: 8
  user_visible: true
---

# sn-image-imitate

Preserve the original reference-analysis, content-rewrite, layout-consistency review, bounded retry, ranking, and detailed artifact output. Use U1.5 native editing as the primary render path so the reference pixels participate directly instead of relying only on “recognize → rewrite → regenerate”.

## Inputs

| Parameter | Default | Meaning |
|---|---|---|
| `reference_image` | required | Local image, public URL, or Data URL |
| `target_content` | required | New content and requested changes |
| `output_mode` | `friendly` | `friendly` or `verbose` |
| `aspect_ratio` | reference ratio or `16:9` | Used only when a fresh canvas is explicitly required |
| `image_size` | `2k` | U1.5 target size; native edits normally use `auto` |
| `max_attempts` | `3` | 1-8 |
| `layout_threshold` | `0.75` | Minimum layout similarity |

## Agent-first rule

Use the current Agent's visual understanding and writing ability for analysis, rewrite, and review. Do not require a default chat model. Only call `sn-image-recognize` or `sn-text-optimize` when an external model was explicitly configured/requested.

## Workflow

1. Validate the reference and target content. Never fabricate labels, values, logos, or facts.
2. Analyze the reference with `prompts/image_annotate.md`. Produce and retain a detailed blueprint covering:
   - canvas and region geometry;
   - reading order, alignment, spacing, hierarchy, connectors, and icon placement;
   - exact visible text/data where relevant;
   - palette, type character, illustration/material treatment, and background;
   - elements that must remain fixed versus content that may change.
3. Rewrite the blueprint with `prompts/caption_rewrite.md`, replacing only the requested content. Preserve region count, proportions, visual rhythm, palette relationships, and layout locks. Use the target content's language unless the user requests another language.
4. Attempt 1 uses native U1.5 editing with the original reference:

   ```bash
   python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-edit \
     --prompt "$EDIT_PROMPT" \
     --images "$REFERENCE_IMAGE" \
     --image-size auto \
     --save-path "$TEMP_DIR/attempt_1.png" \
     --output-format json
   ```

   Do not fall back to U1 Fast; it cannot accept images.
5. Review each candidate against the original reference and blueprint using `prompts/layout_review.md`. Record `layout_similarity_score`, `style_similarity_score`, content accuracy, legibility, violations, and correction instructions. A candidate passes only when layout score reaches `layout_threshold`, content is accurate, and there is no illegible/pseudo-text red line.
6. For attempts 2-8, edit the current best candidate with the original reference as a second input when useful:

   ```bash
   python "$SN_IMAGE_BASE/scripts/sn_agent_runner.py" sn-image-edit \
     --prompt "$CORRECTION_PROMPT" \
     --images "$BEST_CANDIDATE" "$REFERENCE_IMAGE" \
     --image-size auto \
     --save-path "$TEMP_DIR/attempt_${ATTEMPT}.png" \
     --output-format json
   ```

7. Stop on the first fully passing result. If none passes, rank by content accuracy, layout score, style score, legibility, and fewer violations; return the best candidate with `layout_passed=false`.
8. If native editing is unavailable, return the actual error. Use the legacy analysis → rewritten prompt → `sn-image-generate` path only when the user explicitly requests a fresh reinterpretation rather than direct imitation; mark `generation_mode=regenerate`.

## Result contract

Retain original core fields and include model provenance:

```json
{
  "status": "ok",
  "need_main_agent_send": true,
  "image": "/absolute/path/attempt_2.png",
  "reference_blueprint": "...",
  "generation_prompt": "...",
  "layout_passed": true,
  "attempts": [
    {
      "attempt": 1,
      "image": "/absolute/path/attempt_1.png",
      "generation_mode": "edit",
      "model": "sensenova-u1.5-lite",
      "fallback_used": false,
      "layout_similarity_score": 0.81,
      "style_similarity_score": 0.84,
      "violations": [],
      "rank": 1
    }
  ]
}
```

`friendly` shows a short summary and the selected image. `verbose` also shows the blueprint, rewritten prompt, attempt ranking, scores, violations, model, timing, and output paths. Never expose Base64 image data or credentials.
