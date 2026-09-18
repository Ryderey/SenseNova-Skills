# Agnes video (video path)

Status: **the contracts below are verified against the live API and driven by `scripts/agnes_video.py`.** Treat this as the integration reference for the video path.

Last verified: 2026-09-17, real generations on the development machine with both models.

## Where the client lives

The client is the bundled zero-dependency CLI of the sibling Agnes media skill, not a second HTTP client inside this skill:

- `<absolute AGNES_SKILL_DIR>/scripts/agnes_media.py`
- Python 3.10+; run it with the same interpreter that passes `sn-image-doctor`.
- Reads `AGNES_API_KEY` from the process environment. The pipeline also loads scoped provider settings from `<PROJECT_ROOT>/.env` using the image runtime's `python-dotenv` dependency; existing process variables win. Values are literal (no variable interpolation or shell execution), and unrelated environment settings are ignored. Never pass keys on the command line or commit `.env`.
- `AGNES_OUTPUT_DIR` chooses where media is saved; otherwise it writes under `outputs/images` and `outputs/videos` in the calling directory. Set it to the task's system-temporary directory so provider output never lands in the delivered project.
- Exit codes: `0` success, `2` correctable input error, `1` provider, network, or runtime failure.

Inspect `<cli> --help` and `<cli> video-generate --help` before use; the CLI help is authoritative for flags.

Pass `--agnes-cli <absolute path to agnes_media.py>` and `--image-cli <absolute path to sn_agent_runner.py>` to the pipeline, or configure `AGNES_SKILL_DIR` and `SN_IMAGE_BASE_DIR`. The repository copy also finds the sibling image runner automatically. An image runner is required only for selected `generate` clips.

| Command | Use |
|---|---|
| `video-generate` | Submit, poll, and download in one call. The default for this workflow. |
| `video-submit` | Submit only, for asynchronous work |
| `video-status VIDEO_ID` / `video-wait VIDEO_ID` | Check or resume a submitted job |

**Video only.** No image work belongs to this provider: anchor images come from the project's own SenseNova skill, which is also what makes their public URLs available. Never call this client's image commands from this skill.

## Models

Pass the model explicitly in `prompts/video-manifest.json`. `scripts/agnes_video.py` refuses an unknown model before calling the provider, and never substitutes one model for another.

| | `agnes-video-v2.0` | `agnes-video-2.5-flash` |
|---|---|---|
| Resolution | Any short side (`1080p`) or explicit `WxH` | `720P` only |
| Duration | Frame-aligned: `8n+1` frames, at most 441 (about 18s at 24fps) | Whole seconds, 4 to 12 |
| One still as the start | `--mode ti2vid --image URL` | `--mode keyframe --first-frame URL` |
| Start and end stills | `--mode keyframes --extra-body '{"image":["URL1","URL2"]}'` | `--mode keyframe --first-frame A --last-frame B` |
| Reference images or audio | Not supported | `--mode reference --reference-image URL` (up to five) |
| Other flags | `--frame-rate`, `--negative-prompt`, `--num-inference-steps`, `--extra-body` | Rejects all four except through its named frame options |

**Use v2.0 when the page should show a high-definition clip** — it is the default here, and a full-viewport web stage makes 720P visibly soft. Use Flash when a clip must be guided by reference images or reference audio, or when only a last frame is available to anchor on.

Verified resolutions and timings on the development machine, 4-second 16:9 clips:

| Model | Requested | Returned | Wall clock |
|---|---|---|---|
| `agnes-video-v2.0` | 1920×1080 (`--resolution 1080p`) | **1920×1088**, 24 fps, 97 frames, 4.042 s | 113 s |
| `agnes-video-2.5-flash` | 1280×720 (`720P`) | 1280×720, 24 fps, 107 frames, 4.458 s | 197 s |
| `agnes-video-2.5-flash` | 1280×720 (`720P`), keyframed | **1280×704**, 24 fps, 107 frames, 4.458 s | ~140 s |

The provider canvas is not the requested canvas on either model: it pads the short side to a multiple it likes. Normalization crops it back, so the delivered clip is exactly the manifest's target.

## Where the anchor image comes from

**SenseNova handles image generation, editing, repair, enhancement, and compositing; Agnes only generates video.** `scripts/agnes_video.py` calls the `sn-image-base` runner, pins `SN_IMAGE_GEN_MODEL_TYPE=sensenova` and `--model sensenova-u1.5-lite --no-fallback`, and checks the reported model before handing its URL to Agnes. Image-to-image changes use SenseNova `sn-image-edit`; the video pipeline does not edit images itself. Local encoding and frame extraction use the project tools. The Agnes call wrapper refuses image commands.

The transport between them is the image endpoint's own URL response. SenseNova can answer a generation with a URL instead of Base64 (`--response-format url`), and its runner reports that address as `provider_url`. Measured on a real call: an unauthenticated `GET` returned `200 image/png`, and the address is pre-signed with a 24-hour window — long enough for the video job, short enough that the pipeline records when each anchor was saved and refuses to hand over one that is older than 20 hours (`ANCHOR_MAX_AGE_HOURS`). Refresh an expired anchor by re-running that dive with `--force`.

