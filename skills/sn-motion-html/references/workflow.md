# Production workflow

This file is the router and the rulebook for pauses, acceptance scope, and recovery. The default deliverable is an image story. Export its storyboard when requested, and produce a display poster only when requested. The image route needs no video tooling, video credentials, or public image host; the optional video route is the last section of [produce-and-deliver.md](produce-and-deliver.md).

## Stage routing

Read only what the current stage needs. The right column is this turn's completion condition: ending the turn there is finishing the task, not failing it.

| Current task | Required reading | This turn's end |
|---|---|---|
| New story or major story revision | [review-story.md](review-story.md), [schemas.md](schemas.md) | wait after the draft is shown |
| Valid A accepted | [review-visuals.md](review-visuals.md), [prompting.md](prompting.md), identity/style records | wait after the actual samples are shown |
| Valid B accepted | [produce-and-deliver.md](produce-and-deliver.md), [frontend.md](frontend.md) | deliver the finished project |
| Explicit local revision | the change scope plus the related stage file above | the authorized local-revision result |
| Video clips, on request | [produce-and-deliver.md](produce-and-deliver.md), [agnes-video.md](agnes-video.md) | the requested clips, normalized and verified |

Splitting the references reduces context noise; it is not permission isolation. If the host has already injected all of them into context, the split cannot hide the later stages — the stop rules below are what bounds the turn.

## Mode

`collaborative` is the default: the two confirmation points A (story) and B (representative stills) each end a turn. `direct-completion` applies only when the user explicitly delegates the remaining creative decisions or says not to wait; it cancels the user waits, not the stage artifacts or the sample self-check, and its waits can be covered by a recorded delegation — never by a fabricated per-image acceptance.

## A pause is an observable behavior

A pause is real only when all of these hold at once:

1. The actual draft or images are visibly shown — not just file paths, not a "completed" notice.
2. There is a clear question awaiting feedback and a simple way to reply.
3. The current Agent turn has ended, or the host's native wait-for-input mechanism has truly paused.
4. Nothing for the later stages is committed, queued, running in the background, or delegated.
5. No tool call that depends on the pending confirmation appears before the next relevant user event.

Without a dedicated wait tool, end the turn with the final reply. Never simulate waiting with an infinite sleep, file polling, a faked user event, or a self-wakeup. Some hosts automatically append "continue the task" after the model returns; that automatic event is not a user confirmation of a draft or a sample, and it must not advance the phase.

## Acceptance scope

- "You arrange the story, but show me first" is a content delegation, not a cancellation of the review: the draft is still shown and A still waits.
- "Continue" applies only to the most recent shown, still-valid review package. Accepting A does not accept samples that do not exist yet.
- "Change chapter 3, then continue" authorizes that explicit change and continuation; it does not waive future creative confirmations.
- A complete supplied image set saves only new image production; unsupplied copy or order still waits for A.
- Explicit final copy covers the copy decisions it states; a new open-ended visual choice is still handled at B.
- An accepted visual baseline can skip repeat samples; it does not excuse scenes that were never generated.
- Direct-completion mode still runs the representative-sample check; no entry point may read as "immediately batch-generate everything".
- Progress messages, file writes, silence, timeouts, status questions, Agent self-checks, completed plan items, and host auto-continue events are not confirmations.
- "Change chapter 3" or "I take back that yes" is a change request, not a pass: record it as a withdrawal and the earlier acceptance stops authorizing production at once, so nothing generated under it continues. Re-ask only the gate that moved.

## Smoke tests

The default environment check is the offline `sn-image-doctor`; it costs no image quota and proves nothing about remote authentication, so never claim a verified remote login from it. Do not add a real smoke generation as an environment check: after A, the first official representative sample doubles as the link verification and is reused as a final asset. A user-requested independent smoke test runs inside its stated authorization, is recorded with its purpose and count, and never advances A or B — a returned image, at any resolution, is not a user confirmation.

## Production records and review artifacts

`docs/production-spec.md` is a compact human/Agent record, not a second story database. Keep a current state block with:

- interaction mode and its evidence;
- current stage (`story-draft`, `representative-stills`, `complete-stills`, `assembly`, `delivered`, or `local-revision`); when the executor is in use, write its `phase` value beside this name so the two records cannot drift apart;
- revision number, waiting point, next action, chapter IDs involved;
- new-still plan: total, adopted, remaining, and extra identity images;
- generation limits and the location of the authorization record.

