---
name: sn-motion-html
description: Build a scroll-driven image-story web page from supplied images or a short narrative with SenseNova, and export the same story as a storyboard. Use for “SenseNova 技能” requests involving 图片故事网页、滚动叙事网页、图像时间线、沉浸式场景浏览、图片做成网页、分镜稿、storyboard, product scroll story, or turning an existing image set into one continuous page. Images need no video tooling; a composed display poster routes to the infographic workflow, and clip generation is a separate, later-phase path. Single-image infographics, posters, and long images use the infographic workflow instead; ordinary web apps and autoplay video pages are out of scope.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: image-visualization
  priority: 7
  user_visible: true
---

# sn-motion-html

Deliver a reusable project, not a one-off HTML file. One fixed full-viewport media stage and one ordered chapter route carry the whole story: the reader scrolls, the page advances through the chapter sequence, and every chapter's copy stays readable together on its own scene.

The same story data also exports a storyboard, so the whole sequence can be reviewed, annotated, or printed without scrolling anything. Both come from `content/story.json`.

This phase delivers three things, in this order of priority:

| Deliverable | What the user gets | Built by |
|---|---|---|
| Image story page, default | A responsive, previewable story with real stills and complete copy | The project template in this skill |
| Storyboard | The same shots in reading order with stills, copy, and shot direction, as Markdown and as a static HTML document | `scripts/export_storyboard.py` |
| Display poster, on request | A composed image with its own theme, main visual, and a few key facts | The infographic workflow (`sn-infographic`), given a brief derived from the story |
| Video clips, on request | Scroll-scrubbed scene clips, and optionally transitions between chapters | `scripts/agnes_video.py`, with Agnes Video 2.5 Flash |

Generate only what was asked for. Do not add a poster or extra stills to a delivery that did not request them.

## Runtime paths

Resolve `MOTION_SKILL_DIR` as the absolute directory containing this `SKILL.md`. Resolve `PROJECT_ROOT` as the absolute output directory chosen for the story. Resolve `BASE_SKILL_DIR` as the absolute directory of the sibling `sn-image-base` skill, `RUNNER` as `BASE_SKILL_DIR/scripts/sn_agent_runner.py`, and `PYTHON` as the same interpreter that passes `sn-image-doctor`.

Use absolute paths regardless of the current working directory, and never assume the host inherited a previously activated shell environment. On PowerShell, invoke a quoted executable path with the call operator (`& "<absolute PYTHON path>" ...`); on POSIX shells, execute the quoted path directly. These are logical path names, not environment variables; never ask the user to configure them.

New scene images reuse the existing SenseNova runtime through `RUNNER`; do not introduce a second image client. Credentials follow the `sn-image-base` contract: `SENSENOVA_API_KEY`, capability-specific overrides, and `SN_ENV_FILE`.

## What an image story needs

Only Python, Pillow, and a browser. No FFmpeg, no ffprobe, no video credentials, no image host, and no deployment step. Supplied images work as-is, so a complete delivery can cost zero model calls.

A story is readable without any generated motion: the stills, the copy, the navigation, and the cross-dissolves carry it. Do not promise real subject movement, object motion, or a generated continuous shot — those need clips that do not exist in this phase.

## Route the work

1. Collect the subject, audience, language, device targets, chapter scale, supplied images, reference images, factual requirements, and any explicit user decisions. Already-stated requirements count as decisions; do not re-ask them.
2. When stills are missing, inspect the environment for an available image-generation capability before promising output. Reuse the existing SenseNova runtime rather than substituting placeholders.
3. For factual or source-based stories, research first and keep source notes separate from the display copy.
4. Build the chapter blueprint and the shot plan: per chapter, the dominant visual event, the still, the copy, the copy position, and — when it is worth stating — the optional `shot` direction (`intent`, `framing`, `motionNote`).
5. Present one review package covering the visual direction and the chapter arrangement. Record the user's decisions; when the user already specified these, present the package as a confirmation rather than a fresh question.
6. When new stills are needed, generate a small consistency gate first (normally opening, middle, and ending; do not pad a short story to three). Complete the still set only after the direction is accepted.
7. Assemble the project from `content/story.json`, then verify media and browser behavior.
8. Export the storyboard when the user wants the whole story readable at once, or an artifact to annotate or print.
9. When the user asks for a poster, derive the brief from the confirmed story and hand it to `sn-infographic`; never present a compressed still as a designed poster.
10. Deliver the project path, the preview URL, which deliverables exist, the check results, and any remaining blocker.

