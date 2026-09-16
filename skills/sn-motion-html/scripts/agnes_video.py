#!/usr/bin/env python3
"""Generate this project's video clips with Agnes Video 2.5 Flash.

The script is the executor, not the author: it reads the clip prompts and anchor
settings that a host Agent already wrote into prompts/video-manifest.json, calls
the Agnes CLI, normalizes each downloaded clip with FFmpeg, and writes the
normalized clip into assets/video/dives/.

Agnes Video 2.5 Flash accepts no local media: every frame or reference it
receives must be a public HTTPS URL. Three anchor modes cover that:

  generate   create the anchor image through Agnes first, so its own public
             provider URL can be handed to the video call (no host needed)
  url        use the record's first_frame URL, supplied by the user from a host
             they control
  text       no media at all; the clip is composed from its prompt, so it will
             not match the page still exactly

Use --dry-run to print every call it would make without spending anything.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_model import (  # noqa: E402
    ProjectError,
    chapters_of,
    load_story,
    resolve_media_mode,
    validate_story,
)

AGNES_MODEL = "agnes-video-2.5-flash"
IMAGE_MODEL = "agnes-image-2.5-flash"  # only for anchor_mode generate
ANCHOR_MODES = ("generate", "url", "reference", "text")
FLASH_DURATIONS = range(4, 13)
FLASH_REFERENCE_LIMIT = 5
# Agnes Video 2.5 Flash mode per anchor mode: a generated anchor becomes the clip's
# first frame, hosted frames become its boundaries, and references guide it.
FLASH_MODES = {"generate": "keyframe", "url": "keyframe", "reference": "reference", "text": "text"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# Private run state: the provider URL of every generated anchor, so a later
# connector can reference the frames the page actually shows. Never served and
# never a deliverable.
STATE_RELATIVE = ".motion-state/video-anchors.json"


class PipelineError(RuntimeError):
    """A problem that must stop the run before any provider call."""


def public_https(value: str) -> bool:
    """Flash only accepts public HTTPS media inputs."""
    return value.strip().lower().startswith("https://")


def load_state(root: Path) -> dict:
    path = root / STATE_RELATIVE
    if not path.is_file():
        return {"clips": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"clips": {}}
    if not isinstance(state, dict) or not isinstance(state.get("clips"), dict):
        return {"clips": {}}
    return state


def save_state(root: Path, state: dict) -> None:
    path = root / STATE_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_anchor(root: Path, clip_id: str, url: str) -> None:
    state = load_state(root)
    state["clips"][clip_id] = {"anchor_model": IMAGE_MODEL, "anchor_url": url}
    state["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    save_state(root, state)


def agnes_cli(explicit: str | None) -> Path:
    """Resolve the Agnes CLI from an argument or the environment."""
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise PipelineError(f"--agnes-cli does not exist: {path}")
        return path
    skill_dir = os.environ.get("AGNES_SKILL_DIR", "").strip()
    if skill_dir:
        path = (Path(skill_dir).expanduser() / "scripts" / "agnes_media.py").resolve()
        if not path.is_file():
            raise PipelineError(f"AGNES_SKILL_DIR has no scripts/agnes_media.py: {path}")
        return path
    raise PipelineError(
        "cannot find the Agnes CLI: pass --agnes-cli, or set AGNES_SKILL_DIR to the "
        "directory containing the agnes-media SKILL.md"
    )


def run_agnes(cli: Path, args: list[str], output_dir: Path) -> dict:
    """Run one Agnes subcommand and return its JSON object."""
    env = dict(os.environ, AGNES_OUTPUT_DIR=str(output_dir))
    if not env.get("AGNES_API_KEY", "").strip():
        raise PipelineError("AGNES_API_KEY is not set in the environment")
    result = subprocess.run(
        [sys.executable, str(cli), *args],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=1800,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not lines:
        detail = (result.stderr or result.stdout or "").strip()[-800:]
        raise PipelineError(f"agnes {' '.join(args[:1])} failed (exit {result.returncode}): {detail}")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise PipelineError(f"agnes did not return JSON: {exc}") from exc


def read_prompt(root: Path, relative: str, label: str) -> str:
    path = root / relative
    if not path.is_file():
        raise PipelineError(f"{label} prompt is missing: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise PipelineError(f"{label} prompt is empty: {path}")
    return text


def normalize(source: Path, target: Path, *, seconds: int, width: int, height: int, fps: int) -> None:
    """Normalize a provider clip to the manifest's exact target."""
    if shutil.which("ffmpeg") is None:
        raise PipelineError("ffmpeg is required to normalize provider clips")
    target.parent.mkdir(parents=True, exist_ok=True)
    filter_graph = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps}"
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(source), "-t", str(seconds),
         "-vf", filter_graph, "-c:v", "libx264", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-g", "8", "-an", "-movflags", "+faststart", str(target)],
        check=True,
    )


