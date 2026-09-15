#!/usr/bin/env python3
"""Validate a motion-story project for its declared media mode.

Image mode checks the story data and the still images only. It never invokes
ffprobe, so a project without FFmpeg still validates completely.
Video mode adds the manifest, FFmpeg, and the clip checks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_model import (  # noqa: E402
    ProjectError,
    clip_paths,
    load_story,
    resolve_media_mode,
    still_paths,
    validate_story,
)


def load_manifest(root: Path) -> dict:
    path = root / "prompts" / "video-manifest.json"
    if not path.is_file():
        raise ProjectError(f"video mode needs a manifest: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectError(f"prompts/video-manifest.json is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ProjectError("prompts/video-manifest.json must be a JSON object")
    return manifest


def check_stills(records) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    failures: list[str] = []
    try:
        from PIL import Image
    except ImportError:
        return missing, ["Pillow is required to validate still images"]
    for label, path in records:
        if not path.is_file():
            missing.append(f"{label}: {path.name}")
            continue
        try:
            with Image.open(path) as image:
                width, height = image.width, image.height
                image.verify()
            print(f"OK   still {label} {width}x{height} {path.name}")
        except Exception as exc:  # noqa: BLE001 - report any decoder failure
            failures.append(f"{label}: {path.name} is not a readable image ({exc})")
    return missing, failures


def check_clips(records, manifest: dict) -> tuple[list[str], list[str]]:
    if shutil.which("ffprobe") is None:
        return [], ["ffprobe is required to validate clips; FFmpeg is only needed in video mode"]
    width = int(manifest.get("target_width", 1280))
    height = int(manifest.get("target_height", 720))
    fps = int(manifest.get("fps", 24))
    duration_target = float(manifest.get("duration", 4))
    missing: list[str] = []
    failures: list[str] = []
    for label, path in records:
        if not path.is_file():
            missing.append(f"{label}: {path.name}")
            continue
        command = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate:format=duration",
            "-of", "json", str(path),
        ]
        try:
            data = json.loads(subprocess.check_output(command, text=True))
            stream = data["streams"][0]
            duration = float(data["format"]["duration"])
        except Exception as exc:  # noqa: BLE001 - report any probe failure
            failures.append(f"{label}: {path.name} could not be probed ({exc})")
            continue
        okay = (
            stream["codec_name"] == "h264"
            and int(stream["width"]) == width
            and int(stream["height"]) == height
            and stream["r_frame_rate"] == f"{fps}/1"
            and abs(duration - duration_target) < 0.05
        )
        print(
            f"{'OK  ' if okay else 'FAIL'} clip  {label} "
            f"{stream['width']}x{stream['height']} {duration:.3f}s {path.name}"
        )
        if not okay:
            failures.append(
                f"{label}: {path.name} must be h264 {width}x{height} {fps}fps {duration_target}s"
            )
    return missing, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    root = args.project_root.expanduser().resolve()
    try:
        story = load_story(root)
        mode = resolve_media_mode(story)
    except ProjectError as exc:
        print(f"FAIL {exc}")
        return 1

    print(f"Media mode: {mode}")
    meta = story.get("meta") if isinstance(story.get("meta"), dict) else {}
    if meta.get("mediaMode") is None:
        print(f"Note: meta.mediaMode is missing; inferred '{mode}' from the declared media.")
    if meta.get("lang") is None:
        print("Note: meta.lang is missing; the page will infer the interface language from the content. "
              "Add meta.lang for a deterministic result.")
    problems = validate_story(root, story, mode)
    if problems:
        print("FAIL story problems:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    missing: list[str] = []
    failures: list[str] = []

    still_missing, still_failures = check_stills(still_paths(root, story))
    missing.extend(still_missing)
    failures.extend(still_failures)

    if mode == "video":
        try:
            manifest = load_manifest(root)
        except ProjectError as exc:
            print(f"FAIL {exc}")
            return 1
        clip_missing, clip_failures = check_clips(clip_paths(root, story, manifest), manifest)
        missing.extend(clip_missing)
        failures.extend(clip_failures)

    if missing:
        print("Missing media:")
        for item in missing:
            print(f"- {item}")
        if not args.allow_missing:
            return 2

    if failures:
        print("Failed checks:")
        for item in failures:
            print(f"- {item}")
        return 1

    scope = "stills" if mode == "images" else "stills and clips"
    print(f"OK   {scope} validated for media mode '{mode}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
