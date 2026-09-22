# Stage reference: representative stills and confirmation B

Read this file when A has been accepted or explicitly delegated. This turn's end is the shown samples plus a feedback question: generate only the whitelisted representative stills, and do not start the remaining production.

## Check capability before submitting

Run the offline `sn-image-doctor` check first; it consumes no image quota and proves nothing about remote authentication, so do not claim a verified remote login from it. Do not add a real smoke generation as an environment check: the first official representative sample doubles as the link verification, and a successful sample is reused as a final asset. If the user independently asks for a real smoke test, run it inside that authorization, record its purpose and count separately, and do not let it advance A or B — a returned image is never a user confirmation.

## Choose the smallest useful sample set

Use supplied images directly when they meet the requirement. A complete usable image set plus explicit final copy can cover the image stages with zero new image-model calls; record that decision instead of generating a preview set.

Otherwise generate only the smallest useful consistency gate: usually one image for a simple story, or two or three when characters, settings, or emotional range create separate risks. Choose scenes that test identity, composition, and the most important visual decision; do not mechanically pad the set to opening/middle/ending. The exact sample list — chapter IDs and any necessary character reference images — is decided here and shown with the A review package, so the user sees what will be generated before it is generated. A newly added character reference counts in that list and in the call plan; it is not a hidden side path.

Record the authorized model budget and attempt limit before generation. A free-only request requires evidence that the selected account and operation are free or covered by a free quota. If that cannot be verified, complete offline preparation and report the blocker before submitting. A successful response or dry run does not prove zero cost.

## Generate and stop at confirmation B

Generate only the whitelisted samples. When the stage executor is present (`scripts/motion_stage.py`, see [workflow.md](workflow.md)), route the calls through it: it rejects a request whose targets fall outside the A-approved sample list before any provider call. A batch that mixes approved and unapproved targets is rejected whole, with zero real calls.

Display the actual image files, their chapter numbers, and a few concrete checks. The accepted representative stills become the final assets; never generate a preview set and then regenerate the same scenes unconditionally.

In collaborative mode, ask one focused question: keep this visual direction and continue, or name the visual change. This is confirmation B, and it is the end of this turn:

- the samples are shown as actual images, not as paths or "completed" text;
- the final reply carries the question and how to answer it;
- the turn ends there, with no committed, queued, background, or delegated requests for the remaining scenes;
- if the state file is in use, record the phase as `awaiting_visual_review` with the visual review-package identifier.

Direct-completion mode still shows the draft summary and representative images, but continues after the Agent's checks without manufacturing a wait. When existing images or an already accepted visual baseline are sufficient, skip new sample generation and record why. Direct completion never removes the sample self-check.

## Revising a sample before B

While B is pending, the user can authorize a change to a named sample. That is a bounded decision, not a release for the rest of the story: record it as a scoped revision, regenerate only the named sample, and then rebuild and re-show the visual package. Confirmation A still stands, so the draft is not asked about again — but the old sample acceptance is gone with the old images, and production stays closed until B is given on what is actually on screen now.

## What can cover B

- "Continue" applies only to the most recent shown, still-valid review package: accepting A does not accept samples that do not exist yet.
- "Change the coat, then continue" authorizes that explicit change and continuation; a new open-ended visual choice requires another focused confirmation for the affected scope.
- An accepted visual baseline can skip repeat samples; it does not excuse scenes that were never generated.
- A user-provided complete image set saves new image production only; missing copy or order still goes through A.