def write_still(clip: Path, target: Path, *, force: bool) -> None:
    """Use the clip's own first frame as the page still, so page and clip match."""
    from PIL import Image

    if target.exists() and not force:
        raise PipelineError(f"refusing to overwrite an existing still: {target.name} (pass --force)")
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = target.with_suffix(".frame.png")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-frames:v", "1", str(frame)],
        check=True,
    )
    with Image.open(frame) as image:
        image.convert("RGB").save(target, "WEBP", quality=90, method=6)
    frame.unlink()


def resolve_references(root: Path, record: dict) -> list[str]:
    """Return this clip's reference-image URLs, reading recorded anchors at run time.

    A connector without an explicit list borrows the anchor images of the two
    chapters it joins. They are read here rather than at plan time so one
    invocation can generate the dives first and then their connectors.
    """
    if record["references"]:
        return list(record["references"])
    if not record["references_from"]:
        return []
    state = load_state(root)
    resolved: list[str] = []
    missing: list[str] = []
    for clip_id in record["references_from"]:
        entry = state["clips"].get(clip_id) or {}
        url = str(entry.get("anchor_url") or "")
        if public_https(url):
            resolved.append(url)
        else:
            missing.append(clip_id)
    if missing:
        raise PipelineError(
            f"{record['id']}: no anchor image is recorded for {', '.join(missing)} in "
            f"{STATE_RELATIVE}; generate those dives first, or list reference_images explicitly"
        )
    return resolved


