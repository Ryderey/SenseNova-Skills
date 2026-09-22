---
name: sn-motion-html
description: Build a scroll-driven image-story web page from supplied images or a short narrative with SenseNova, and export the same story as a storyboard. Use for “SenseNova 技能” requests involving 图片故事网页、滚动叙事网页、图像时间线、沉浸式场景浏览、图片做成网页、分镜稿、storyboard, product scroll story, or turning an existing image set into one continuous page. Images need no video tooling; a composed display poster routes to the infographic workflow, and clip generation is a separate, later-phase path. Single-image infographics, posters, and long images use the infographic workflow instead; ordinary web apps and autoplay video pages are out of scope.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: image-visualization
  priority: 7
  user_visible: true
  workflow_protocol: 2
---

# sn-motion-html

## Execution contract

Collaborative mode by default. This execution completes only the currently authorized stage; ending the turn at a stage hand-off is task completion, not failure.

- **New story:** show the complete chapter-by-chapter copy and visual plan, record `awaiting_story_review`, ask for feedback in the final reply, and end the turn. Image generation and edit calls must be 0 at this point.
- **After a new user confirmation of the current draft:** generate only the specified representative stills, display them, record `awaiting_visual_review`, ask for feedback in the final reply, and end the turn. Do not generate other scenes, and do not start later stages as committed, queued, background, or delegated work.
- **After a new user confirmation of the current samples:** complete the remaining images, show the overview, and finish the page.
- An explicit direct-completion instruction cancels only the user waits, not the stage artifacts or the sample self-check. Reuse existing inputs and valid decisions within scope; do not re-ask settled questions.

