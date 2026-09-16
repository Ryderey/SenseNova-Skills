# Production workflow

The deliverable is an image story, its storyboard, and — only when asked — a display poster. No stage needs video tooling, video credentials, or a public image host.

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

Each chapter needs a stable ID, a short navigation label, eyebrow, title, optional subtitle, two or three compact paragraphs, tags, and its still. When the plan is worth stating per chapter, add the optional `shot` block (`intent`, `framing`, `motionNote`); see [schemas.md](schemas.md). It is optional, and a story without it exports a complete storyboard.

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
5. Save lossless masters under `assets/images/scenes/`, then run `scripts/make_posters.py` to write the compressed web images. Record accepted variants and the reason for selection in `docs/image-qa.md`.

Report the number of new stills and the correction rounds before starting a batch. Keep intermediates — assembled prompts, analysis drafts, rejected candidates — in a per-task directory under the system temporary directory, and clean them up after delivery.

## 6. Assemble the site

Use `content/story.json` as the source of truth and stack one ordered scene per chapter inside one fixed stage. Select a UI treatment from [frontend.md](frontend.md) or customize it: header geometry, copy material, type hierarchy, navigation, and per-scene copy position may all change, while the single continuous media stage stays.

Run the project checks from the initialized project:

```bash
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

## 7. Export the storyboard

Export whenever the user wants the whole story reviewed at once, or wants an artifact they can annotate, print, or hand to someone who is not going to scroll a page:

```bash
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/export_storyboard.py" "<absolute PROJECT_ROOT>"
```

This writes `exports/storyboard.md` and `exports/storyboard.html` from the same story data the page reads. Both list every shot in chapter order with its still, copy, tags, and declared shot direction, so the two can never drift apart.

- Re-export after every content change; never hand-edit an export, and tell the user that `content/story.json` is the editing entry point.
- The export requires every declared still to exist, so run it after the image set is complete rather than around missing files. A draft marked "待配图" is an internal review step, not an `exports/` deliverable.
- The static HTML is itself a readable page: a user who only wants a storyboard never has to build or scroll the story page. Only that HTML is served by the preview; the Markdown stays in the project.

## 8. Optional display poster

Only when the user asks for a poster as a separate deliverable. It is a designed image with its own title, key information, and dimensions — not a resized still. `scripts/make_posters.py` produces compressed web images and is never the poster path.

Build the brief from confirmed story content only, then hand it to the infographic workflow (`sn-infographic`), which keeps its own confirmation gate, quality review, and text-correction rounds. The brief contains:

1. the story's title and, when useful, its subtitle or kicker;
2. the main visual: the accepted still that carries the story, passed as a reference image when the poster must reproduce that subject, or described from the style preamble when it only has to stay in the same visual world;
3. two to four key facts or phrases from the chapter copy — short labels, not the paragraphs;
4. the target ratio and size, stated explicitly, and the language.

Keep the exact long Chinese copy in the page and the storyboard, where it stays editable and pixel-exact. State the poster's real dimensions and file path in the delivery, and confirm the Chinese text and facts against the brief before handing it over.

## 9. Verify and hand off

Validate every declared file and exercise a fresh browser session at desktop, tablet, and phone widths. Include a reduced-motion test. Generate and inspect a labeled contact sheet, and check each still for baked-in watermarks, brand marks, and stray text. If a live tab existed before the media changed, hard-refresh it.

Hand off the preview URL, the exact project path, the media locations, the actual media mode, which deliverables exist (page, storyboard, poster), and any credentials or provider settings the user still owns.

## 10. Video clips (Agnes Video 2.5 Flash)

Only when the user asks for clips. An image story and its storyboard are complete without this stage, and a project must never be described as having generated motion unless the clips exist.

The request contract, the Flash constraints, and the measured provider behaviour are in [agnes-video.md](agnes-video.md). Read it before shaping prompts: Flash takes 720P only, whole-second durations from 4 to 12, and — the constraint that shapes everything — **every media input must be a public HTTPS URL**, which a project's own stills are not.

1. Initialize the video project with `--media video`, or add video scaffolding to an existing project only when the user wants that project to carry clips.
2. Settle the anchor question with the user first: publish their stills to a host they control, let the anchor image be generated through Agnes (whose own outputs are already public), or compose the clip from text alone. Never publish a user's images without asking.
3. Author `prompts/video-manifest.json` and one prompt file per clip. The manifest carries the provider parameters and, per clip, its `anchor_mode` and prompt paths; the script executes what those say rather than authoring content.
4. Draft each clip prompt from the chapter's own direction: `shot.motionNote` is the intended movement, `shot.framing` is what must stay consistent. Follow the shared Agnes prompt order — subject and scene, action and change, camera, visual style, then consistency.
5. Run the pipeline. It resolves the anchors, calls Agnes, and normalizes every clip locally:

   ```bash
   "<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/agnes_video.py" "<absolute PROJECT_ROOT>" --write-stills
   ```

   Add `--dry-run` first to see every call without spending anything, `--only <id>` to redo one clip, and `--seed` for a reproducible run.
6. With `--write-stills`, each clip's own first frame becomes the page still, so the page shows exactly what its clip starts with.
7. Run `scripts/verify_media.py`: it requires every clip to be h264 at the manifest's exact dimensions, frame rate, and duration. Provider output is neither the right size nor the right length, so the script's FFmpeg normalization is what makes that check pass — never hand a provider file straight into `assets/`.
8. Connectors join adjacent chapters. Their natural anchors are the neighbours' boundary frames, which are local extracts with no URL, so a connector runs in `reference` mode instead: it borrows the two chapters' recorded anchor images, starts in one chapter's visual world and lands in the other's, with no hosting. Give it an explicit `reference_images` list when you want different references, `url` mode to pin a hosted frame exactly, or `null` in `connectors` to declare the seam an accepted visible cut.