def plan_records(root: Path, manifest: dict) -> list[dict]:
    """Build one execution plan per clip, with every problem reported up front.

    Dives carry the chapter's motion and feed the page still. Connectors join two
    chapters: their boundary frames are local extracts, so they are anchored
    through provider-hosted images instead — `reference` uses the two chapters'
    anchor images (both already public), `url` uses frames the user hosts, and
    `text` composes from the prompt alone.
    """
    if manifest.get("model") != AGNES_MODEL:
        raise PipelineError(
            f"prompts/video-manifest.json must set \"model\": \"{AGNES_MODEL}\"; "
            f"got {manifest.get('model')!r}"
        )
    seconds = manifest.get("duration")
    if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds not in FLASH_DURATIONS:
        raise PipelineError(f"Flash needs an integer duration from 4 to 12 seconds; got {seconds!r}")
    if str(manifest.get("resolution", "")).strip().lower() != "720p":
        raise PipelineError(f"Flash requires resolution 720P; got {manifest.get('resolution')!r}")

    records: list[dict] = []
    groups = (
        ("dive", "dives", "assets/video/dives", True),
        ("connector", "connectors", "assets/video/connectors", False),
    )
    for kind, key, default_dir, has_still in groups:
        for entry in manifest.get(key) or []:
            if not isinstance(entry, dict):
                raise PipelineError(f"every {key}[] entry must be an object")
            clip_id = str(entry.get("id") or "")
            if not SAFE_ID.match(clip_id):
                raise PipelineError(f"{key}[].id must be filename-safe; got {clip_id!r}")
            anchor = str(entry.get("anchor_mode") or "text")
            if anchor not in ANCHOR_MODES:
                raise PipelineError(f"{clip_id}.anchor_mode must be one of {ANCHOR_MODES}; got {anchor!r}")

            first_frame = str(entry.get("first_frame") or "").strip()
            last_frame = str(entry.get("last_frame") or "").strip()
            references = [str(value).strip() for value in entry.get("reference_images") or []]
            references_from: list[str] = []
            anchor_prompt = None

            if anchor == "generate":
                if kind == "connector":
                    raise PipelineError(
                        f"{clip_id}: a connector joins two existing chapters, so a generated anchor would not "
                        "be either boundary. Use reference, url, or text instead"
                    )
                anchor_prompt = read_prompt(root, str(entry.get("anchor_prompt") or ""), f"{clip_id} anchor")
            elif anchor == "url":
                frames = [value for value in (first_frame, last_frame) if value]
                if not frames:
                    raise PipelineError(f"{clip_id}.anchor_mode is 'url' but neither first_frame nor last_frame is set")
                for value in frames:
                    if not public_https(value):
                        raise PipelineError(f"{clip_id}: a hosted frame must be a public HTTPS URL; got {value!r}")
            elif anchor == "reference":
                if not references:
                    # Borrow the two chapters' own anchor images. They are resolved
                    # when this clip runs, not when the plan is built, so a single
                    # invocation can generate the dives and then their connectors.
                    if kind != "connector":
                        raise PipelineError(
                            f"{clip_id}.anchor_mode is 'reference' but no reference_images are listed"
                        )
                    neighbours = [str(entry.get("from") or ""), str(entry.get("to") or "")]
                    if not all(neighbours):
                        raise PipelineError(
                            f"{clip_id}: a reference connector needs both 'from' and 'to', or an explicit "
                            "reference_images list"
                        )
                    references_from = neighbours
                if len(references) > FLASH_REFERENCE_LIMIT:
                    raise PipelineError(
                        f"{clip_id} lists {len(references)} reference images; Flash accepts at most "
                        f"{FLASH_REFERENCE_LIMIT}"
                    )
                for value in references:
                    if not public_https(value):
                        raise PipelineError(f"{clip_id}: a reference image must be a public HTTPS URL; got {value!r}")

            records.append({
                "kind": kind,
                "id": clip_id,
                "anchor_mode": anchor,
                "first_frame": first_frame,
                "last_frame": last_frame,
                "references": references,
                "references_from": references_from,
                "anchor_prompt": anchor_prompt,
                "prompt": read_prompt(root, str(entry.get("prompt") or ""), f"{clip_id} motion"),
                "output": str(entry.get("output") or f"{default_dir}/{clip_id}.mp4"),
                "still": f"assets/images/scenes/{clip_id}.webp" if has_still else None,
            })
    if not records:
        raise PipelineError("prompts/video-manifest.json declares no clips")
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--agnes-cli", help="absolute path to agnes_media.py")
    parser.add_argument("--only", action="append", default=[], metavar="ID",
                        help="limit the run to these dive ids (repeatable)")
    parser.add_argument("--seed", type=int, help="seed for every clip in this run")
    parser.add_argument("--write-stills", action="store_true",
                        help="write each clip's first frame as the page still")
    parser.add_argument("--force", action="store_true", help="overwrite existing clips")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and every call without spending anything")
    args = parser.parse_args()

    root = args.project_root.expanduser().resolve()
    try:
        story = load_story(root)
        mode = resolve_media_mode(story)
        problems = validate_story(root, story, mode)
        if problems:
            raise PipelineError("story problems: " + "; ".join(problems))
        manifest_path = root / "prompts" / "video-manifest.json"
        if not manifest_path.is_file():
            raise PipelineError(f"video mode needs a manifest: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = plan_records(root, manifest)
        cli = None if args.dry_run else agnes_cli(args.agnes_cli)
    except (ProjectError, PipelineError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}")
        return 1

    wanted = set(args.only)
    if wanted:
        unknown = wanted - {record["id"] for record in records}
        if unknown:
            print(f"FAIL --only names unknown dive ids: {', '.join(sorted(unknown))}")
            return 1
        records = [record for record in records if record["id"] in wanted]

    width = int(manifest.get("target_width", 1280))
    height = int(manifest.get("target_height", 720))
    fps = int(manifest.get("fps", 24))
    seconds = int(manifest["duration"])
    ratio = str(manifest.get("ratio", "16:9"))
    workdir = Path(tempfile.gettempdir()) / "sn-motion-video"
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"Model: {AGNES_MODEL}  {seconds}s  {ratio}  {width}x{height}@{fps}fps")
    print(f"Clips: {len(records)}")
    failures: list[str] = []
    for record in records:
        output = root / record["output"]
        anchor = record["anchor_mode"]
        print(f"\n== {record['kind']} {record['id']}  anchor={anchor}")
        if output.is_file() and not args.force:
            print(f"   skip: {record['output']} already exists (pass --force to replace)")
            continue
        if args.dry_run:
            if anchor == "generate":
                first_line = record["anchor_prompt"].splitlines()[0]
                print(f"   would call image-generate ({IMAGE_MODEL}, 1K, {ratio}): {first_line}...")
            elif anchor == "url":
                if record["first_frame"]:
                    print(f"   would use first_frame {record['first_frame']}")
                if record["last_frame"]:
                    print(f"   would use last_frame {record['last_frame']}")
            elif anchor == "reference":
                if record["references"]:
                    for url in record["references"]:
                        print(f"   would use reference image {url}")
                else:
                    # Resolved at run time; report it either way so a dry run can
                    # still warn that the anchors are not recorded yet.
                    try:
                        for url in resolve_references(root, record):
                            print(f"   would use reference image {url}")
                    except PipelineError as exc:
                        print(f"   note: {exc}")
            print(f"   would call video-generate --mode {FLASH_MODES[anchor]}: "
                  f"{record['prompt'].splitlines()[0]}...")
            print(f"   would normalize into {record['output']}")
            if anchor == "generate":
                print("   would record the anchor url in .motion-state/video-anchors.json")
            # Only a dive carries a page still; a connector has no still of its own.
            if args.write_stills and record["still"]:
                print(f"   would write still {record['still']}")
            continue
        try:
            first_frame = record["first_frame"]
            if anchor == "generate":
                image = run_agnes(cli, [
                    "image-generate", "--model", IMAGE_MODEL, "--prompt", record["anchor_prompt"],
                    "--size", "1K", "--ratio", ratio,
                ], workdir)
                urls = [url for url in image.get("image_urls") or [] if isinstance(url, str)]
                if not urls:
                    raise PipelineError(f"{record['id']}: image-generate returned no public URL")
                first_frame = urls[0]
                print(f"   anchor image: {first_frame}")

            video_args = [
                "video-generate", "--model", AGNES_MODEL,
                "--mode", FLASH_MODES[anchor],
                "--duration", str(seconds), "--resolution", "720P", "--aspect-ratio", ratio,
                "--timeout-seconds", "900", "--poll-interval-seconds", "10",
                "--prompt", record["prompt"],
            ]
            if anchor == "url":
                if first_frame:
                    video_args += ["--first-frame", first_frame]
                if record["last_frame"]:
                    video_args += ["--last-frame", record["last_frame"]]
            elif anchor == "reference":
                for url in resolve_references(root, record):
                    video_args += ["--reference-image", url]
            elif anchor != "text":
                video_args += ["--first-frame", first_frame]
            if args.seed is not None:
                video_args += ["--seed", str(args.seed)]

            video = run_agnes(cli, video_args, workdir)
            downloaded = str(video.get("local_path") or "")
            if not downloaded or not Path(downloaded).is_file():
                raise PipelineError(f"{record['id']}: provider returned no downloaded clip")
            print(f"   provider clip: {Path(downloaded).name}")

            normalize(Path(downloaded), output, seconds=seconds, width=width, height=height, fps=fps)
            print(f"   wrote {record['output']}")
            if anchor == "generate":
                # Remember which image the clip starts from, so a later connector can
                # reference the frame the page actually shows.
                record_anchor(root, record["id"], first_frame)
                print("   recorded anchor url in .motion-state/video-anchors.json")
            # Only a dive carries a page still; a connector has no still of its own.
            if args.write_stills and record["still"]:
                write_still(output, root / record["still"], force=args.force)
                print(f"   wrote {record['still']}")
        except (PipelineError, subprocess.CalledProcessError, OSError) as exc:
            failures.append(f"{record['id']}: {exc}")
            print(f"   FAIL {exc}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    if args.dry_run:
        print("\nDry run complete: nothing was generated.")
    else:
        print("\nAll requested clips are in place. Run scripts/verify_media.py next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
