# Production workflow

The default deliverable is an image story. Export its storyboard when requested, and produce a display poster only when requested. The image route needs no video tooling, video credentials, or public image host; section 10 adds the optional video route.

## 0. Establish the task and mode

Read the user's requirements, existing project files, supplied images, and any production records before making a plan. Record the following in `docs/production-spec.md` when a project is being created or materially revised:

- purpose, audience, language, device targets, and chapter scale;
- factual, adapted, or fictional treatment, with source notes kept separate from display copy;
- chronological, thematic, geographic, or process-based structure;
- visual medium, palette, lighting, camera grammar, prohibited elements, and recurring identities;
- available images, required new stills, generation model, budget authority, and attempt limits;
- interaction mode: `collaborative` by default, or `direct-completion` when the user explicitly delegates the remaining creative decisions or says not to wait.

Preserve the continuous-stage skeleton: one fixed media stage and one ordered route. Use the user's already-stated decisions as decisions, not questions. When resuming, trust actual files and records only after checking that the referenced files still exist.

## 1. Draft the story and confirmation A

For factual work, use primary or authoritative sources. For adapted or fictional work, state the major adaptation choices, especially the ending when multiple versions exist. Build a chapter sequence with one dominant visual event per chapter and stable, filename-safe IDs. Each chapter needs the actual display copy, a navigation label, title, optional subtitle, tags, expected still path, and, when useful, a `shot` block (`intent`, `framing`, `motionNote`). See [schemas.md](schemas.md).

Write the intended copy to `content/story.json` as early as possible. During drafting, a still may point to an expected path that does not exist yet; use `verify_media.py --allow-missing` only for offline assembly checks. Do not create placeholder images, run the formal storyboard export, or generate new stills to make an incomplete draft look finished.

In collaborative mode, show:

1. a short proposal covering audience, adaptation, ending, chapter count, visual direction, and recurring identities;
2. every chapter's actual text and dominant visual event, with current display number and stable ID available for internal mapping;
3. the still plan, expected image count, and the next representative scenes to be generated.

Ask one focused question: accept this draft and direction, or name the chapter and change. This is confirmation A. A progress message, a file write, silence, timeout, or a question about status is not confirmation. If the user edits the draft, revise only the affected proposal and show it again without generating new images.

Explicit final copy or a direct-completion instruction can cover A. A complete supplied image set covers only the image-production stages; if the user has not also supplied final copy/order or explicitly delegated the remaining creative decisions, still wait for A. Do not ask the user to re-confirm a decision already made; record whether it was accepted, explicitly delegated, or merely proposed.

## 2. Generate representative stills and confirmation B

Check that the image-generation capability is available before submitting. Use supplied images directly when they meet the requirement. A complete usable image set plus explicit final copy can cover the image stages with zero new image-model calls. Otherwise generate only the smallest useful consistency gate: usually one image for a simple story, or two or three when characters, settings, or emotional range create separate risks. Choose scenes that test identity, composition, and the most important visual decision; do not mechanically pad the set to opening/middle/ending.

Display the actual image files, their chapter numbers, and a few concrete checks. The accepted representative stills become the final assets; never generate a preview set and then regenerate the same scenes unconditionally. In collaborative mode, ask one focused question: keep this visual direction and continue, or name the visual change. This is confirmation B. A request such as “change the coat, then continue” authorizes that explicit change and continuation; a new open-ended visual choice requires another focused confirmation for the affected scope.

Direct-completion mode still shows the draft summary and representative images, but continues after the Agent's checks without manufacturing a wait. When existing images or an already accepted visual baseline are sufficient, skip new sample generation and record why.

Record the authorized model budget and attempt limit before generation. A free-only request requires evidence that the selected account and operation are free or covered by a free quota. If that cannot be verified, complete offline preparation and report the blocker before submitting. A successful response or dry run does not prove zero cost.

## 3. Complete the still set and show the overview

Complete only the missing stills after A and B are accepted or explicitly delegated. Keep accepted samples, prefer editing from accepted references for recurring subjects, and keep key subjects inside the safe central crop. Put copy in HTML, not in pixels. Generate with SenseNova at `--image-size 4k --model sensenova-u1.5-lite --no-fallback --image-format png`; preserve PNG masters under `assets/images/scenes/`. Run `scripts/make_posters.py` only when PNG masters exist and their WebP page copies need to be created or refreshed. If the project already uses WebP assets without PNG masters, skip compression. When compression is needed, reuse the recorded `--max-width` (for example, `4096`) instead of silently applying the default and overwriting an established page width. Record master dimensions, delivered web dimensions, parameters, references, accepted variants, and visual checks in `docs/image-qa.md`.

