# Seedance integration (later-phase Ark video path)

**Frozen: not part of the current phase.** This is a reference for a future change, not a current capability of the skill. No first-phase deliverable reads this file, and nothing here may be presented as an already delivered or already verified video result. An image story never calls it, and no image-mode check requires its tooling or credentials.

Reopen it only when a real need for subject motion or generated transitions is established, and then as a separate change with its own model choice, cost basis, and authorization.

This describes the Ark/Seedance request contract used by `scripts/seedance_pipeline.py`. Use the current official model documentation when model IDs or supported parameters may have changed. The script targets the Ark asynchronous content-generation API.

## Motion prompt patterns

These are the prompt shapes a future pass would start from. They exist so the work is not re-derived later; they are not a current step.

Dive motion — restrained movement that preserves the source image:

```text
Use image 1 as the sole visual reference. Preserve identities, layout, palette, and materials.
Four-second continuous shot. [Small environmental motion]. [One subtle character action].
Camera [locked / slow push / shallow orbit]. No cut, no redesign, no new character,
no text, no logo, no sudden lighting change. End on a stable readable frame.
```

Connector motion — with two reference images, assign the semantic order explicitly even when both use `reference_image`:

```text
Image 1 is the departure boundary; image 2 is the destination boundary.
Create a continuous journey from [departure] to [destination]. Begin with the visual
language of image 1, travel via [sea / sky / tunnel / map / material transformation],
and settle into image 2. Preserve recurring identities and palette. No cut, no text,
no extra subject, no violent morph, no camera roll. Stable first and last moments.
```

A video prompt describes change over time; it does not repeat the still's description. The chapter's `shot.motionNote` is the natural first draft of it.

## Request flow

- Base URL: `https://ark.cn-beijing.volces.com/api/v3`
- Create: `POST /contents/generations/tasks`
- Poll: `GET /contents/generations/tasks/{id}`
- Terminal states: `succeeded`, `failed`, `cancelled`, and sometimes `expired`
- Download `content.video_url` immediately after success; provider URLs are temporary.

The default content array is a text prompt followed by one or two local images encoded as data URLs. `reference_images` sends each with `role: reference_image`. `first_last` sends connector frames with `first_frame` and `last_frame` roles.

## Configuration

Keep these in the project manifest rather than the script:

- model ID;
- requested duration, resolution, and ratio;
- audio and watermark policy;
- conditioning mode;
- dive and connector records.

Keep credentials in `.env`:

```dotenv
ARK_API_KEY=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
SEEDANCE_MODEL=
```

`SEEDANCE_MODEL` is an optional runtime override. Never send a key to the frontend or include it in task metadata.

## Concurrency and recovery

Use a bounded thread pool. Run dives first; a connector cannot begin until both adjacent dive boundary frames exist. Within each phase, clips are independent and can run concurrently. Start with four workers unless the account's documented quota suggests another value.

Skip non-empty final outputs unless `--force` is explicit. Save task IDs and sanitized request metadata so interrupted runs can be audited. Do not record the Authorization header, data URLs, or secrets.

Known defect to fix before this path is ever enabled: the current full-cycle retry can create duplicate billable tasks. See the integration plan's frozen-work note; do not enable the path without addressing it.

Retry transient task or network failures at most once by default. Do not retry `ModelNotOpen`, authentication, access, billing, or invalid-parameter failures without a configuration change.

## Normalization

For interactive frame scrubbing, provider output is an input, not the final web asset. Normalize with FFmpeg to a fixed canvas, constant frame rate, exact duration, H.264 `yuv420p`, short GOP, no audio when silent, and `+faststart`. Extract boundary frames from the normalized dives, not from the source stills.

Official references:

- https://www.volcengine.com/docs/82379/1520757?lang=zh
- https://www.volcengine.com/docs/82379/1521309?lang=zh
