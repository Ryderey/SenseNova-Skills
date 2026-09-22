# Stage reference: story draft and confirmation A

Read this file when the task is a new story or a major story revision. This turn's end is the shown draft plus a feedback question: image generation and edit calls stay at 0 until A is accepted or explicitly delegated.

## Establish the task and mode

Read the user's requirements, existing project files, supplied images, and any production records before planning. Record in `docs/production-spec.md` when a project is created or materially revised:

- purpose, audience, language, device targets, and chapter scale;
- factual, adapted, or fictional treatment, with source notes kept separate from display copy;
- chronological, thematic, geographic, or process-based structure;
- visual medium, palette, lighting, camera grammar, prohibited elements, and recurring identities;
- available images, required new stills, generation model, budget authority, and attempt limits;
- interaction mode: `collaborative` by default, or `direct-completion` when the user explicitly delegates the remaining creative decisions or says not to wait.

Preserve the continuous-stage skeleton: one fixed media stage and one ordered route. Use the user's already-stated decisions as decisions, not questions. When resuming, trust actual files and records only after checking that the referenced files still exist.

## Draft the story

For factual work, use primary or authoritative sources. For adapted or fictional work, state the major adaptation choices, especially the ending when multiple versions exist. Build a chapter sequence with one dominant visual event per chapter and stable, filename-safe IDs. Each chapter needs the actual display copy, a navigation label, title, optional subtitle, tags, expected still path, and, when useful, a `shot` block (`intent`, `framing`, `motionNote`). See [schemas.md](schemas.md).

Write the intended copy to `content/story.json` as early as possible. During drafting, a still may point to an expected path that does not exist yet; use `verify_media.py --allow-missing` only for offline assembly checks. Do not create placeholder images, run the formal storyboard export, or generate new stills to make an incomplete draft look finished.

## Show the draft and stop at confirmation A

In collaborative mode, show:

1. a short proposal covering audience, adaptation, ending, chapter count, visual direction, and recurring identities;
2. every chapter's actual text and dominant visual event, with current display number and stable ID available for internal mapping;
3. the still plan, expected image count, and the next representative scenes to be generated.

Then ask one focused question: accept this draft and direction, or name the chapter and change. This is confirmation A, and it is the end of this turn:

- the draft is shown as actual readable text, not as a file path or a "done" notice;
- the final reply carries the question and how to answer it;
- the turn ends there. Do not run image generation, editing, compression, export, or preview setup "while waiting", and do not queue them as background work;
- if the state file is in use (see [workflow.md](workflow.md)), record the phase as `awaiting_story_review` with the review-package identifier, and keep the image call count at 0.

A progress message, a file write, silence, timeout, a status question, or a host auto-continue event is not confirmation. If the user edits the draft, revise only the affected proposal and show it again without generating new images.

## What can cover A

- Explicit final copy covers the copy decisions it actually states; anything left open is still proposed and shown.
- A direct-completion instruction covers A and continues through the stages without manufacturing a wait, but still produces the draft and the representative-sample check as visible stage artifacts.
- "You arrange the story, but show me first" delegates the creative content, not the review: the draft is still shown and A still waits.
- A complete supplied image set covers only the image-production stages. Without final copy or an explicit delegation, the new story still waits for A.
- Do not ask the user to re-confirm a decision already made; record whether it was accepted, explicitly delegated, or merely proposed.
