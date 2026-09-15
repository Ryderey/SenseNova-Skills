# SN Motion HTML Story Guide

English | [简体中文](sn-motion-html_CN.md)

[`sn-motion-html`](../skills/sn-motion-html/SKILL.md) turns a set of images and a short narrative into one scroll-driven web page. The reader scrolls; the page advances through an ordered chapter route on a single fixed media stage, with each chapter's copy staying readable on its own scene.

Use it for image stories, scroll-driven product tours, image timelines, and immersive scene walkthroughs. A single-image infographic, poster, or long image belongs to [`sn-infographic`](../skills/sn-infographic/SKILL.md); redesigning one reference image belongs to [`sn-image-imitate`](../skills/sn-image-imitate/SKILL.md). Ordinary web apps, dashboards, and autoplay video pages are out of scope.

## What you get

- A reusable project, not a one-off HTML file: web source, `content/story.json`, accepted images, web posters, and a short README.
- Editable content: chapters, copy, navigation labels, and sources live in `content/story.json`.
- One fixed media stage and one ordered route, expressed through header, panel material, typography, navigation, and per-scene copy placement.
- Web posters generated from lossless masters, so compression never touches the original.
- A reduced-motion path that keeps the story readable with stills only.

## Requirements

Image mode is the default and needs only Python and Pillow. It reuses the existing SenseNova runtime for any new stills, so no second image client is installed.

| Capability | Image mode (default) | Video mode (explicit) |
|---|---|---|
| Python + Pillow | Required | Required |
| SenseNova credentials | Only when new stills are generated | Only when new stills are generated |
| FFmpeg + ffprobe | Not used | Required |
| Video provider credentials | Not used | Required |

Without FFmpeg, ffprobe, or any video credentials, an image story still initializes, builds, validates, and delivers. That is a supported configuration, not a degraded one.

## Media mode

Each project records `meta.mediaMode` in `content/story.json`:

- `images` — the default. Every chapter needs one valid still. `clip` and `connectors` are not required, and the page never requests a clip even if legacy fields remain.
- `video` — explicit request only. Every chapter needs a still and a scene clip, and each adjacent pair needs a connector clip. FFmpeg, ffprobe, and provider credentials become required.

An explicit `images` always wins over leftover video fields. A project with no `mediaMode` field is treated as video only when it actually declares clips or connectors; otherwise it is treated as images.

## Initialize a project

Resolve these logical paths first. They are resolved at run time and are not environment variables.

- `PYTHON` — the interpreter that passes [`sn-image-doctor`](../skills/sn-image-doctor/SKILL.md).
- `MOTION_SKILL_DIR` — the directory containing the skill's `SKILL.md`.
- `PROJECT_ROOT` — the output directory for the story.

```bash
"<absolute PYTHON path>" "<absolute MOTION_SKILL_DIR>/scripts/init_project.py" "<absolute PROJECT_ROOT>" \
  --title "故事标题" \
  --style cinematic \
  --ui folio \
  --media images \
  --lang zh
```

| Option | Meaning |
|---|---|
| `--title` | Story title. Quotes, backslashes, and HTML characters are escaped safely. |
| `--style` | `anime`, `cinematic`, or `cgi`. Controls the visual world and the still prompts. |
| `--ui` | `folio`, `caption`, or `graphic`. Controls header, copy treatment, navigation, and typography. |
| `--media` | `images` (default) or `video`. |
| `--lang` | `zh` or `en`. Sets the interface language and `html lang`. |
| `--force` | Merge into a non-empty directory. |

Style and UI are independent: never infer one from the other.

`--force` refreshes template scaffolding but never overwrites `content/story.json`, `assets/`, `.env`, `tmp/`, or `.motion-state/`. It prints which files it preserved.

An image project deliberately ships no video manifest, no video credentials file, and no empty video directories, so nothing implies a video dependency the project does not have.

## Production flow

1. Collect the subject, audience, language, device targets, chapter scale, supplied images, reference images, and factual requirements. Already-stated requirements count as decisions; do not re-ask them.
2. For factual stories, research first and keep source notes separate from the display copy.
3. Build the chapter blueprint: one dominant visual event per chapter, its still, its copy, and its copy position.
4. Present one review package covering the visual direction and the chapter arrangement, and record the user's decisions.
5. When new stills are needed, generate a small consistency gate first (normally opening, middle, and ending), then complete the still set after the direction is accepted. Reuse the existing SenseNova runtime; see [`sn-image-base`](../skills/sn-image-base/SKILL.md).
6. Put the words in HTML, not in the pixels. Body copy, titles, navigation labels, and sources stay in `content/story.json` so they remain editable and translatable.
7. Save lossless masters under `assets/images/scenes/`, then generate the web posters.
8. Validate, review a contact sheet, exercise a fresh browser session, and hand off.

