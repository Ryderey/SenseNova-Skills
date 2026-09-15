---
name: sn-motion-html
description: Build a scroll-driven image-story web page from supplied images or a short narrative with SenseNova. Use for “SenseNova 技能” requests involving 图片故事网页、滚动叙事网页、图像时间线、沉浸式场景浏览、图片做成网页、product scroll story, or turning an existing image set into one continuous page. Images are the default deliverable and need no video tooling; clip generation is a separate explicitly authorized path. Single-image infographics, posters, and long images use the infographic workflow instead; ordinary web apps and autoplay video pages are out of scope.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: image-visualization
  priority: 7
  user_visible: true
---

# sn-motion-html

Deliver a reusable project, not a one-off HTML file. One fixed full-viewport media stage and one ordered chapter route carry the whole story: the reader scrolls, the page advances through the chapter sequence, and every chapter's copy stays readable together on its own scene.

Image mode is the default. It needs only Python, Pillow, and the existing SenseNova image runtime, and it is the mode to build unless the user explicitly asks for generated video clips.

## Runtime paths

Resolve `MOTION_SKILL_DIR` as the absolute directory containing this `SKILL.md`. Resolve `PROJECT_ROOT` as the absolute output directory chosen for the story. Resolve `BASE_SKILL_DIR` as the absolute directory of the sibling `sn-image-base` skill, `RUNNER` as `BASE_SKILL_DIR/scripts/sn_agent_runner.py`, and `PYTHON` as the same interpreter that passes `sn-image-doctor`.

Use absolute paths regardless of the current working directory, and never assume the host inherited a previously activated shell environment. On PowerShell, invoke a quoted executable path with the call operator (`& "<absolute PYTHON path>" ...`); on POSIX shells, execute the quoted path directly. These are logical path names, not environment variables; never ask the user to configure them.

New scene images reuse the existing SenseNova runtime through `RUNNER`; do not introduce a second image client. Credentials follow the `sn-image-base` contract: `SENSENOVA_API_KEY`, capability-specific overrides, and `SN_ENV_FILE`. Video credentials belong to the optional video path only and never substitute for image credentials.

## Media mode

The project records its mode in `content/story.json` as `meta.mediaMode`, either `images` or `video`.

| Behavior | `images`, the default | `video`, explicit request only |
|---|---|---|
| Required media | One valid still per chapter | One still, one scene clip, and one connector clip per adjacent pair |
| Interaction | Staged still transitions with restrained movement | Scroll position maps to the clip playhead, forward and reverse |
| `clip` / `connectors` | Not required, and never loaded even if legacy fields remain | Required and validated |
| Tooling | Python and Pillow | Adds FFmpeg and ffprobe |
| Credentials | Image credentials only when new stills are needed | Adds the selected video provider's credentials |
| Missing media | Report the missing still; never pass a placeholder off as the delivered scene | Keep the still visible and report the degradation |

New projects always write `mediaMode`. When reading a project without the field, treat it as a video project only if it actually declares clips or connectors; otherwise treat it as images and tell the user to add the field. Reject unknown values. An explicit `images` wins over leftover video fields so nothing is loaded by accident.

## Route the work

1. Collect the subject, audience, language, device targets, chapter scale, supplied images, reference images, factual requirements, and any explicit user decisions. Already-stated requirements count as decisions; do not re-ask them.
2. When stills are missing, inspect the environment for an available image-generation capability before promising output. Reuse the existing SenseNova runtime rather than substituting placeholders.
3. For factual or source-based stories, research first and keep source notes separate from the display copy.
4. Build the chapter blueprint and the shot plan: per chapter, the dominant visual event, the still, the copy, and the copy position.
5. Present one review package covering the visual direction and the chapter arrangement. Record the user's decisions; when the user already specified these, present the package as a confirmation rather than a fresh question.
6. When new stills are needed, generate a small consistency gate first (normally opening, middle, and ending; do not pad a short story to three). Complete the still set only after the direction is accepted.
7. Assemble the project from `content/story.json`, then verify media and browser behavior.
8. Deliver the project path, the preview URL, the actual media mode, the check results, and any remaining blocker.

