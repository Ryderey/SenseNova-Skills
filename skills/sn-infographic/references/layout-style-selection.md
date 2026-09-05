# Layout & Style Selection Rules

Resolved by the host Agent's own reasoning — no external LLM call is required.

**Operate on names only until selection is complete.** This procedure ranks layout/style names (for example `hub-spoke`, `corporate-memphis`) from content, audience and canvas relevance. Read only the two selected definition files when assembling the final prompt. All 87 layouts and 66 styles remain available for explicit user selection.

An explicit `layout` or `style` requested by the user wins when its matching definition file exists. If it does not exist, report the invalid name and continue with recommendations. After selection, apply the high-risk CJK density gate from `prompt-writing-rules.md` to the resolved internal reading flow; style choices are unaffected.

## Step 1 — Layout Candidates (by data_type)

Analyze the information structure of `user_prompt`, determine the `data_type`, and map to layout candidates.
Each data_type has a primary (match_score=1.0) and alternatives (match_score=0.7).

| data_type | Primary Layout | Alternative Layouts |
|-----------|----------------|---------------------|
| timeline / history | `linear-progression` | `winding-roadmap`, `step-staircase`, `one-way-flow`, `flashback` |
| process / tutorial | `linear-progression` | `winding-roadmap`, `step-staircase`, `swimlane`, `modular-repetition`, `funnel`, `one-way-flow` |
| comparison | `binary-comparison` | `four-quadrant-grid`, `conflict-contrast` |
| hierarchy | `hierarchical-layers` | `axial-expansion`, `deconstruction` |
| relationships | `hub-spoke` | `jigsaw`, `multi-focal`, `venn-diagram` |
| data / metrics | `dashboard` | `periodic-table`, `data-landscape`, `hard-alignment`, `swiss-grid` |
| cycle / loop | `circular-flow` | `s-curve`, `wave-path`, `spiral-vortex` |
| system / structure | `structural-breakdown` | `multi-scale`, `containerization`, `deconstruction` |
| journey / narrative | `winding-roadmap` | `story-mountain`, `comic-strip`, `emotional-gradient`, `storyboard`, `flashback`, `full-illustration`, `one-way-flow`, `left-image-right-text`, `diagonal-composition`, `overlapping` |
| overview / summary | `bento-grid` | `periodic-table`, `containerization`, `top-image-bottom-text`, `panorama`, `golden-ratio-split` |
| problem / solution | `iceberg` | `conflict-contrast`, `visual-tension`, `funnel`, `bridge` |
| categories / collection | `periodic-table` | `bento-grid`, `tile-layout`, `gallery-style`, `skewed-grid` |
| spatial / geographic | `multi-scale` | `strong-perspective`, `panorama`, `isometric-map` |
| cross-functional / workflow | `swimlane` | `linear-progression`, `modular-repetition` |
| feature list / catalog | `modular-repetition` | `bento-grid`, `containerization`, `left-text-right-image` |
| single concept spotlight | `single-focal-point` | `big-typography`, `ultra-minimalist`, `header-body`, `center-focus`, `frame-composition`, `full-bleed-image`, `visual-first`, `single-object-art`, `macro-closeup`, `golden-ratio-split`, `deconstruction`, `heading-subheading`, `top-image-bottom-text`, `generous-margins`, `asymmetry`, `edge-tension`, `breaking-the-grid`, `strong-perspective` |
| dialogue / Q&A | `speech-bubbles` | `character-guide`, `comic-strip` |
| discovery / exploration | `nonlinear-path` | `scene-unfolding`, `random-scatter`, `disrupted-flow`, `collage-glitch`, `hidden-details` |
| network / multi-center | `multi-focal` | `hub-spoke`, `multi-directional` |
| report / long-form | `header-body` | `swiss-grid`, `hard-alignment`, `heading-subheading`, `editorial-vogue`, `chapter-layout` |
| marketing / CTA | `z-pattern` | `tile-layout`, `luxury-layout`, `editorial-vogue`, `generous-margins`, `full-bleed-image`, `visual-first`, `center-focus`, `frame-composition`, `overlapping`, `asymmetry`, `edge-tension`, `breaking-the-grid`, `skewed-grid`, `diagonal-composition`, `visual-tension`, `collage-glitch` |

