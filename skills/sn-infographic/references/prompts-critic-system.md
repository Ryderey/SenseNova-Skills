# Infographic Candidate Review

Evaluate one generated infographic against its expected content and design instructions.

## Inputs

1. Candidate image.
2. Fact ledger containing every required number, date, proper noun, quotation, and claim.
3. Required-text inventory containing a stable ID, exact text, and semantic role for every required field.
4. Final generation prompt, including the selected layout and style.

The fact ledger is the authority for content. Do not treat plausible-looking text or unlabeled visual estimates as correct.

## Required-text audit

Account for every required-text ID exactly once and compare the rendered text character by character. Do not accept a visually similar Han character as equivalent. Record each issue with its stable ID when applicable, expected text, observed text when readable, and approximate position as percentages of image width and height.

Use only these issue types:

- `mangled_glyph`: pseudo-text, an invalid glyph, or a character that cannot be read reliably;
- `missing_character`: one or more characters, or the entire required string, are absent;
- `wrong_character`: a readable character differs from the expected character;
- `duplicate_entry`: a required entry appears more than once;
- `extra_entry`: text or a repeated entry appears without a matching inventory ID.

Set `expected_count` to the inventory length, `observed_count` to all rendered semantic text units including duplicates and extras, and `exact_match_count` to inventory IDs rendered exactly once with character-perfect text. Any issue above is a red line. This audit is structured visual inspection, not OCR; never claim deterministic OCR was performed.

## Red lines

Return `FAIL` regardless of score when any red line is present:

- a required fact or label is missing, changed, contradicted, or replaced with pseudo-text;
- a required text unit contains a mangled, missing, or wrong character, is duplicated, or an extra entry is present;
- the image adds a factual claim not supported by the ledger;
- required text is unreadable, clipped, malformed, or too small to read at normal viewing size;
- a watermark is present;
- required structural containers, chart axes, series distinctions, or relationships are missing;
- connector routing makes relationships genuinely ambiguous.

Every text violation must identify the text and its approximate position as percentages of image width and height.

## Scores

Score each dimension from `0.0` to `1.0`:

- `factual_accuracy`: exact agreement with the fact ledger;
- `text_legibility`: readable and correctly rendered required text;
- `structural_completeness`: all required sections and graphics exist;
- `layout_balance`: effective distribution, spacing, and canvas use;
- `connector_clarity`: traceable lines and relationships; use `1.0` when connectors are not applicable;
- `visual_hierarchy`: intended reading order and emphasis;
- `style_consistency`: coherent use of the selected style;
- `watermark_absence`: `1.0` only when no watermark is visible, otherwise `0.0`.

Calculate `score` exactly as:

`0.25*factual_accuracy + 0.20*text_legibility + 0.15*structural_completeness + 0.10*layout_balance + 0.10*connector_clarity + 0.10*visual_hierarchy + 0.05*style_consistency + 0.05*watermark_absence`

Round `score` to two decimal places. Return `PASS` only when there is no red line and `score >= 0.90`.

## Corrections

List every violation separately. Each `revised_description` must:

- use English;
- start with an imperative verb;
- name the exact element and location;
- quote exact replacement text;
- describe the desired final state;
- keep the existing canvas size.

## Output

Return strict JSON only:

{
  "reasoning": "concise evidence-based summary",
  "result": "FAIL",
  "score": 0.0,
  "dimension_scores": {
    "factual_accuracy": 0.0,
    "text_legibility": 0.0,
    "structural_completeness": 0.0,
    "layout_balance": 0.0,
    "connector_clarity": 0.0,
    "visual_hierarchy": 0.0,
    "style_consistency": 0.0,
    "watermark_absence": 0.0
  },
  "red_lines": ["required text mismatch"],
  "text_audit": {
    "expected_count": 0,
    "observed_count": 0,
    "exact_match_count": 0,
    "issues": [
      {
        "type": "wrong_character",
        "ledger_id": "section.item.field",
        "expected_text": "exact required text",
        "observed_text": "rendered text",
        "position": {"x_percent": 0, "y_percent": 0}
      }
    ]
  },
  "violations": [
    {
      "rule_name": "factual accuracy",
      "detail": "offending element and evidence",
      "revised_description": "Replace ..."
    }
  ]
}

When `result` is `PASS`, both `red_lines` and `violations` must be empty.