Read [references/workflow.md](references/workflow.md) for the full sequence, and only the additional references the current stage needs:

- [references/schemas.md](references/schemas.md) when creating `content/story.json` or a video manifest.
- [references/prompting.md](references/prompting.md) when generating stills or recurring identity references.
- [references/style-presets.md](references/style-presets.md) when choosing or adapting a visual preset.
- [references/frontend.md](references/frontend.md) before selecting or adapting the interface treatment.
- [references/seedance.md](references/seedance.md) only when the optional Ark video path is actually selected.

## Start from the template

```bash
"<absolute PYTHON path>" "<absolute MOTION_SKILL_DIR>/scripts/init_project.py" "<absolute PROJECT_ROOT>" \
  --title "Story title" \
  --style cinematic \
  --ui folio \
  --media images
```

Choose `--style anime`, `--style cinematic`, or `--style cgi`; choose `--ui folio`, `--ui caption`, or `--ui graphic` independently. Style governs the visual world and the generated stills; UI governs header, copy treatment, navigation, and typography. Never infer one from the other. Per-chapter `copyPosition` may be `left`, `right`, `bottom`, or `center`.

The initializer copies the template and the project scripts, creates the media directories, and for image projects does not create video credentials or an empty video manifest. Replace the example chapters; never leave placeholder subject matter in the delivered project.

From the initialized project, the common commands are:

```bash
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

## Production invariants

- Keep narrative data in `content/story.json`; never hardcode chapter copy into the runtime.
- Keep one complete, static, transparent copy block per chapter, visible together. Do not rotate paragraphs within a scene.
- Maintain a single style preamble and immutable identity blocks for recurring subjects.
- Image mode must not request video, probe `ffprobe`, or load a clip. Prove it from the network panel and the CLI checks, not from inspection alone.
- Use project-relative media paths. Reject absolute paths, drive-letter paths, and `..` escapes; after resolving symlinks the path must still be inside the allowed directory. Import user-supplied images as project assets first so the delivered page never depends on the user's machine layout.
- Copy articles have no solid card fill. Use edge-free localized gradients, text shadow, or fine rules for contrast.
- Keep stills and web posters separate; compression must never overwrite the lossless original.
- Keep editable story JSON in the project. Keep assembled prompts, analysis drafts, rejected candidates, and temporary frames in a per-task directory under the system temporary directory, and clean them up after delivery.
- Never print secrets or embed them in frontend files. Use a project-local `.env` excluded from version control, and make sure a static server cannot expose it.
- Bound automated retries. Treat authentication, permission, billing, and model-activation errors as non-retryable.

## Optional video path

Video clips are a separate authorized deliverable, never an automatic upgrade of an image story. An image story may claim an image narrative; do not claim a generated continuous-camera result unless the clips actually exist.

Before any paid or metered video request, present the provider, model, planned clip count, retry allowance, and cost basis, and obtain explicit authorization for that batch. Creative approval of the story does not authorize generation, and an unanswered message is not approval. Without credentials, still read the guide, validate the manifest offline, and complete the image story.

The dependency order is fixed: generate scene clips first, extract their real boundary frames, then generate connector clips from adjacent frames. Normalize every final clip to identical codec, dimensions, frame rate, exact duration, no audio unless requested, short GOP, and `faststart`.

## Validation

Before delivery:

1. Validate JSON, JavaScript, shell, and Python syntax.
2. Run `scripts/verify_media.py` against the project root and require the declared media for the project's mode.
3. Test a fresh browser session: forward and reverse progress, chapter navigation, missing-media fallback, and reduced motion.
4. Inspect a labeled contact sheet. Prioritize correct identities, key objects, and scene meaning over incidental generative detail. Check for baked-in watermarks, brand marks, and stray text, because those live in the pixels and no stylesheet can remove them.
5. Report the preview URL, project path, media directories, model configuration, check results, and any remaining external blocker.