## Step 2 — Style Candidates (by tone / domain, independent of layout)

Analyze the tone and domain of `user_prompt`, and map to style candidates.
Each context has a primary (match_score=1.0) and alternatives (match_score=0.7).

| Context | Primary Style | Alternative Styles |
|---------|---------------|-------------------|
| Technical / Engineering | `technical-schematic` | `ikea-manual`, `ui-wireframe`, `technical-diagram`, `parametric-design`, `subway-map` |
| Software / Product / Tech brand | `tech-brand` | `material-design`, `corporate-memphis`, `ui-wireframe`, `parametric-design` |
| Sci-fi / Futuristic | `neon-futurism` | `cyberpunk`, `sci-fi-ui`, `synthwave`, `holographic`, `liquid-metal`, `vaporwave` |
| Professional / Business | `corporate-memphis` | `swiss-style`, `minimalism`, `flat-design`, `bauhaus`, `high-contrast-ad` |
| Data / Analytics | `data-visualization` | `technical-diagram`, `swiss-style`, `minimalism`, `subway-map`, `parametric-design` |
| Educational / Instructional | `chalkboard` | `instructional-visual`, `ikea-manual`, `paper-collage`, `bauhaus` |
| Playful / Casual / Kids | `paper-collage` | `crayon-hand-drawn`, `cartoon-flat`, `kawaii`, `lego-brick`, `screen-print` |
| Luxury / Premium / Fashion | `luxury-minimal` | `art-deco`, `fashion-editorial`, `art-nouveau`, `liquid-metal` |
| Chinese domain | `chinese-guochao` | `modern-ink-wash` |
| Japanese domain | `ukiyo-e` | `kawaii` |
| Vintage / Retro | `aged-academia` | `vintage-poster`, `newspaper-collage`, `woodcut`, `art-nouveau`, `screen-print`, `vaporwave` |
| Artistic / Fine art | `impressionism` | `expressionism`, `cubism`, `baroque`, `surrealism`, `art-nouveau` |
| Handmade / Craft | `paper-collage` | `crayon-hand-drawn`, `storybook-watercolor`, `claymation`, `origami`, `screen-print` |
| Illustration / Drawing | `pen-sketch` | `line-drawing`, `marker-style`, `thick-paint`, `monochrome-illustration` |
| Experimental / Avant-garde | `deconstructivism` | `glitch-art`, `op-art`, `geometric-burst`, `fractal-art`, `surreal-collage`, `parametric-design`, `vaporwave` |
| Scandinavian / Minimal | `scandinavian` | `minimalism`, `swiss-style`, `luxury-minimal`, `bauhaus` |
| Playful / Geometric | `origami` | `pixel-art`, `knolling`, `lego-brick`, `bauhaus` |
| Photography / Mixed | `mixed-media` | `film-photography`, `double-exposure`, `newspaper-collage` |
| Marketing / Advertising | `high-contrast-ad` | `screen-print`, `flat-design`, `corporate-memphis` |
| Futuristic / Luxury Tech | `liquid-metal` | `neon-futurism`, `holographic`, `parametric-design` |
| Internet / Youth Culture | `vaporwave` | `glitch-art`, `cyberpunk`, `pixel-art` |

## Step 3 — Deterministic relevance ranking and shortlist

Rank layout and style independently. Do not use randomness, and do not let the table's primary label outweigh stronger request evidence.

1. Score layouts:
   - matched primary: 70 points; each listed alternative: 60 points;
   - explicit structural cue in the request: +25;
   - strong audience match: +20;
   - canvas fit: +15;
   - content-density fit: +15.
