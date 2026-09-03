# Infographic Candidate Review

Evaluate one generated infographic against its expected content and design instructions.

## Inputs

1. Candidate image.
2. Fact ledger containing every required number, date, proper noun, quotation, and claim.
3. Required text labels.
4. Final generation prompt, including the selected layout and style.

The fact ledger is the authority for content. Do not treat plausible-looking text or unlabeled visual estimates as correct.

## Red lines

Return `FAIL` regardless of score when any red line is present:

- a required fact or label is missing, changed, contradicted, or replaced with pseudo-text;
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
  "result": "PASS",
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
  "red_lines": [],
  "violations": [
    {
      "rule_name": "factual accuracy",
      "detail": "offending element and evidence",
      "revised_description": "Replace ..."
    }
  ]
}

When `result` is `PASS`, both `red_lines` and `violations` must be empty.
