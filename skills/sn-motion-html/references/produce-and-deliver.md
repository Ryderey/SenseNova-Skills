# Stage reference: complete the stills, assemble, verify, deliver

Read this file when B has been accepted or explicitly delegated, or when a clear local revision authorizes specific follow-on work. This turn's end is the delivered project, or the authorized local-revision result.

## Complete the still set and show the overview

Complete only the missing stills after A and B are accepted or explicitly delegated. Keep accepted samples, prefer editing from accepted references for recurring subjects, and keep key subjects inside the safe central crop. Put copy in HTML, not in pixels. Generate with SenseNova at `--image-size 4k --model sensenova-u1.5-lite --no-fallback --image-format png`; preserve PNG masters under `assets/images/scenes/`. Run `scripts/make_posters.py` only when PNG masters exist and their WebP page copies need to be created or refreshed. If the project already uses WebP assets without PNG masters, skip compression. When compression is needed, reuse the recorded `--max-width` (for example, `4096`) instead of silently applying the default and overwriting an established page width. Record master dimensions, delivered web dimensions, parameters, references, accepted variants, and visual checks in `docs/image-qa.md`.

Before a batch, report the number of new stills and correction rounds. Keep assembled prompts, analysis drafts, rejected candidates, and temporary frames in a per-task system-temporary directory. Once a candidate is adopted, retain its full prompt and generation basis in the production record; clean rejected experiments after replacement is verified.

When the stage executor is present (`scripts/motion_stage.py`, see [workflow.md](workflow.md)), route the remaining image calls through it: `run-remaining` validates B and the actual missing or authorized-revision assets before calling the runner, and records each attempt's start, end, and result. Generation targets the lossless master, so a chapter whose declared page asset is WebP is reported as needing a local `make_posters.py` run, never as needing another image call. An interrupted or result-unknown attempt is reconciled against the real files before anything is resubmitted, because a timed-out request may already have been billed.

When every still exists, generate and display the labeled full contact sheet. It is a required overview artifact, but it is not a third forced confirmation by default. If the user explicitly asks to inspect all images before assembly, mark the workflow as waiting for that request and do not continue until it is answered.

## Assemble, verify, and deliver

Use `content/story.json` as the only story source of truth and stack one ordered scene per chapter inside one fixed stage. Select a UI treatment from [frontend.md](frontend.md) or customize it while preserving the continuous media stage. Compress without overwriting masters.

Run the project checks from the initialized project:

```bash
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

Run `make_posters.py` separately only when PNG masters need WebP creation or refresh, and pass the width already recorded for the project, such as `--max-width 4096`. Skip it for WebP-only projects or when the current WebP copies are already valid; media validation does not require PNG masters.

Export whenever the user wants the whole story reviewed at once, or wants an artifact to annotate or print:

```bash
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/export_storyboard.py" "<absolute PROJECT_ROOT>"
```

The export requires every declared still to exist. Re-export after every content change; never hand-edit it. A draft marked "待配图" is a review artifact, not an `exports/` deliverable.

Before delivery, validate JSON, JavaScript, shell, and Python syntax; inspect the labeled overview; and use a fresh browser session at desktop, tablet, and phone widths with forward/reverse progress, navigation, missing-media fallback, reduced motion, and no copy overflow. Hand off the project path, preview URL, media locations, actual media mode, visible stage artifacts, deliverables, checks, and the current production state.

## Optional display poster

Only when the user asks for a poster as a separate deliverable. It is a designed image with its own title, key information, and dimensions — not a resized still. `scripts/make_posters.py` produces compressed web images and is never the poster path.

Build the brief from confirmed story content only, then hand it to the infographic workflow (`sn-infographic`), which keeps its own confirmation gate, quality review, and text-correction rounds. The brief contains:

1. the story's title and, when useful, its subtitle or kicker;
2. the main visual: the accepted still that carries the story, passed as a reference image when the poster must reproduce that subject, or described from the style preamble when it only has to stay in the same visual world;
3. two to four key facts or phrases from the chapter copy — short labels, not the paragraphs;
4. the target ratio and size, stated explicitly, and the language.

Keep the exact long Chinese copy in the page and the storyboard, where it stays editable and pixel-exact. State the poster's real dimensions and file path in the delivery, and confirm the Chinese text and facts against the brief before handing it over.

## Video clips (Agnes video)

Only when the user asks for clips. An image story and its storyboard are complete without this stage, and a project must never be described as having generated motion unless the clips exist.

The request contracts and the measured provider behaviour are in [agnes-video.md](agnes-video.md). Read it before shaping prompts. Two choices matter: pick the model — `agnes-video-v2.0` for high-definition clips, `agnes-video-2.5-flash` when reference images or a last-frame-only anchor are needed — and respect the constraint that shapes everything: **every media input must be a public HTTPS URL**, which a project's own stills are not.

1. Initialize the video project with `--media video`, or add video scaffolding to an existing project only when the user wants that project to carry clips.
2. Resolve an image anchor for every clip: use a SenseNova-generated URL or a supplied public HTTPS image URL. Respect already-stated choices. Image generation, editing, repair, enhancement, and compositing stay with SenseNova; Agnes only generates video. Missing or unusable anchors block the clip, with no text-only fallback. Never publish a user's images without asking.
3. Author `prompts/video-manifest.json` and one prompt file per clip. The manifest carries the provider parameters and, per clip, its `anchor_mode` and prompt paths; the script executes what those say rather than authoring content.
4. Draft each clip prompt from the chapter's own direction: `shot.motionNote` is the intended movement, `shot.framing` is what must stay consistent. Follow the shared Agnes prompt order — subject and scene, action and change, camera, visual style, then consistency.
5. Run the pipeline. It resolves the anchors, calls Agnes, and normalizes every clip locally:

   ```bash
   "<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/agnes_video.py" "<absolute PROJECT_ROOT>" \
     --image-cli "<absolute BASE_SKILL_DIR>/scripts/sn_agent_runner.py" \
     --agnes-cli "<absolute AGNES_SKILL_DIR>/scripts/agnes_media.py" \
     --write-stills --dry-run
   ```

   Check this dry run before removing `--dry-run` to execute. Use `--only <id>` to select clips and `--seed` when supported. In PowerShell prefix the quoted Python executable with `&`. The live pipeline loads provider settings from the project's `.env` without overriding process variables; `python-dotenv` comes from the image runtime requirements. Explicit CLI paths take precedence over `SN_IMAGE_BASE_DIR` and `AGNES_SKILL_DIR`. The repository copy can also discover its sibling image runner; exported projects should pass the paths shown above.
6. With `--write-stills`, each clip's first frame becomes the page still at the video's delivery resolution (normally 1920×1080). This is a video-derived still, not a SenseNova 4K master. Keep any existing high-resolution originals separately; `--force` permits replacing the WebP page still.
7. Run `scripts/verify_media.py`: it requires every clip to be h264 at the manifest's exact dimensions, frame rate, and duration. Provider output is neither the right size nor the right length, so the script's FFmpeg normalization is what makes that check pass — never hand a provider file straight into `assets/`.
8. Connectors join adjacent chapters. Their natural anchors are the neighbours' boundary frames, which are local extracts with no URL, so a connector runs in `reference` mode instead: it borrows the two chapters' recorded anchor images, starts in one chapter's visual world and lands in the other's, with no hosting. Give it an explicit `reference_images` list when you want different references, `url` mode to pin a hosted frame exactly, or `null` in `connectors` to declare the seam an accepted visible cut.
