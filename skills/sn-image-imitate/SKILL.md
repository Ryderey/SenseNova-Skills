---
name: sn-image-imitate
description: Recreate a supplied reference image's style and layout with new user content using SenseNova. Use for “SenseNova 技能” requests involving 仿图、参考图重做、照图改版、风格模仿、保留版式换内容或以图改图. Apply when a reference image defines the target layout or visual direction.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: image-visualization
  priority: 8
  user_visible: true
---

# sn-image-imitate

Preserve the original reference-analysis, content-rewrite, layout-consistency review, bounded retry, ranking, and detailed artifact output. Use U1.5 native editing as the primary render path so the reference pixels participate directly instead of relying only on “recognize → rewrite → regenerate”.

## Runtime dependency

Before analysis, read the sibling [`sn-image-base`](../sn-image-base/SKILL.md) skill and use its absolute `PYTHON`, `RUNNER`, model defaults, fallback policy, output contract, and Credential discovery procedure. Resolve `DOCTOR` as the sibling `sn-image-doctor/scripts/check_environment.py` and `POLICY` as this skill's `scripts/imitation_policy.py`. Use absolute paths for all three scripts.

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

0. Before reference analysis, run `"<absolute PYTHON path>" "<absolute DOCTOR path>" --require-edit`. This check is offline. If the image API key is missing from the process, immediately follow `sn-image-base` Credential discovery, inject a persistent value into the same shell without printing it, and rerun the Doctor. Stop before analysis when the Doctor still fails.
1. Validate the reference and target content, create `$TEMP_DIR`, and save the user's target request verbatim to `$TEMP_DIR/target_content.txt`. Never fabricate labels, values, logos, or facts.
2. Analyze the reference with `prompts/image_annotate.md`. Save its `LAYOUT_BLUEPRINT_JSON` object to `$TEMP_DIR/reference_blueprint.json`, including a stable-ID `source_topic_elements` inventory. Produce and retain a detailed blueprint covering:
   - canvas and region geometry;
   - reading order, alignment, spacing, hierarchy, connectors, and icon placement;
   - exact visible text/data where relevant;
   - palette, type character, illustration/material treatment, and background;
   - elements that must remain fixed versus content that may change.
3. Rewrite the blueprint with `prompts/caption_rewrite.md`, save its structured result to `$TEMP_DIR/rewrite.json`, and save the exact `rewritten_caption` value as UTF-8 text in `$TEMP_DIR/rewritten_caption.txt`. It must declare `target_language`, user-authorized `allowed_foreign_terms`, and exactly one ledger disposition for every source topic ID. General requests to preserve the reference's style or layout never authorize semantic carry-over. Translate every topic-bearing element to the target topic while preserving its structural and stylistic role, region count, proportions, visual rhythm, palette relationships, and layout locks. Then run:

   ```bash
   "<absolute PYTHON path>" "<absolute POLICY path>" \
     "$TEMP_DIR/reference_blueprint.json" \
     "$TEMP_DIR/rewrite.json" \
     "$TEMP_DIR/target_content.txt"
   ```

   Record its JSON output as `ledger_validation`. Reject and repair the rewrite until it returns `valid=true`, allowing at most two repair passes before returning its errors without rendering. It deterministically checks ledger coverage, action/evidence fields, and unapproved Latin-script fragments in Chinese captions; semantic correctness remains the Agent's responsibility.
4. Attempt 1 uses native U1.5 editing with the original reference and only `rewritten_caption` as the editing instruction:

   ```bash
   "<absolute PYTHON path>" "<absolute RUNNER path>" sn-image-edit \
     --prompt-path "$TEMP_DIR/rewritten_caption.txt" \
     --images "$REFERENCE_IMAGE" \
     --image-size auto \
     --no-prompt-extend \
     --save-path "$TEMP_DIR/attempt_1.png" \
     --output-format json
   ```

   Do not fall back to U1 Fast; it cannot accept images.
5. Review each candidate with `prompts/layout_review.md`, supplying the original reference, candidate, target content, `target_language`, `allowed_foreign_terms`, `rewritten_caption`, and the complete `semantic_replacement_ledger`. Record all fields in its schema. A candidate passes only when layout score reaches `layout_threshold`, target content is accurate, all required text is legible, every ledger entry is valid, and both `semantic_residue` and `language_contamination` are empty.
6. For attempts 2-8, save the exact correction prompt as UTF-8 text in `$TEMP_DIR/correction_${ATTEMPT}.txt`, then edit the current best candidate with the original reference as a second input when useful:

   ```bash
   "<absolute PYTHON path>" "<absolute RUNNER path>" sn-image-edit \
     --prompt-path "$TEMP_DIR/correction_${ATTEMPT}.txt" \
     --images "$BEST_CANDIDATE" "$REFERENCE_IMAGE" \
     --image-size auto \
     --no-prompt-extend \
     --save-path "$TEMP_DIR/attempt_${ATTEMPT}.png" \
     --output-format json
   ```

7. Stop on the first fully passing result. If none passes, rank by content accuracy, layout score, style score, legibility, and fewer violations; return the best candidate with `layout_passed=false`.
8. If native editing is unavailable, return the actual error. Use the legacy analysis → rewritten prompt → `sn-image-generate` path only when the user explicitly requests a fresh reinterpretation rather than direct imitation; pass `--no-prompt-extend` there as well and mark `generation_mode=regenerate`.

## Result contract

Retain original core fields and include model provenance:

```json
{
  "status": "ok",
  "need_main_agent_send": true,
  "image": "/absolute/path/attempt_2.png",
  "reference_blueprint": "...",
  "generation_prompt": "...",
  "target_language": "<inferred BCP-47 language tag>",
  "allowed_foreign_terms": [],
  "ledger_validation": {"valid": true, "errors": []},
  "semantic_replacement_ledger": [
    {
      "reference_element_id": "topic_001",
      "reference_element": "pig mascot",
      "action": "replace",
      "target_element": "chicken mascot",
      "explicit_user_request_quote": null,
      "compatibility": "compatible",
      "contradiction_acknowledgment_quote": null
    }
  ],
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
      "content_accuracy_score": 1.0,
      "text_legibility_score": 0.95,
      "semantic_residue": [],
      "language_contamination": [],
      "violations": [],
      "rank": 1
    }
  ]
}
```

`friendly` shows a short summary and the selected image. When `layout_passed=false`, it must also name the unresolved content, text, or layout findings that prevented a pass. `verbose` also shows the blueprint, rewritten prompt, semantic replacement ledger, attempt ranking, scores, violations, model, timing, and output paths. Never expose Base64 image data or credentials.
