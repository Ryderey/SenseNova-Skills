# Production workflow

The default deliverable is an image story: supplied or generated stills arranged into one scroll-driven page. Clip generation is a separate branch that follows the image story rather than replacing it.

## 1. Frame the experience

Record these decisions in `docs/production-spec.md`:

- purpose and audience;
- factual, adapted, or fictional treatment;
- chronological, thematic, geographic, or process-based structure;
- chapter count and approximate reading density;
- visual medium, palette, lighting, camera grammar, and prohibited elements;
- recurring characters/products and required identity fidelity;
- desktop/mobile targets, interface treatment, copy positions, and language;
- available images, required new stills, and any explicit user decisions;
- generation model, budget authority, and attempt limits when new stills are needed.

Preserve the continuous-stage skeleton: one fixed media stage and one ordered route. Decide how header, navigation, typography, and copy placement express the subject without covering scene focal points. Treat these as proposals until the review package in section 4 is accepted.

## 2. Research and outline

For factual work, use primary or authoritative sources. Separate research notes from the concise display copy. Build:

1. a source-backed event or concept list;
2. a chapter sequence with one dominant visual event per chapter;
3. a source appendix rather than inline citations unless requested.

Each chapter needs a stable ID, a short navigation label, eyebrow, title, optional subtitle, two or three compact paragraphs, tags, and its still.

## 3. Establish visual continuity

Create a single style preamble with medium, palette, materials, camera, light, composition, and negative constraints. For every recurring identity, create an immutable block describing face or form, silhouette, colors, clothing or packaging, the signature object, and the allowed changes.

## 4. Present the review package

Present the visual direction and the chapter arrangement together, and record the user's decisions. When the user already specified these, present the package as a confirmation rather than a fresh question. If the user requests changes, revise the affected proposal and present it again.

The package contains:

1. the style preamble and identity blocks;
2. the chapter sequence: display copy, dominant visual event, and copy position per chapter;
3. when new stills are needed, a small consistency gate (normally opening, middle, and ending) for the user to inspect.

Nothing here authorizes generation. See section 7 for the separate authorization that any metered or paid request requires.

## 5. Build the image set

Use supplied images directly when they meet the requirement. When new stills are needed:

1. Confirm an image-generation capability is available in the current environment; it may be a callable tool, an installed skill that provides the image workflow, or both. In this repository that capability is `sn-image-base`.
2. Complete the still set only after the direction is accepted, treating the accepted gate images as the consistency baseline.
3. Prefer editing from the reference images for recurring subjects. Keep key subjects inside the safe central crop, and keep text, logos, and watermarks out unless explicitly required.
4. Put the copy in HTML, not in the pixels: body text, buttons, and source labels belong to the page, so they stay editable and translatable.
5. Save lossless masters under `assets/images/scenes/`, then run `scripts/make_posters.py` to write the web posters. Record accepted variants and the reason for selection in `docs/image-qa.md`.

Report the number of new stills and the correction rounds before starting a batch. Keep intermediates — assembled prompts, analysis drafts, rejected candidates — in a per-task directory under the system temporary directory, and clean them up after delivery.

## 6. Assemble the site

Use `content/story.json` as the source of truth and interleave scene and connector records into one route inside one fixed stage. Select a UI treatment from `references/frontend.md` or customize it: header geometry, copy material, type hierarchy, navigation, and per-scene copy position may all change, while the single continuous media stage stays.

Run the project checks from the initialized project:

```bash
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

## 7. Optional video clips

Only when the user explicitly asks for generated clips. Image work is complete and deliverable without this stage; an image story must not be described as a generated continuous-camera result.

Before the first metered or paid request, present the provider, model, planned clip count, retry allowance, and cost basis, and obtain authorization for that batch. Without credentials, still validate the manifest offline and deliver the image story. See `references/seedance.md` for the Ark request contract; verify current model documentation before use.

Use two dependency phases:

1. generate all scene clips concurrently;
2. extract their actual first and last frames;
3. generate connector clips concurrently from adjacent boundary frames.

Download provider results immediately, and normalize locally rather than assuming provider duration or codecs are exact. Resume by skipping outputs that pass media validation, not by checking that a file is non-empty.

## 8. Verify and hand off

Validate every declared file and exercise a fresh browser session. Include a reduced-motion test, and in video mode a real lazy-load test. Generate and inspect a labeled contact sheet. If a live tab existed before the media changed, hard-refresh it because a failed lazy-load may remain cached in that runtime instance.

Hand off the preview URL, the exact project path, the generation commands used, the media locations, the actual media mode, and any credentials or provider settings the user still owns.
