# Agnes Video 2.5 Flash (video path)

Status: **the request contract below is verified against the live API; the project pipeline that drives it is not built yet.** Treat this as the integration reference and as the current boundary of the video path.

Last verified: 2026-09-17, two real generations on the development machine.

## Where the client lives

The client is the bundled zero-dependency CLI of the sibling Agnes media skill, not a second HTTP client inside this skill:

- `<absolute AGNES_SKILL_DIR>/scripts/agnes_media.py`
- Python 3.10+; run it with the same interpreter that passes `sn-image-doctor`.
- Reads `AGNES_API_KEY` from the environment. Never pass the key on the command line or write it into a project.
- `AGNES_OUTPUT_DIR` chooses where media is saved; otherwise it writes under `outputs/images` and `outputs/videos` in the calling directory. Set it to the task's system-temporary directory so provider output never lands in the delivered project.
- Exit codes: `0` success, `2` correctable input error, `1` provider, network, or runtime failure.

Inspect `<cli> --help` and `<cli> video-generate --help` before use; the CLI help is authoritative for flags.

| Command | Use |
|---|---|
| `video-generate` | Submit, poll, and download in one call. The default for this workflow. |
| `video-submit` | Submit only, for asynchronous work |
| `video-status VIDEO_ID` / `video-wait VIDEO_ID` | Check or resume a submitted job |
| `image-generate` | Only when a public image URL is needed as a video input; it returns one |

## Model and modes

Pass the model explicitly: `--model agnes-video-2.5-flash`. The CLI's own default is `agnes-video-v2.0`; never let the selected Flash model be replaced by it, and never retry a failed Flash request on 2.0.

| Mode | Use when | Options |
|---|---|---|
| `text` | No media input | `--mode text` |
| `keyframe` | The shot starts from, ends at, or spans a still | `--mode keyframe --first-frame URL [--last-frame URL]` |
| `reference` | Identity, style, or rhythm comes from supplied media | `--mode reference --reference-image URL` (repeated), `--reference-audio URL` |

Flash constraints, all verified in the client source:

- `--duration` must be a whole number of seconds from 4 to 12.
- `--resolution` must be `720P`.
- `--aspect-ratio` must be one of `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`.
- Keyframe and reference inputs cannot be combined in one request.
- At most five reference images. Images and audio only: Flash rejects video references.
- `--image`, `--frame-rate`, `--negative-prompt`, `--num-inference-steps`, and `--extra-body` do not apply and are rejected.

## How a clip gets its media

**Every media input must be a public HTTPS URL.** Local paths and Data URIs are refused for Flash video, so a project's stills cannot be passed directly: they live on the user's disk. Each clip therefore declares an `anchor_mode`:

| Mode | What it sends | Use it when |
|---|---|---|
| `generate` | An anchor image created through Agnes first, whose own public URL becomes the clip's first frame | The default for a dive. Needs no host |
| `reference` | Public reference images that guide identity, style, and place | The default for a connector: it borrows the two chapters' anchor images |
| `url` | `first_frame` and/or `last_frame` as public URLs the user controls | The user hosts the exact boundary frames they want anchored |
| `text` | Nothing at all | A clip composed only from its prompt; it will not match the page still |

### Why a connector uses `reference`

A connector's natural anchors are its neighbours' boundary frames — the last frame of one dive and the first frame of the next. Both are local extracts, so neither has a URL. But the *first frame of the next dive is already public*: it is that dive's anchor image, and `scripts/agnes_video.py` records it in `.motion-state/video-anchors.json` when it generates the dive. A connector in `reference` mode borrows both chapters' recorded anchors, so it starts in one chapter's visual world and lands in the other's, with no hosting and no re-rendering of anything.

Both anchors are resolved when the connector runs, not when the plan is built, so a single invocation can generate the dives and then their connectors. A dry run reports either the resolved URLs or a note that the anchors are not recorded yet.

Explicit `reference_images` (up to five) override the borrowed pair, and `url` mode still accepts a hosted exact frame when the user wants one end of a seam pinned precisely.

### Re-hosting a local frame does not work well

Turning a local frame into a public URL through an image call is possible — image commands accept local paths and return provider URLs — and it was measured on a real boundary frame:

| Prompt | Returned | Mean pixel difference from the source |
|---|---|---|
| "Return this image unchanged" | 1024×1024 | 27.7/255 (11%) |
| "Increase resolution and clarity, change nothing else", `--size 2K --ratio 16:9` | 2624×1472, exact 16:9 | 42.4/255 (17%) |

Two conclusions. The canvas problem is solvable by stating `--size` and `--ratio` (both are accepted even by `image-edit`). But these endpoints are generative: they redraw the frame rather than copy it, and asking for more clarity makes the deviation *worse* because it invites re-rendered texture. The result is a plausible twin of the frame, not the frame — acceptable where the runtime dissolves the seam, not acceptable as a true boundary. Prefer `reference`; use this route only if you need a URL and have no other source.

Never publish a user's images to a public host without asking: that is an outward-facing action, and cached copies outlive deletion.

## Prompt shape

Follow the shared Agnes Video 2.5 prompting order: subject and scene, then action and change, then camera language, then visual style, then sound and rhythm when relevant, then the traits that must stay consistent. Keep it concise enough for the requested duration, and do not invent shots, subjects, or events the story does not contain.

- `text`: describe the scene and the motion; include sound only when it belongs to the request.
- `keyframe`: describe the movement and camera change away from (or between) the supplied frames, plus what must remain consistent. The first frame is honored: a verified run reproduced its source composition to within a mean pixel difference of 7.7/255.
- `reference`: state what each asset contributes, keep `<Picture N>` / `<Audio N>` markers exact, and number them from 1 in input order.

A chapter's `shot.motionNote` is the natural first draft of the prompt, and `shot.framing` states what must stay consistent.

## Provider output is not the deliverable

Measured behavior, which is why normalization is mandatory rather than optional:

| Run | Requested | Returned |
|---|---|---|
| `text`, 4 s, 720P, 16:9 | 1280×720, 4.000 s | 1280×720, 24 fps, 4.458 s, 107 frames |
| `keyframe`, 4 s, 720P, 16:9 | 1280×720, 4.000 s | **1280×704**, 24 fps, 4.458 s, 107 frames |

Wall-clock time was about 197 seconds for the first 4-second clip (submit, poll, download).

Normalize every downloaded clip locally before it enters a project:

```bash
ffmpeg -v error -y -i "<provider clip>" -t <exact seconds> \
  -vf "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=24" \
  -c:v libx264 -profile:v high -pix_fmt yuv420p -g 8 -an -movflags +faststart \
  "<project>/assets/video/dives/<id>.mp4"
```

Verified result: exactly 4.000 s, 1280×720, 24 fps, 96 frames, and `scripts/verify_media.py` reports `OK` for the normalized clip in a real video project. `scale` with `force_original_aspect_ratio=increase` followed by `crop` removes the provider's few-pixel size drift without leaving letterbox bars, and the story page crops to fill anyway.

The manifest's single `duration` applies to dives and connectors alike, so normalize both to that same length; a connector simply has more frames available across its shorter scroll span.

Failure handling: polling retries HTTP 429 and 503. On timeout, keep the reported `video_id` so the job can be resumed with `video-status` or `video-wait` instead of being resubmitted. Do not resubmit blindly: a second submit is a second billed job.