Before a batch, report the number of new stills and correction rounds. Keep assembled prompts, analysis drafts, rejected candidates, and temporary frames in a per-task system-temporary directory. Once a candidate is adopted, retain its full prompt and generation basis in the production record; clean rejected experiments after replacement is verified.

When every still exists, generate and display the labeled full contact sheet. It is a required overview artifact, but it is not a third forced confirmation by default. If the user explicitly asks to inspect all images before assembly, mark the workflow as waiting for that request and do not continue until it is answered.

## 4. Assemble, verify, and deliver

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

## 5. Production records and review artifacts

`docs/production-spec.md` is a compact human/Agent record, not a second story database. Keep a current state block with:

- interaction mode and its evidence;
- current stage (`story-draft`, `representative-stills`, `complete-stills`, `assembly`, `delivered`, or `local-revision`);
- revision number, waiting point, next action, chapter IDs involved;
- new-still plan: total, adopted, remaining, and extra identity images;
- generation limits and the location of the authorization record.

Also record the current display-number-to-stable-ID mapping and distinguish `user accepted`, `user delegated`, `Agent checked`, and `unreviewed`. `docs/image-qa.md` records accepted image sources, model/parameters, reference paths, and checks without inventing provider fields. An optional `docs/review/story-draft.md` is a read-only review copy derived from `story.json`; edit `story.json` first. Do not put workflow state in the frontend runtime.

## 6. Resume and local revision

When resuming, read the state block, the relevant story chapters, image QA, and actual files before continuing. A generated but not-yet-shown representative still is shown first rather than regenerated. A missing file invalidates the stale record and is reported; it does not silently trigger a full restart. An old project without a state block gets the minimum record needed for the current task, never a fabricated acceptance.

For a local revision, map the user's current display number or title to the stable chapter ID. State the affected scope in one sentence, retain unrelated accepted assets, update the source artifact first, then regenerate only required derivatives: WebP, contact sheet, and storyboard when applicable. A clear request to fix copy or replace one image is authorization for that scope and does not restart the two confirmation points. Reconfirm only when the change introduces a new creative choice, such as an open-ended scene change or a global visual direction.

## 7. Change matrix

| User change | Update | Usually retain | Confirmation |
|---|---|---|---|
| Typo, shorter copy, same event | Chapter copy, exports, browser check | Images, identities, style, other chapters | Direct when explicitly requested |
| Chapter event or key object | Copy, shot, image and affected follow-on scenes | Unrelated chapters | Confirm only the new choice |
| One image's expression, composition, or detail | That image, its basis, WebP, overview, relevant export | Other accepted images and copy | Direct when clear |
| Recurring character appearance | Identity record and every affected image | Images without that identity | Show affected chapter IDs and follow scope |
| Global visual style | Style basis, representative samples, affected stills | Accepted copy and chapter structure | New visual confirmation |
| Reorder/add/remove chapters | Order, number mapping, affected transitions, assets, exports | Stable IDs that still apply | Show changed structure/copy |
| Layout or responsive issue | Layout, copy position/crop, browser check | Story meaning and usable images | Direct when clear; replace images only if necessary |

Do not claim that a local change touches one file when real dependencies extend further. Conversely, do not regenerate unrelated scenes merely to make them look consistent. `make_posters.py` may recompress the whole PNG directory deterministically; that is not a reason for new image-model calls.

## 8. Cost and waiting discipline

Two confirmations add a little text and waiting cost but expose story and visual errors before the most expensive work. Do not promise a fixed token or image-cost saving. If usage is available, record text input/output, image calls, local processing time, user replies, and total wait separately. Word count is not token usage, and image cost is not text cost.

Keep the first review complete, show only changed chapters for local revisions, reuse accepted references, and do not generate unrequested character boards, posters, videos, or alternate full style sets. Host rules may require a different wait behavior; preserve visible stage artifacts and report the deviation honestly.

## 8.1 Optional display poster

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

## 10. Video clips (Agnes video)

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