## Common commands

Run these from anywhere; every path is absolute.

```bash
# Validate the story data and the stills (image mode never invokes ffprobe)
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"

# Build web posters from the PNG masters
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/make_posters.py" "<absolute PROJECT_ROOT>"

# Build a labeled review sheet (written to the system temporary directory by default)
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"

# Preview locally
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

`verify_media.py` exits `0` when everything checks out, `1` on a failed check, and `2` when declared media is missing. `--allow-missing` turns the missing-media exit into `0`, which is useful while a project is still being assembled.

## Project layout

```text
index.html               entry point
styles.css               stage and UI treatment
src/app.js               loads story.json, validates it, localizes the UI
src/motion-runtime.js    the staged route, progress mapping, and cross-fades
content/story.json       the editable story: meta, chapters, sources
prompts/style-preamble.txt   the chosen image style block
prompts/style-motion.txt     the chosen motion block (video mode)
assets/images/scenes/    scene stills and their posters
scripts/                 the project's own check, poster, sheet, and preview tools
```

Video projects add `prompts/video-manifest.json`, `prompts/video/`, `assets/video/`, a `.env`, and `scripts/seedance_pipeline.py`.

## Preview and hosting

`scripts/serve_project.py` is a local preview server, not a deployment target. It serves only what the page requests — the HTML entry point, `styles.css`, `src/` JavaScript, `content/` JSON, and final media under `assets/` — and refuses configuration files, prompts, scripts, private state, temporary files, dotfiles, directory listings, and paths that resolve outside the project. It answers range requests so media can be seeked.

Open the page over HTTP. The page reads `content/story.json` with `fetch`, so opening `index.html` directly from the filesystem will not work.

## Troubleshooting

- **The preview refuses a file.** Only the paths above are served. Move the asset under `assets/`, or reference it from `content/` if it is story data.
- **"Could not load the story data."** The page was opened over `file://`, or `content/story.json` is missing. Use the preview server.
- **"The story data is incomplete."** `meta`, `chapters`, or the chapter list is missing or empty. The message names the failing field.
- **`verify_media.py` exits 2.** A still or clip is missing; the report lists each one. Use `--allow-missing` while assembling.
- **`verify_media.py` exits 1.** A declared value is invalid — an unsafe chapter `id`, a duplicate `id`, a non-positive `span`, an unknown enum, or an unreadable image. Details are printed per item.
- **A still is rejected as unreadable.** The file is not a decodable image, or it is truncated. Re-export it.
- **`make_posters.py` reports no PNG masters.** Stills are already web-ready, or the masters live outside `assets/images/scenes/`. Point `content/story.json` at the web-format files you actually have.
- **Contact sheet labels are numbers only.** No CJK-capable font was found on this machine, so labels were reduced to indices to stay readable. Install a CJK font to get titles back.
- **The page shows the fallback panel.** That still failed to load; check the path in `content/story.json` and the network panel.
- **A watermark or brand mark is visible in the delivered scenes.** Watermarks live in the pixels and no stylesheet can remove them, so confirm each still on the contact sheet before delivery. If the stills came from an external tool, regenerate without its watermark; the image skills in this repository default to `watermark=false`.
- **The interface language does not match the content.** When `meta.lang` is absent the page infers it from the content's script, which is less deterministic than declaring it. Add `meta.lang`.
- **The page has no motion at all.** When the operating system has animations switched off, the browser reports `prefers-reduced-motion: reduce` and the skill correctly disables the still drift. That is intended behaviour, not a fault. To review the designed motion, append `?motion=full` to the preview URL, or `?motion=reduce` to force the reduced path; with no parameter the system preference always wins.
- **The dissolve is too fast or too slow, or the zoom is too strong.** Tune `meta.crossfade` (viewport heights; image mode defaults to 0.8) and `meta.drift` (zoom range per chapter; image mode defaults to 0.16).
- **Video mode reports that ffprobe is required.** Video validation needs FFmpeg installed. Image mode never does.

## Optional video clips

Clip generation is a separate, explicitly authorized deliverable. An image story must not be described as a generated continuous-camera result unless the clips exist.

Before the first metered or paid request, present the provider, model, planned clip count, retry allowance, and cost basis, and obtain authorization for that batch. Creative approval of the story does not authorize generation. Without credentials, still validate the manifest offline and deliver the image story.

The dependency order is fixed: generate scene clips, extract their real first and last frames, then generate connector clips from adjacent frames. Normalize every final clip to the same codec, dimensions, frame rate, exact duration, short GOP, and `faststart`. See [references/seedance.md](../skills/sn-motion-html/references/seedance.md) for the Ark contract, and verify current model documentation before use.