Read [references/workflow.md](references/workflow.md) for the full sequence, and only the additional references the current stage needs:

- [references/schemas.md](references/schemas.md) when creating `content/story.json` or exporting a storyboard.
- [references/prompting.md](references/prompting.md) when generating stills or recording shot direction.
- [references/style-presets.md](references/style-presets.md) when choosing or adapting a visual preset.
- [references/frontend.md](references/frontend.md) before selecting or adapting the interface treatment or the storyboard layout.
- [references/seedance.md](references/seedance.md) only if a later phase actually reopens the video path; it is a frozen reference, not current capability.

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
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/export_storyboard.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

## Production invariants

- Keep narrative data in `content/story.json`; never hardcode chapter copy into the runtime. The page and the storyboard are both generated from it, so it stays the single source of truth.
- Keep one complete, static, transparent copy block per chapter, visible together. Do not rotate paragraphs within a scene.
- Maintain a single style preamble and immutable identity blocks for recurring subjects.
- The page must not request video, probe `ffprobe`, or load a clip. Prove it from the network panel and the CLI checks, not from inspection alone.
- Use project-relative media paths. Reject absolute paths, drive-letter paths, and `..` escapes; after resolving symlinks the path must still be inside the allowed directory. Import user-supplied images as project assets first so the delivered page never depends on the user's machine layout.
- Copy articles have no solid card fill. Use edge-free localized gradients, text shadow, or fine rules for contrast.
- Keep stills and their compressed web images separate; compression must never overwrite the lossless original.
- Never hand-edit an export. `exports/storyboard.md` and `exports/storyboard.html` are generated; edit the story data and export again.
- Keep editable story JSON in the project. Keep assembled prompts, analysis drafts, rejected candidates, and temporary frames in a per-task directory under the system temporary directory, and clean them up after delivery.
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

## Video clips (Agnes Video 2.5 Flash)

On request only. The selected model is Agnes Video 2.5 Flash; its request contract, constraints, and measured behaviour are in [references/agnes-video.md](references/agnes-video.md), and the workflow is section 10 of [references/workflow.md](references/workflow.md).

`scripts/agnes_video.py` is the executor: it reads `prompts/video-manifest.json`, resolves each clip's anchor, calls the Agnes CLI, and normalizes every downloaded clip with FFmpeg so `verify_media.py` passes. Run it with `--dry-run` first to see every call before spending anything. The script does not author content — clip prompts and anchor prompts are written into the project first, which is where the reasoning belongs.

The constraint that shapes the whole design: **Flash takes no local media, so every frame or reference it receives must be a public HTTPS URL.** A project's own stills are not, so each clip declares an `anchor_mode` — `generate` (create the anchor through Agnes and use its own public URL, the default for a dive), `reference` (public images that guide the clip; a connector borrows the two chapters' recorded anchors, which needs no host), `url` (public URLs the user controls, to pin a boundary exactly), or `text` (no media, composed from the prompt). Never publish a user's images to a host without asking.

A dive that ran records the anchor URL it started from in `.motion-state/video-anchors.json`, and that is what its neighbouring connectors reference.

An image story and its storyboard remain complete without any of this, and the image path must never depend on video tooling, credentials, or the Agnes skill. Never describe a project as having generated motion unless the clips exist and are in the project.

