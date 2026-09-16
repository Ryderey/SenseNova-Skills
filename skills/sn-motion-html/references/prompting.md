# Prompting patterns

Start from one of the coordinated presets in [style-presets.md](style-presets.md), or replace it with a user-defined art direction. The initializer writes the chosen image block to `prompts/style-preamble.txt`; a video project additionally writes the motion block to `prompts/style-motion.txt`, which an image story never uses.

## Generating stills

Still generation reuses the existing SenseNova runtime instead of a second client. Resolve the sibling skill and pass absolute paths:

```bash
"<absolute PYTHON path>" "<absolute BASE_SKILL_DIR>/scripts/sn_agent_runner.py" sn-image-generate \
  --prompt-path "<absolute task temporary directory>/chapter-03.txt" \
  --image-size 2k \
  --aspect-ratio 16:9 \
  --save-path "<absolute PROJECT_ROOT>/assets/images/scenes/03-chapter.png" \
  --output-format json
```

- Prefer `--prompt-path` over `--prompt` for anything long or multilingual, so shell quoting cannot alter the text.
- Keep the assembled prompt file in the per-task system temporary directory, not in the project.
- Use native editing (`sn-image-edit`) with a reference image for recurring subjects rather than re-describing them from scratch; editing never falls back to a model without image input.
- Record the model actually used, whether a fallback occurred, and which candidate was accepted. After a fallback, re-check style consistency instead of assuming it held.

## Text belongs to the page

Generate images without embedded copy, and let HTML carry the words. Body paragraphs, titles, navigation labels, source labels, and buttons stay in `content/story.json` so they remain editable, translatable, and legible at every viewport. Chinese text baked into pixels is hard to correct afterwards, so keep it out of the image unless the design genuinely requires in-scene lettering — and then treat it as a deliberate, reviewed exception.

## Style preamble

Create one reusable block containing:

```text
MEDIUM: [photography / illustration / clay diorama / collage / ...]
PALETTE: [named colors and contrast]
MATERIALS: [surface and texture]
CAMERA: [lens, angle, distance, projection]
LIGHT: [direction, softness, time or studio setup]
COMPOSITION: landscape frame, safe central crop, readable depth layers
CONTINUITY: use supplied identity references without redesign
EXCLUDE: text, letters, numbers, logo, watermark, unintended modern objects
```

Keep style separate from subject instructions so every scene receives an identical style block.

## Identity block

For every recurring person, creature, product, or vehicle, lock:

- apparent age or form and body proportions;
- face or silhouette geometry;
- dominant colors and materials;
- signature garment, marking, or object;
- allowed scene-specific wear or state changes;
- features that must never change.

Generate a neutral reference sheet before narrative scenes. In scene prompts, name only the references that actually appear; too many unrelated references dilute identity control.

## Scene still

```text
[STYLE PREAMBLE]
[RELEVANT IDENTITY BLOCKS]

Create chapter [ID]: [visual event].
Foreground: [anchor detail].
Midground: [main action and identities].
Background: [place, weather, destination].
Story facts that must be readable: [2-4 items].
Keep the main subjects inside the central safe area for a 16:9 web crop.
Static frozen moment; no motion blur; no embedded text.
```

One still communicates one dominant event. A montage is acceptable only when the art direction explicitly calls for a miniature world or a multi-event tableau.

## Framing the still against the copy

The page lays a copy block over part of every still, so compose for the space the words will use. Decide the copy position and the composition together rather than after the fact:

- For `left` or `right`, keep the subject on the opposite side and leave readable negative space on the copy side. Avoid a busy high-frequency background exactly where the block lands.
- For `bottom`, keep the horizon and the subject's head in the upper two thirds.
- For `center`, use a sparse frame with a calm area behind the title, and expect only short copy.
- Keep the subject off the extreme edges: the stage crops with `object-fit: cover`, and portrait phones crop the sides hardest.

Write the framing you intend into the chapter's optional `shot.framing`, and check it against the still you actually accepted. A framing note that describes a picture nobody has is worse than no note: the storyboard would then state something false. The storyboard renders `intent`, `framing`, and `motionNote` verbatim, so keep each one short and true to the accepted image.

## Describing movement without producing it

`shot.motionNote` records the movement a future filming or animation pass would use — a slow push, a lateral drift, a hold on the hands. Write it as an intention:

- Describe what would move and roughly how, not a finished shot.
- Never phrase it as though footage exists, and never let it appear in a delivery summary as a produced result.
- It is also useful input later: it is the sentence a future video pass would start from, and it costs nothing now.

Video prompts for the frozen later phase are kept in [seedance.md](seedance.md).