Also record the current display-number-to-stable-ID mapping and distinguish `user accepted`, `user delegated`, `Agent checked`, and `unreviewed`. `docs/image-qa.md` records accepted image sources, model/parameters, reference paths, and checks without inventing provider fields. An optional `docs/review/story-draft.md` is a read-only review copy derived from `story.json`; edit `story.json` first. Do not put workflow state in the frontend runtime.

When the machine state file `.motion-state/review.json` is in use (see [schemas.md](schemas.md)), it owns the phase, review-package identifiers, approvals, and operation records; `docs/production-spec.md` summarizes or points at it, and the two files never decide the current phase independently. `content/story.json` remains the only source of story content.

## Resume and local revision

When resuming, read the state block, the relevant story chapters, image QA, and actual files before continuing. A generated but not-yet-shown representative still is shown first rather than regenerated. A missing file invalidates the stale record and is reported; it does not silently trigger a full restart. An old project without a state block gets the minimum record needed for the current task, never a fabricated acceptance. A missing state file never means "already accepted".

For a local revision, map the user's current display number or title to the stable chapter ID. State the affected scope in one sentence, retain unrelated accepted assets, update the source artifact first, then regenerate only required derivatives: WebP, contact sheet, and storyboard when applicable. A clear request to fix copy or replace one image is authorization for that scope and does not restart the two confirmation points. Reconfirm only when the change introduces a new creative choice, such as an open-ended scene change or a global visual direction. Waiting states do not block authorized local revisions: copy can change while waiting for A, and a named sample can be revised while waiting for B — that authorization is scoped and does not release other scenes.

### Change matrix

| User change | Update | Usually retain | Confirmation |
|---|---|---|---|
| Typo, shorter copy, same event | Chapter copy, exports, browser check | Images, identities, style, other chapters | Direct when explicitly requested |
| Chapter event or key object | Copy, shot, image and affected follow-on scenes | Unrelated chapters | Confirm only the new choice |
| One image's expression, composition, or detail | That image, its basis, WebP, overview, relevant export | Other accepted images and copy | Direct when clear |
| Recurring character appearance | Identity record and every affected image | Images without that identity | Show affected chapter IDs and follow scope |
| Global visual style | Style basis, representative samples, affected stills | Accepted copy and chapter structure | New visual confirmation |
| Reorder/add/remove chapters | Order, number mapping, affected transitions, assets, exports | Stable IDs that still apply | Show changed structure/copy |
| Layout or responsive issue | Layout, copy position/crop, browser check | Story meaning and usable images | Direct when clear; replace images only if necessary |

Do not claim that a local change touches one file when real dependencies extend further. Conversely, do not regenerate unrelated scenes merely to make them look consistent. `make_posters.py` may recompress the whole PNG directory deterministically; that is not a reason for new image-model calls.

## Cost and waiting discipline

Two confirmations add a little text and waiting cost but expose story and visual errors before the most expensive work. Do not promise a fixed token or image-cost saving. If usage is available, record text input/output, image calls, local processing time, user replies, and total wait separately. Word count is not token usage, and image cost is not text cost.

Keep the first review complete, show only changed chapters for local revisions, reuse accepted references, and do not generate unrequested character boards, posters, videos, or alternate full style sets. Host rules may require a different wait behavior; preserve visible stage artifacts and report the deviation honestly.

## Program checks and their boundary

When `scripts/motion_stage.py` is present in the project, it is the controlled entry for story image calls: it reads `.motion-state/review.json`, checks the phase and approval scope, validates every target ID, and only then calls the existing SenseNova runner. Its guarantee is program-level: it refuses out-of-scope calls at the normal entry before any provider request. Four of its rules exist because the obvious shortcut is wrong:

- generation targets the lossless master and never resends an image merely because a WebP page copy is missing — while a page copy older than its master still counts as needing a refresh, so a replacement is not "delivered" while the page would show the superseded picture;
- every attempt is recorded with its quota before the request is sent, so a killed run resumes as an in-doubt call that must be reconciled rather than silently bought twice;
- the lock is one the operating system grants and releases with the process, so a second run is refused while the first is alive and a crash leaves nothing to take over — age and file contents never decide who may run;
- the newest decision on a package is the one that stands — a change request withdraws an earlier acceptance — and a revision covers exactly the change it was given on, style basis and meta included, staying open until every chapter it authorized has really been produced (a file that landed before an interruption counts as produced, not as still owed).

It is not an unblockable host gate — an Agent with arbitrary shell access, the ability to edit the state file, or direct credentials can still bypass it, and a decision the model records itself is only `agent-recorded`, not proof of a real user event. Report this boundary honestly instead of describing the executor as enforcement.