Anchor size comes from the manifest's `anchor_image_size` (default `2k`). The anchor only has to feed the video model: the page still is derived from the clip's own first frame at the manifest's delivery target, so the 4K still default used by image projects would be wasted here.

## How a clip gets its media

**Every media input must be a public HTTPS URL.** Local paths and Data URIs are refused for video on both models, so a project's stills cannot be passed directly: they live on the user's disk. Each clip therefore declares an `anchor_mode`:

| Mode | What it sends | Use it when |
|---|---|---|
| `generate` | An anchor image created through the project's SenseNova skill first, whose own public URL becomes the clip's first frame | The default for a dive. Needs no host |
| `reference` | Public images that carry identity, style, and place: on v2.0 they become the two boundaries of a keyframes transition, on Flash they are reference images | The default for a connector: it borrows the two chapters' anchor images |
| `url` | `first_frame` and/or `last_frame` as public URLs the user controls | The user hosts the exact boundary frames they want anchored. Pinning only the last frame needs Flash |

Every clip must explicitly declare one of these three modes. Missing modes and `text` are rejected before generation. An unavailable URL blocks that clip rather than changing its conditioning.

### Why a connector uses `reference`

A connector's natural anchors are its neighbours' boundary frames — the last frame of one dive and the first frame of the next. Both are local extracts, so neither has a URL. But the *first frame of the next dive is already public*: it is that dive's anchor image, and `scripts/agnes_video.py` records it in `.motion-state/video-anchors.json` when it generates the dive. A connector in `reference` mode borrows both chapters' recorded anchors, so it starts in one chapter's visual world and lands in the other's, with no hosting and no re-rendering of anything.

Both anchors are resolved when the connector runs, not when the plan is built, so a single invocation can generate the dives and then their connectors. A dry run reports either the resolved URLs or a note that the anchors are not recorded yet.

Explicit `reference_images` override the borrowed pair (one or two for v2.0, up to five for Flash). The borrowed pair contains chapter anchors, not the previous clip's actual last frame; inspect the seam visually rather than claiming exact frame continuity. Use `url` for exact hosted boundary frames.

### Local frames and public URLs

A SenseNova edit may change image content, so it is not lossless hosting. When an image needs editing, use `sn-image-edit --response-format url` and inspect the edited image before making it a keyframe. When the exact existing pixels must be preserved, use a user-authorized host or an existing provider URL. Do not use Agnes image commands to obtain URLs.

Never publish a user's images to a public host without asking: that is an outward-facing action, and cached copies outlive deletion.

## Prompt shape

Follow the shared Agnes Video 2.5 prompting order: subject and scene, then action and change, then camera language, then visual style, then sound and rhythm when relevant, then the traits that must stay consistent. Keep it concise enough for the requested duration, and do not invent shots, subjects, or events the story does not contain.

- `keyframe`: describe the movement and camera change away from (or between) the supplied frames, plus what must remain consistent. The first frame is honored: a verified run reproduced its source composition to within a mean pixel difference of 7.7/255.
- `reference`: state what each asset contributes, keep `<Picture N>` / `<Audio N>` markers exact, and number them from 1 in input order.

A chapter's `shot.motionNote` is the natural first draft of the prompt, and `shot.framing` states what must stay consistent.

## Provider output is not the deliverable

See the measured table above: the provider returns neither the requested canvas nor the requested duration, so normalization is mandatory rather than optional. Normalize every downloaded clip locally before it enters a project:

```bash
ffmpeg -v error -y -i "<provider clip>" -t <exact seconds> \
  -vf "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=24" \
  -c:v libx264 -profile:v high -pix_fmt yuv420p -g 8 -an -movflags +faststart \
  "<project>/assets/video/dives/<id>.mp4"
```

Verified result: exactly 4.000 s at the manifest's target, 24 fps, 96 frames, and `scripts/verify_media.py` reports `OK` for the normalized clip in a real video project. `scale` with `force_original_aspect_ratio=increase` followed by `crop` removes the provider's few-pixel canvas drift (1920×1088 → 1920×1080, 1280×704 → 1280×720) without leaving letterbox bars, and the story page crops to fill anyway.

### Quality and payload

The manifest's `crf` (0–51, default 23) is the one knob that trades quality for page weight, and high-definition clips make it worth setting. Measured on a real 1080p project, re-encoding the same normalized clips:

| Clip | At crf 23 | crf 26 | crf 30 |
|---|---|---|---|
| Transition with camera movement | 11.0 MB | 7.6 MB (68%) | 4.1 MB (37%) |
| Scene clip | 3.9 MB | 2.9 MB (73%) | 1.9 MB (48%) |

A transition carries the most motion and dominates the payload, so a project that streams over a slow connection should raise `crf` to about 26, or 30 if softness in fine detail is acceptable. The page loads clips lazily, so only the clips near the reader's position are fetched.

The manifest's single `duration` applies to dives and connectors alike, so normalize both to that same length; a connector simply has more frames available across its shorter scroll span.

Failure handling: polling retries HTTP 429 and 503. On timeout, keep the reported `video_id` so the job can be resumed with `video-status` or `video-wait` instead of being resubmitted. Do not resubmit blindly: a second submit is a second billed job.