2. Score styles separately:
   - every style in the matched context row: 60 points; row primary: +5 as a weak default only;
   - explicit aesthetic, cultural, material, or medium cue in the request: +30;
   - audience and publishing-context fit: +20;
   - legibility fit for the actual text density: +15;
   - illustration, photography, or rendering-medium fit: +10.
3. Use these audience signals where relevant:
   - executives/decision makers: `dashboard`, `comparison-matrix`, `swiss-grid`; `swiss-style`, `data-visualization`, `minimalism`
   - general/public: `bento-grid`, `storyboard`, `visual-first`; `flat-design`, `instructional-visual`, `paper-collage`
   - technical experts: `structural-breakdown`, `swimlane`, `isometric-tech-stack`; `technical-schematic`, `technical-diagram`, `sci-fi-ui`
   - children/education: `comic-strip`, `character-guide`, `step-staircase`; `cartoon-flat`, `kawaii`, `crayon-hand-drawn`
4. Use these layout signals where relevant:
   - portrait/tall: vertical timelines, `winding-roadmap`, `chapter-layout`, `top-image-bottom-text`
   - landscape/wide: `swimlane`, `binary-comparison`, `dashboard`, `data-landscape`, `panorama`
   - square: `hub-spoke`, `circular-flow`, `bento-grid`, `nine-grid`, `center-focus`
   - sparse content: focal and minimal layouts; dense content: grid, dashboard, chapter, or container layouts.
5. For dense text, award style legibility points to restrained candidates such as `swiss-style`, `minimalism`, `data-visualization`, and `instructional-visual`; do not award them to a decorative style merely because it is the row primary.
6. Reject any candidate whose definition file does not exist. Rank by score; break ties by stronger explicit-request evidence, then table order, then lexical name.
7. Build three viable combinations in this order:
   - **Recommended:** the highest-scoring compatible layout×style pair.
   - **Clarity-first:** the best alternative for reading order, text density, and information retrieval.
   - **Expressive:** the strongest visually distinct alternative that still fits the content and audience.

Every combination must be unique. When at least three compatible styles exist, use a different style file for each; vary the layout as well when doing so does not weaken an explicit structure requirement. Keep an explicitly requested layout or style fixed while varying the unresolved dimension. Give each option a short direction name in the user's language, the raw layout/style IDs, one sentence of rationale, and one concrete tradeoff.

## Step 4 — User-visible confirmation gate

- When both layout and style were explicitly supplied and valid, treat them as confirmed and record `selection.status=resolved` and `selection_source=user_explicit`.
- In `selection_mode=auto`, select Recommended, show its names and rationale before rendering, and record `selection.status=resolved` and `selection_source=auto`.
- Otherwise show the three numbered combinations with Recommended marked, including rationale and tradeoff. Ask the user to reply with `1`, `2`, `3`, or another valid layout/style, then stop. Do not assemble the final prompt or call image generation/editing until the user answers.
- After the user chooses, record `selection.status=resolved`, `selection_source=user_confirmed`, the resolved `layout`, `style`, `selection_reason`, and all three alternatives. Reuse that direction for every refinement round unless the user explicitly asks for new recommendations.

Use this compact presentation:

```text
1. [Recommended] Human-readable direction (layout × style) — rationale. Tradeoff: ...
2. [Clarity-first] Human-readable direction (layout × style) — rationale. Tradeoff: ...
3. [Expressive] Human-readable direction (layout × style) — rationale. Tradeoff: ...
Choose 1/2/3, or name another layout/style.
```

## Fallback

If `data_type` or context cannot be determined, do not silently collapse to one fixed pair. In confirmation mode, explain the ambiguity and offer three options fitted to the known audience, density, and canvas. In auto mode, score `bento-grid`, `header-body`, and `single-focal-point` against those signals; score `minimalism`, `flat-design`, and `corporate-memphis` against audience and density, then select the deterministic winner.
