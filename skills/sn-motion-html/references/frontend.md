# Motion frontend

## Non-negotiable structure

Whatever the media mode, the experience is one staged route:

```text
scene 0 → connector 0 → scene 1 → connector 1 → … → final scene
```

Render every media segment as an absolutely stacked child of one fixed, full-viewport stage. A single document-height track supplies the route distance. Do not turn scenes into separate cards, articles, or independently sticky media blocks. In image mode the connector segments do not exist, so the route is a plain scene sequence; the stage, the route, the copy layer, and the navigation stay identical.

## The two modes

| | `images` | `video` |
|---|---|---|
| Media element | `<img>` poster only | `<img>` poster replaced by `<video>` once a decoded frame paints |
| Progress mapping | Scroll position drives opacity cross-fades, per-scene pacing, and a restrained poster scale | Scroll position additionally drives each clip's `currentTime`, forward and reverse |
| Continuous work | None between scroll events; no animation loop runs | A coalesced seek loop over the visible, ready segments |
| Failure | A failed image leaves the labelled fallback panel visible | A failed clip leaves the poster visible and never blanks the stage |

Image mode must not fetch, decode, or seek a clip. In video mode, load nearby clips as Blob URLs so seeking is reliable, retain the poster until a decoded frame paints, and release a clip and its object URL once it leaves the active window.

## Reduced motion

Under `prefers-reduced-motion`, do not load video at all and disable the still drift. Keep the stills, the copy, the navigation, and the cross-dissolves, because those carry the story. Reduced motion is a supported way to read the story, not a degraded state; it must never be reported as a media failure.

Video failure and reduced motion are different states: the first is a degradation to report, the second is an intended path.

A machine with operating-system animations switched off reports `reduce`, which removes every designed motion effect. Reviewers who cannot change that setting can append `?motion=full` to the preview URL to force the full-motion path, or `?motion=reduce` to force the reduced one. With no parameter the operating system's preference always wins, so this stays a review aid and never a delivery setting.

## The transition itself

Two things make the seam read as one continuous move rather than a slide change, and both are easy to undo by accident:

- The arriving scene dissolves in **on top of** a departing scene that stays fully opaque underneath. Do not ramp both layers down together: alpha-compositing two half-transparent layers lets the dark stage bleed through, and the frame visibly dips toward black at the midpoint of every transition.
- Image mode needs a much longer window than video mode. A frame-matched video seam only has to hide the join; two unrelated stills have to dissolve. Size the window from `meta.crossfade` rather than reusing the video constant, and check the result by scrolling through a seam slowly instead of jumping to it.

The copy is timed to clear before the image settles: a scene's copy finishes fading out as its segment ends and the next scene's copy only starts when its own segment begins, so two copy blocks are never on screen at once and neither fights the dissolve.

## Interface presets

All presets share the exact same stage and timeline. They change only page chrome and copy composition:

- **Folio (`ui: folio`)** — offset editorial header, unboxed transparent copy, fine rules, restrained vertical chapter index.
- **Caption (`ui: caption`)** — quiet centered header, wide transparent lower-third composition, minimal scene navigation.
- **Graphic (`ui: graphic`)** — compact block header, transparent outlined copy, assertive labels and progress marks.

Treat these as starting points. Subject-specific changes may reshape the panel, header, typography, and navigation, but must not alter the staged media topology. Do not clone distinctive decorative elements from a reference; use new geometry, spacing, materials, and type hierarchy while preserving the underlying interaction.

## Copy placement

Each scene has one complete static copy block. Do not rotate paragraphs within a scene. Set `copyPosition` per scene:

- `left` or `right` uses available negative space beside the focal subject;
- `bottom` creates a wide lower-third panel;
- `center` is reserved for sparse title-like scenes and must retain image readability.

Keep a scene's copy position stable for its whole range. Hide copy during a connector rather than switching paragraphs inside it, and show the next scene's copy only when its own segment begins.

Copy blocks are transparent by default: no opaque rectangle, frosted card, or large drop shadow. Protect legibility with a soft localized gradient that has no visible edge, plus restrained text shadow or fine rules. A solid card is an explicit exception for a user-requested brand language, not a default. Text must stay semantic — headings, paragraphs, lists, and links, not images of text.

## Header, navigation, and accessibility

The header stays fixed but visually quiet. It may contain the title, a compact source link, and overall progress. Navigation targets the beginning of each scene's route range, is keyboard-operable, and updates `aria-current` without seeking a video independently.

- Only the active chapter's copy may be reached by assistive technology; inactive chapters leave the accessibility tree so a screen reader does not read every stacked layer at once.
- Source links accept only `http` and `https`. Never render `javascript:` or `data:` URLs from story data.
- Provide a visible focus indicator for the header, navigation, dialog, and source controls.
- On narrow screens, default copy to a bottom panel even when desktop uses left or right placement, and keep the active chapter's copy scrollable rather than shrinking the type to fit unbounded text.
- Keep critical subjects inside a safe central crop; landscape video crops aggressively on portrait screens.
- Prime loaded muted videos on the first user gesture for mobile browsers.

## Hosting safety

Never let a preview server expose configuration, prompts, scripts, private state, or temporary files, and do not rely on a filename merely starting with a dot. Serve only what the page requests: the HTML entry point, its stylesheet, `src/` JavaScript, `content/` JSON, and final media under `assets/`. Directory listings stay off, and a resolved path must remain inside the project.

`scripts/serve_project.py` implements that rule for local preview and is not a production server. For external hosting, prefer publishing a dedicated directory, and confirm MP4 responses carry the correct content type and byte-range support.
