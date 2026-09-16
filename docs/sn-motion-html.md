# SN Motion HTML Story Guide

English | [简体中文](sn-motion-html_CN.md)

[`sn-motion-html`](../skills/sn-motion-html/SKILL.md) turns a set of images and a short narrative into one scroll-driven web page, and exports the same story as a storyboard. The reader scrolls; the page advances through an ordered chapter route on a single fixed media stage, with each chapter's copy staying readable on its own scene.

Use it for image stories, scroll-driven product tours, image timelines, and immersive scene walkthroughs. A single-image infographic, poster, or long image belongs to [`sn-infographic`](../skills/sn-infographic/SKILL.md); redesigning one reference image belongs to [`sn-image-imitate`](../skills/sn-image-imitate/SKILL.md). Ordinary web apps, dashboards, and autoplay video pages are out of scope.

## What you get

- A reusable project, not a one-off HTML file: web source, `content/story.json`, accepted images, compressed web images, and a short README.
- Editable content: chapters, copy, navigation labels, and sources live in `content/story.json`.
- One fixed media stage and one ordered route, expressed through header, panel material, typography, navigation, and per-scene copy placement.
- A storyboard: `exports/storyboard.md` and `exports/storyboard.html`, generated from the same story data, so the whole sequence can be read, annotated, or printed without scrolling the page.
- A reduced-motion path that keeps the story readable with stills only.

A display poster — a composed image with its own theme and key facts — is a separate, on-request deliverable produced by [`sn-infographic`](../skills/sn-infographic/SKILL.md) and saved as `exports/story-poster.png`. It is not the same thing as the compressed web images this skill writes.

## Requirements

Only Python, Pillow, and a browser. Any new stills reuse the existing SenseNova runtime, so no second image client is installed. Supplied images work as-is, so a complete delivery can cost zero model calls.

| Capability | Needed |
|---|---|
| Python + Pillow | Required |
| SenseNova credentials | Only when new stills or a display poster are generated |
| FFmpeg and ffprobe | Only for video clips: normalization and validation |
| Agnes credentials (`AGNES_API_KEY`) | Only for video clips |
| Image host or public storage | Only when you anchor a clip to your own still (`anchor_mode: url`) |

No FFmpeg, no ffprobe, and no video credentials: an image story still initializes, builds, validates, exports, and delivers. That is a supported configuration, not a degraded one.

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
| `--media` | `images` (default) or `video` (later phase; see the note below). |
| `--lang` | `zh` or `en`. Sets the interface language and `html lang`. |
| `--force` | Merge into a non-empty directory. |

Style and UI are independent: never infer one from the other.

`--force` refreshes template scaffolding but never overwrites `content/story.json`, `assets/`, `.env`, `tmp/`, or `.motion-state/`. It prints which files it preserved.

An image project deliberately ships no video manifest, no video credentials file, and no empty video directories, so nothing implies a video dependency the project does not have.

## Production flow

1. Collect the subject, audience, language, device targets, chapter scale, supplied images, reference images, and factual requirements. Already-stated requirements count as decisions; do not re-ask them.
2. For factual stories, research first and keep source notes separate from the display copy.
3. Build the chapter blueprint: one dominant visual event per chapter, its still, its copy, and its copy position. State the shot direction (`intent`, `framing`, `motionNote`) when it is worth recording.
4. Present one review package covering the visual direction and the chapter arrangement, and record the user's decisions.
5. When new stills are needed, generate a small consistency gate first (normally opening, middle, and ending), then complete the still set after the direction is accepted. Reuse the existing SenseNova runtime; see [`sn-image-base`](../skills/sn-image-base/SKILL.md).
6. Put the words in HTML, not in the pixels. Body copy, titles, navigation labels, and sources stay in `content/story.json` so they remain editable and translatable.
7. Save lossless masters under `assets/images/scenes/`, then generate the compressed web images.
8. Export the storyboard when the whole story has to be reviewable at once.
9. Validate, review a contact sheet, exercise a fresh browser session at desktop, tablet, and phone widths, and hand off.

