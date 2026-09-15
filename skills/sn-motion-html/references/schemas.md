# Project schemas

## `content/story.json`

```json
{
  "meta": {
    "title": "Story title",
    "kicker": "Optional short genre or series label",
    "subtitle": "Short deck",
    "description": "Search and share description",
    "note": "Optional adaptation note",
    "style": "anime | cinematic | cgi",
    "ui": "folio | caption | graphic",
    "mediaMode": "images | video",
    "lang": "zh | en",
    "crossfade": 0.8,
    "drift": 0.16,
    "connectorSpan": 1.2
  },
  "chapters": [
    {
      "id": "01-opening",
      "label": "Opening",
      "eyebrow": "Chapter 1",
      "title": "A concise title",
      "subtitle": "Place or phase",
      "accent": "#B85C3C",
      "copyPosition": "left | right | bottom | center",
      "span": 4.6,
      "linger": 0.35,
      "paragraphs": ["Short paragraph one.", "Short paragraph two."],
      "tags": ["Source", "Theme"],
      "still": "assets/images/scenes/01-opening.webp",
      "clip": "assets/video/dives/01-opening.mp4"
    }
  ],
  "connectors": ["assets/video/connectors/01-opening-to-next.mp4"],
  "sources": [{"label": "Source title", "url": "https://example.com"}]
}
```

Requirements:

- `id` values are unique, filename-safe, and stable. Reject anything outside `[A-Za-z0-9][A-Za-z0-9._-]*`.
- `style` controls art direction; `ui` controls header, panel, typography, and navigation. Do not infer one from the other.
- `mediaMode` is `images` or `video`, and every new project writes it. An explicit `images` always wins, so a leftover `clip` field cannot make an image project load video. When the field is absent, treat the project as video only if it actually declares clips or connectors; otherwise treat it as images and ask the user to add the field. Reject unknown values.
- `lang` selects the interface strings and the `html lang` attribute. `zh` and `en` are the supported interface languages; the content follows the user's language.
- `crossfade` is the dissolve window in viewport heights for the arriving scene. It defaults to `0.8` in image mode and `0.14` in video mode, because a frame-matched video seam only has to hide the join while two unrelated stills have to dissolve. Lower it toward `0.2` for a crisper cut, raise it for a slower blend.
- `drift` is the still's zoom range across one chapter; even chapters zoom in, odd chapters zoom out. It defaults to `0.16` in image mode and `0.06` in video mode. Keep it modest: every step of zoom also crops the frame, so large values push subjects out of the safe area.
- Keep paragraphs short enough to display together at the minimum supported viewport. One chapter shows one complete, static copy block.
- `copyPosition` is optional. Choose it against the scene's focal subject and safe negative space.
- `span` is measured in viewport heights, not seconds. Larger values give the chapter more reading distance. It must be a finite positive number.
- `linger` (0–0.6) holds the middle of a chapter's scroll range still so the copy can be read.
- `still` is required in both modes.
- `clip` is required in video mode, and is absent or ignored in image mode.
- In video mode, `connectors.length` is `chapters.length - 1`. Use `null`, or omit a connector the user explicitly accepted as a visible cut.

### Path rules

Media paths are project-relative. Reject absolute paths, drive-letter paths, UNC paths, and `..` traversal; after resolving symlinks the target must still be inside the project. Import a user-supplied image into `assets/images/` before referencing it, so the delivered page never depends on the user's machine layout.

### Stills and posters

`assets/images/scenes/*.png` holds the lossless master used as a generation input; the page loads the `.webp` poster that `scripts/make_posters.py` writes beside it. Compression never overwrites a master. An image project may reference a still in any web image format when no master exists.

## `prompts/video-manifest.json`

Video mode only. Image projects do not create this file.

```json
{
  "provider": "ark",
  "model": "doubao-seedance-2-5-260628",
  "duration": 4,
  "resolution": "720p",
  "ratio": "16:9",
  "target_width": 1280,
  "target_height": 720,
  "fps": 24,
  "crf": 20,
  "gop": 8,
  "generate_audio": false,
  "watermark": false,
  "conditioning_mode": "reference_images",
  "dives": [
    {
      "id": "01-opening",
      "prompt": "prompts/video/dives/01-opening.txt",
      "still": "assets/images/scenes/01-opening.png",
      "output": "assets/video/dives/01-opening.mp4"
    }
  ],
  "connectors": [
    {
      "id": "01-opening-to-next",
      "from": "01-opening",
      "to": "02-next",
      "prompt": "prompts/video/connectors/01-opening-to-next.txt",
      "output": "assets/video/connectors/01-opening-to-next.mp4"
    }
  ]
}
```

`conditioning_mode` values:

- `reference_images`: each local frame uses `role: reference_image`; works well for Seedance multimodal composition and explicit output ratios.
- `first_last`: a connector uses `first_frame` and `last_frame`; choose this when exact boundary anchoring matters more and the selected model supports it. Verify model-specific ratio restrictions.

The first/last frame cache is `assets/video/frames/{dive-id}-{first|last}.png`.

The manifest governs production and `content/story.json` governs what the page loads; `scripts/verify_media.py` checks the union of both, so a clip the page expects but the manifest never produces is reported instead of silently missing.