A pause is an observable behavior, not a log note: the actual draft or images are visibly shown, one focused question with a simple reply path is asked, the turn ends (or the host's native wait truly pauses), nothing later is queued, and no tool call depends on the pending confirmation. A progress message, a file write, silence, a status question, an Agent self-check, a completed plan item, or a host auto-continue event is not a user confirmation. When the project carries `scripts/motion_stage.py`, story image calls go through it and it refuses out-of-scope calls before any provider request; that is a program check, not an unblockable host gate.

Show the user one line about the flow — 采用分阶段流程：文案 → 样图 → 网页 — and verify the protocol version at task start or deployment check, not in every reply. Hashes, state fields, and tool traces stay out of the chat; the user sees actual copy, actual images, and one question.

Deliver a reusable project, not a one-off HTML file. One fixed full-viewport media stage and one ordered chapter route carry the whole story: the reader scrolls, the page advances through the chapter sequence, and every chapter's copy stays readable together on its own scene.

The same story data also exports a storyboard, so the whole sequence can be reviewed, annotated, or printed without scrolling anything. Both come from `content/story.json`.

This phase delivers three things, in this order of priority:

| Deliverable | What the user gets | Built by |
|---|---|---|
| Image story page, default | A responsive, previewable story with real stills and complete copy | The project template in this skill |
| Storyboard | The same shots in reading order with stills, copy, and shot direction, as Markdown and as a static HTML document | `scripts/export_storyboard.py` |
| Display poster, on request | A composed image with its own theme, main visual, and a few key facts | The infographic workflow (`sn-infographic`), given a brief derived from the story |
| Video clips, on request | Scroll-scrubbed scene clips, and optionally transitions between chapters | `scripts/agnes_video.py`, with Agnes video (v2.0 by default) |

Generate only what was asked for. Do not add a poster or extra stills to a delivery that did not request them.

## Runtime paths

Resolve `MOTION_SKILL_DIR` as the absolute directory containing this `SKILL.md`. Resolve `PROJECT_ROOT` as the absolute output directory chosen for the story. Resolve `BASE_SKILL_DIR` as the absolute directory of the sibling `sn-image-base` skill, `RUNNER` as `BASE_SKILL_DIR/scripts/sn_agent_runner.py`, and `PYTHON` as the same interpreter that passes `sn-image-doctor`.

Use absolute paths regardless of the current working directory, and never assume the host inherited a previously activated shell environment. On PowerShell, invoke a quoted executable path with the call operator (`& "<absolute PYTHON path>" ...`); on POSIX shells, execute the quoted path directly. These are logical path names, not environment variables; never ask the user to configure them.

All image generation, editing, repair, enhancement, and compositing use the SenseNova backend. When the project carries the stage executor `scripts/motion_stage.py` (the initializer copies it), route story image calls through it: it checks the current phase and approval scope against `.motion-state/review.json` and only then calls `RUNNER` (`BASE_SKILL_DIR/scripts/sn_agent_runner.py`). An older project without the executor keeps the same runner contract directly, with the stage rules in the references as the check. Set `SN_IMAGE_GEN_MODEL_TYPE=sensenova` for these calls and explicitly select `sensenova-u1.5-lite`; use `--no-fallback` when resolution or anchor identity must be preserved. Agnes is used only for video generation. Local file copying, lossless saving, WebP compression, video encoding, and frame extraction remain deterministic project-tool operations. Credentials follow the `sn-image-base` contract: `SENSENOVA_API_KEY`, capability-specific overrides, and `SN_ENV_FILE`.

## What an image story needs

Only Python, Pillow, and a browser. No FFmpeg, no ffprobe, no video credentials, no image host, and no deployment step. Supplied images work as-is, so a complete delivery can cost zero model calls.

A story is readable without any generated motion: the stills, the copy, the navigation, and the cross-dissolves carry it. Do not promise real subject movement, object motion, or a generated continuous shot — those need clips that do not exist in this phase.

## Route the work

1. Collect the subject, audience, language, device targets, chapter scale, supplied images, reference images, factual requirements, and explicit user decisions. Already-stated requirements count as decisions; do not re-ask them. Use collaborative mode by default. Use direct-completion mode only when the user explicitly says to finish without waiting, to decide for them, or equivalent.
2. Inspect existing projects, images, production notes, and available image-generation capability before promising new stills. Resume from real files and recorded decisions; do not reinitialize an old project or replace missing assets silently.
3. For factual or source-based stories, research first and keep source notes separate from the display copy. Build the chapter blueprint and shot plan with stable chapter IDs, actual display copy, the dominant visual event, the still path, copy position, and optional `shot` direction.
4. In collaborative mode, write the complete draft copy to `content/story.json` with expected still paths, show every chapter's actual text and visual event, and end the turn at confirmation A (`awaiting_story_review`). Do not generate new stills before A, and do not queue later-stage work while waiting. A reply accepts only the material actually shown at that point.
5. After A, generate only the representative stills needed to check identity and visual direction (usually one for a simple story, two or three when risks differ), display the actual samples with chapter numbers and checks, and end the turn at confirmation B (`awaiting_visual_review`). If the user supplied a complete usable image set or an already accepted visual baseline, skip new image calls and record that decision. Reuse accepted samples as final assets; do not generate a separate preview set.
6. After B, or immediately in direct-completion mode, complete the remaining stills, show a labeled full contact sheet, and continue to assembly. The contact sheet is normally a visible stage artifact, not a third forced approval; wait after it only when the user explicitly asks to review all images first.
7. Assemble the project from `content/story.json`, compress without overwriting masters, export the storyboard only after every declared still exists, and verify media and browser behavior.
8. For a clear user request to change one chapter, one image, a recurring identity, the global style, chapter structure, or layout, map the current chapter number to its stable ID and update only the affected artifacts. Preserve unrelated accepted work and re-run only the required derived checks.
9. When the user asks for a poster, derive the brief from the accepted story and hand it to `sn-infographic`; never present a compressed still as a designed poster.
10. Deliver the project path, preview URL, visible stage artifacts, which deliverables exist, the check results, current production state, and any remaining blocker.

Read [references/workflow.md](references/workflow.md) for the stage router, the pause rules, the acceptance scope, and the recovery rules, then only the stage reference the current task needs:

- [references/review-story.md](references/review-story.md) for a new story or a major story revision: drafting and confirmation A.
- [references/review-visuals.md](references/review-visuals.md) after A is accepted: representative stills and confirmation B.
- [references/produce-and-deliver.md](references/produce-and-deliver.md) after B is accepted: the remaining stills, assembly, verification, delivery, the optional poster, and the optional video route.
- [references/schemas.md](references/schemas.md) when creating `content/story.json`, exporting a storyboard, or using the review state file.
- [references/prompting.md](references/prompting.md) when generating stills or recording shot direction.
- [references/style-presets.md](references/style-presets.md) when choosing or adapting a visual preset.
- [references/frontend.md](references/frontend.md) before selecting or adapting the interface treatment or the storyboard layout.
- [references/agnes-video.md](references/agnes-video.md) before producing video clips. [references/seedance.md](references/seedance.md) is historical only and is not an executable route for this workflow.

## Start from the template

```bash
"<absolute PYTHON path>" "<absolute MOTION_SKILL_DIR>/scripts/init_project.py" "<absolute PROJECT_ROOT>" \
  --title "Story title" \
  --style cinematic \
  --ui folio \
  --media images
```

Choose `--style anime`, `--style cinematic`, or `--style cgi`; choose `--ui folio`, `--ui caption`, or `--ui graphic` independently. Style governs the visual world and the generated stills; UI governs header, copy treatment, navigation, and typography. Never infer one from the other. Per-chapter `copyPosition` may be `left`, `right`, `bottom`, or `center`.

The initializer copies the template and the project scripts, creates the media directories, and creates no video credentials, manifest, or empty video directories. Replace the example chapters; never leave placeholder subject matter in the delivered project.

From the initialized project, the common commands are:

```bash
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/motion_stage.py" "<absolute PROJECT_ROOT>" status
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/export_storyboard.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

`motion_stage.py status` reports the current phase, the shown review packages, the allowed target scope, and the waiting item; it never calls the provider. Use it when resuming and before any image call.

## Production invariants

- Keep narrative data in `content/story.json`; never hardcode chapter copy into the runtime. The page and the storyboard are both generated from it, so it stays the single source of truth.
- Keep one complete, static, transparent copy block per chapter, visible together. Do not rotate paragraphs within a scene.
- Maintain a single style preamble and immutable identity blocks for recurring subjects.
- An **image** project must not request video, probe `ffprobe`, or load a clip. A video project loads only its own clips. Prove it from the network panel and the CLI checks, not from inspection alone.
- Use project-relative media paths. Reject absolute paths, drive-letter paths, and `..` escapes; after resolving symlinks the path must still be inside the allowed directory. Import user-supplied images as project assets first so the delivered page never depends on the user's machine layout.
- Copy articles have no solid card fill. Use edge-free localized gradients, text shadow, or fine rules for contrast.
- Keep stills and their compressed web images separate; compression must never overwrite the lossless original.
- Distinguish 4K masters from page assets: for newly generated PNG masters, the default compression width is 2560; use the project's recorded `--max-width` (such as `4096`) when refreshing an established 4K page asset. Skip compression for valid WebP-only projects, and verify the browser-loaded dimensions, not only the master.
- Never hand-edit an export. `exports/storyboard.md` and `exports/storyboard.html` are generated; edit the story data and export again.
- Keep editable story JSON in the project. Keep assembled prompts, analysis drafts, rejected candidates, and temporary frames in a per-task directory under the system temporary directory. After delivery, clean up rejected or experimental material, but retain the full prompt, model/parameter record, reference paths, and accepted candidate for every adopted generated still in the production record.
- Never print secrets or embed them in frontend files. Use a project-local `.env` excluded from version control, and make sure a static server cannot expose it.
- Bound automated retries. Treat authentication, permission, billing, and model-activation errors as non-retryable.

## Deliverables and their names

These three are easy to confuse, and confusing them in a delivery summary is a real defect:

- **Compressed web image** (`scripts/make_posters.py`): the same picture as its master, only smaller, for the page to load. Never call it a poster or a designed asset.
- **Storyboard** (`scripts/export_storyboard.py`): `exports/storyboard.md` and `exports/storyboard.html`, generated from the story data. The HTML is a static, printable document; it is not the scrolling story page.
- **Display poster** (on request, via `sn-infographic`): a composed image with a theme, a main visual, and a few key facts, made from a brief derived from confirmed story content. Keep the exact long Chinese copy in the page and the storyboard instead.

## Validation

Before delivery:

1. Validate JSON, JavaScript, shell, and Python syntax.
2. Run `scripts/verify_media.py` against the project root and require every declared still.
3. Run `scripts/export_storyboard.py` when a storyboard is part of the delivery, and confirm it reports the expected shot count and writes both files.
4. Test a fresh browser session: forward and reverse progress, chapter navigation, missing-media fallback, reduced motion, and a narrow viewport with no overflow in the copy panel.
5. Inspect a labeled contact sheet. Prioritize correct identities, key objects, and scene meaning over incidental generative detail. Check for baked-in watermarks, brand marks, and stray text, because those live in the pixels and no stylesheet can remove them.
6. Report the preview URL, the project path, which deliverables exist, the media directories, the model configuration, the check results, and any remaining external blocker.

## Video clips (Agnes video)

On request only. The default model is Agnes Video v2.0, which renders high-definition clips; Agnes Video 2.5 Flash is the alternative when reference images or a last-frame anchor are needed, since it is capped at 720P. Both contracts, their constraints, and the measured behaviour are in [references/agnes-video.md](references/agnes-video.md), and the workflow is the video section of [references/produce-and-deliver.md](references/produce-and-deliver.md).

`scripts/agnes_video.py` is the executor: it reads `prompts/video-manifest.json`, resolves each clip's anchor, calls the Agnes CLI, and normalizes every downloaded clip with FFmpeg so `verify_media.py` passes. Run it with `--dry-run` first to see every call before spending anything. The script does not author content — clip prompts and anchor prompts are written into the project first, which is where the reasoning belongs.

Image work stays with SenseNova. Every video clip must explicitly declare `anchor_mode`: `generate` (SenseNova generates an anchor and returns its public HTTPS URL), `reference` (supplied URLs or the neighbouring chapters' recorded anchors), or `url` (explicit first/last frame URLs). The template selects `generate` for dives and `reference` for connectors. Missing modes and `text` are rejected before generation. If an anchor URL is unavailable, report the failure rather than submitting unanchored video. Never publish a user's images to a host without asking.

A dive that ran records the anchor URL it started from in `.motion-state/video-anchors.json`, and that is what its neighbouring connectors reference.

An image story and its storyboard remain complete without any of this, and the image path must never depend on video tooling, credentials, or the Agnes skill. Never describe a project as having generated motion unless the clips exist and are in the project.