## Common commands

Run these from anywhere; every path is absolute.

```bash
# Validate the story data and the stills (never invokes ffprobe)
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"

# Compress the scene masters into the web images the page loads
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/make_posters.py" "<absolute PROJECT_ROOT>"

# Export the storyboard as Markdown and as a static HTML document
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/export_storyboard.py" "<absolute PROJECT_ROOT>"

# Build a labeled review sheet (written to the system temporary directory by default)
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"

# Preview locally
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

`verify_media.py` exits `0` when everything checks out, `1` on a failed check, and `2` when declared media is missing. `--allow-missing` turns the missing-media exit into `0`, which is useful while a project is still being assembled.

`export_storyboard.py` exits `0` on success, `1` when the story data is invalid, and `2` when a declared still is missing. It has no allow-missing option: an exported storyboard that points at absent images would be a broken deliverable. It writes nothing unless every shot checks out.

## The storyboard

`exports/storyboard.md` and `exports/storyboard.html` are generated from `content/story.json` and list every shot in chapter order with its still, copy, tags, chapter ID, and any declared shot direction.

- They are generated, not authored: edit `content/story.json` and export again. Hand-edits are lost on the next export.
- Both documents show the same shots, the same copy, and the same sources, so they cannot drift apart.
- The Markdown is for editing and diffing; media paths are relative from inside `exports/`, so images resolve in an editor that renders them.
- The HTML is a static, print-ready document: no server and no JavaScript needed, a two-column layout that stacks on narrow screens, page breaks that keep each shot together, and a print stylesheet. It is not the scrolling story page, and it does not share its runtime.
- Only the exported deliverables are served by the preview — `exports/storyboard.html`, `exports/story-poster.png`, and any alternative poster directions named `exports/story-poster-clarity.png` or `exports/story-poster-photo.png`. The Markdown and everything else under `exports/` stay private.

## Project layout

```text
index.html               entry point
styles.css               stage and UI treatment
src/app.js               loads story.json, validates it, localizes the UI
src/motion-runtime.js    the staged route, progress mapping, and cross-fades
content/story.json       the editable story: meta, chapters, sources
prompts/style-preamble.txt   the chosen image style block
prompts/style-motion.txt     the chosen motion block (written by the initializer; an image story never reads it)
assets/images/scenes/    scene stills and their compressed web images
exports/                 storyboard.md and storyboard.html once exported, plus the on-request story-poster.png
scripts/                 the project's own check, compression, storyboard, sheet, and preview tools
                         (a video project also gets agnes_video.py, its clip pipeline)
```

## Preview and hosting

`scripts/serve_project.py` is a local preview server, not a deployment target. It serves only what the page requests — the HTML entry point, `styles.css`, `src/` JavaScript, `content/` JSON, final media under `assets/`, and `exports/storyboard.html` — and refuses configuration files, prompts, scripts, private state, temporary files, dotfiles, directory listings, and paths that resolve outside the project. It answers range requests so media can be seeked.

Open the page over HTTP. The page reads `content/story.json` with `fetch`, so opening `index.html` directly from the filesystem will not work. The exported storyboard HTML is the exception: open it directly, over HTTP, or print it.

## Troubleshooting

- **The preview refuses a file.** Only the paths above are served. Move the asset under `assets/`, or reference it from `content/` if it is story data.
- **"Could not load the story data."** The page was opened over `file://`, or `content/story.json` is missing. Use the preview server.
- **"The story data is incomplete."** `meta`, `chapters`, or the chapter list is missing or empty. The message names the failing field.
- **`verify_media.py` exits 1.** A declared value is invalid — an unsafe chapter `id`, a duplicate `id`, a non-positive `span`, a `shot` field that is not a non-empty string, an unknown enum, or an unreadable image. Details are printed per item.
- **`verify_media.py` exits 2.** A still is missing; the report lists each one. Use `--allow-missing` while assembling.
- **`export_storyboard.py` exits 2.** A declared still is missing, and nothing was written. Add the image, then export again; a "待配图" draft belongs in the review step, not in `exports/`.
- **Edits to the storyboard disappeared.** The exports are generated. Edit `content/story.json` and export again.
- **A still is rejected as unreadable.** The file is not a decodable image, or it is truncated. Re-export it.
- **`make_posters.py` reports no PNG masters.** Stills are already web-ready, or the masters live outside `assets/images/scenes/`. Point `content/story.json` at the web-format files you actually have.
- **You need a poster, not a compressed image.** `make_posters.py` only makes smaller copies of existing stills. A designed poster with a title and key facts is a brief for [`sn-infographic`](../skills/sn-infographic/SKILL.md), delivered as `exports/story-poster.png`; say so explicitly, because it is a separate deliverable with its own generation and review.
- **Contact sheet labels are numbers only.** No CJK-capable font was found on this machine, so labels were reduced to indices to stay readable. Install a CJK font to get titles back.
- **The page shows the fallback panel.** That still failed to load; check the path in `content/story.json` and the network panel.
- **A watermark or brand mark is visible in the delivered scenes.** Watermarks live in the pixels and no stylesheet can remove them, so confirm each still on the contact sheet before delivery. If the stills came from an external tool, regenerate without its watermark; the image skills in this repository default to `watermark=false`.
- **The interface language does not match the content.** When `meta.lang` is absent the page infers it from the content's script, which is less deterministic than declaring it. Add `meta.lang`.
- **The page has no motion at all.** When the operating system has animations switched off, the browser reports `prefers-reduced-motion: reduce` and the skill correctly disables the still drift. That is intended behaviour, not a fault. To review the designed motion, append `?motion=full` to the preview URL, or `?motion=reduce` to force the reduced path; with no parameter the system preference always wins.
- **The dissolve is too fast or too slow, or the zoom is too strong.** Tune `meta.crossfade` (viewport heights; image mode defaults to 0.8) and `meta.drift` (zoom range per chapter; image mode defaults to 0.16).

## Video clips (Agnes Video 2.5 Flash)

On request only. Clip generation uses Agnes Video 2.5 Flash through the sibling `agnes-media` skill's bundled CLI, driven by `scripts/agnes_video.py`. The request contract, constraints, and measured provider behaviour are in [references/agnes-video.md](../skills/sn-motion-html/references/agnes-video.md); the workflow is section 10 of [references/workflow.md](../skills/sn-motion-html/references/workflow.md).

```bash
# See every call the pipeline would make, without spending anything
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/agnes_video.py" "<absolute PROJECT_ROOT>" --dry-run

# Generate, normalize, and write each clip's first frame as the page still
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/agnes_video.py" "<absolute PROJECT_ROOT>" --write-stills
```

Requirements: `AGNES_API_KEY` in the environment, `AGNES_SKILL_DIR` pointing at the Agnes media skill, and FFmpeg plus ffprobe for normalization and validation. An image story needs none of them.

Two things are worth knowing before you ask for clips:

- **Flash accepts no local media.** Every first frame, last frame, or reference must be a public HTTPS URL, so each clip declares how it gets one: generated through Agnes (`generate`), published by you (`url`), or composed from the prompt alone (`text`). This skill never publishes your images to a host on its own.
- **Provider output is not the deliverable.** A requested 4-second 720P clip came back as 1280×704 and 4.46 seconds, so the pipeline always normalizes locally; `verify_media.py` then requires the exact manifest dimensions, frame rate, and duration.

A transition between two chapters is anchored on their boundary frames, which are local extracts — anchoring one therefore needs hosted frame URLs. Until you provide them, a transition runs in `text` mode or the seam is declared an accepted visible cut.
