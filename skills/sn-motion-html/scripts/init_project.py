#!/usr/bin/env python3
"""Initialize an SN Motion HTML project from the bundled template.

Image mode is the default. It creates no video credentials, no video manifest,
and no empty video directories, so an image story needs only Python and Pillow.
"""

from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_model import (  # noqa: E402
    LANGS,
    MEDIA_MODES,
    PROTECTED_TEMPLATE_PATHS,
    VIDEO_ONLY_TEMPLATE_PATHS,
)

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "assets" / "template"

ALWAYS_SCRIPTS = (
    "project_model.py",
    "make_posters.py",
    "verify_media.py",
    "contact_sheet.py",
    "export_storyboard.py",
    "serve_project.py",
)
VIDEO_SCRIPTS = ("agnes_video.py", "seedance_pipeline.py")

HTML_LANG = {"zh": "zh-CN", "en": "en"}

IMAGE_DIRS = ("assets/images/characters", "assets/images/scenes", "docs")
VIDEO_DIRS = ("assets/video/dives", "assets/video/connectors", "assets/video/frames")


def is_protected(relative: Path) -> bool:
    """Whether a template path must survive a --force merge."""
    return any(
        relative == Path(entry) or Path(entry) in relative.parents
        for entry in PROTECTED_TEMPLATE_PATHS
    )


def copy_template(template: Path, output: Path, merge: bool) -> list[str]:
    skipped: list[str] = []
    for source in sorted(template.rglob("*")):
        relative = source.relative_to(template)
        target = output / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if merge and target.exists() and is_protected(relative):
            skipped.append(relative.as_posix())
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return skipped


def copy_scripts(output: Path, media: str) -> None:
    scripts = output / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for name in ALWAYS_SCRIPTS + (VIDEO_SCRIPTS if media == "video" else ()):
        source = SKILL_ROOT / "scripts" / name
        if not source.is_file():
            raise SystemExit(f"skill script is missing: {source}")
        target = scripts / name
        shutil.copy2(source, target)
        target.chmod(0o755)


def strip_video_scaffolding(output: Path, story: dict) -> list[str]:
    """Remove video-only files and fields from an image project.

    Returns the paths that were removed so the caller can report them rather
    than deleting a manifest silently.
    """
    removed: list[str] = []
    for relative in VIDEO_ONLY_TEMPLATE_PATHS:
        candidate = output / relative
        if candidate.is_dir():
            shutil.rmtree(candidate, ignore_errors=True)
            removed.append(relative)
        elif candidate.exists():
            candidate.unlink()
            removed.append(relative)
    if "connectors" in story:
        removed.append("story.json: connectors")
        story.pop("connectors")
    for chapter in story.get("chapters", []):
        if isinstance(chapter, dict) and "clip" in chapter:
            removed.append(f"story.json: {chapter.get('id')}.clip")
            chapter.pop("clip")
    return removed


def write_story(output: Path, story: dict, args: argparse.Namespace) -> None:
    meta = story.setdefault("meta", {})
    meta["title"] = args.title
    meta["style"] = args.style
    meta["ui"] = args.ui
    meta["mediaMode"] = args.media
    meta["lang"] = args.lang
    meta.pop("accent", None)
    (output / "content" / "story.json").write_text(
        json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_index(output: Path, title: str, lang: str) -> None:
    index = output / "index.html"
    text = index.read_text(encoding="utf-8")
    index.write_text(
        text.replace("{{TITLE}}", escape(title, quote=True)).replace(
            'lang="en"', f'lang="{HTML_LANG[lang]}"', 1
        ),
        encoding="utf-8",
    )


def write_style_prompts(output: Path, style: str) -> None:
    preset = json.loads(
        (SKILL_ROOT / "assets" / "style-presets" / f"{style}.json").read_text(encoding="utf-8")
    )
    (output / "prompts" / "style-preamble.txt").write_text(
        preset["image_prompt"].strip() + "\n", encoding="utf-8"
    )
    (output / "prompts" / "style-motion.txt").write_text(
        preset["video_prompt"].strip() + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="Untitled Story")
    parser.add_argument("--style", choices=["anime", "cinematic", "cgi"], default="cinematic")
    parser.add_argument("--ui", choices=["folio", "caption", "graphic"], default="folio")
    parser.add_argument(
        "--media",
        choices=list(MEDIA_MODES),
        default="images",
        help=(
            "images (default) ships no video tooling, manifest, or credentials; "
            "video adds clips, FFmpeg, and provider credentials"
        ),
    )
    parser.add_argument("--lang", choices=list(LANGS), default="zh", help="project content language")
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "merge into a non-empty directory. Template scaffolding is refreshed, but "
            "content/story.json, assets/, .env, tmp/, and .motion-state/ are never overwritten"
        ),
    )
    args = parser.parse_args()

    output = args.output.expanduser().resolve()
    if output.exists() and not output.is_dir():
        parser.error(f"output path exists and is not a directory: {output}")
    merge = output.is_dir() and any(output.iterdir())
    if merge and not args.force:
        parser.error(f"output directory is not empty: {output}; pass --force to merge")

    output.mkdir(parents=True, exist_ok=True)
    skipped = copy_template(TEMPLATE, output, merge)
    copy_scripts(output, args.media)

    story_path = output / "content" / "story.json"
    story = json.loads(story_path.read_text(encoding="utf-8"))
    preserved_story = merge and is_protected(Path("content/story.json")) and story_path.exists()

    stripped: list[str] = []
    if args.media == "images":
        stripped = strip_video_scaffolding(output, story)

    if preserved_story:
        story.setdefault("meta", {})["mediaMode"] = args.media
        story_path.write_text(
            json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        write_story(output, story, args)

    write_index(output, args.title, args.lang)
    write_style_prompts(output, args.style)

    for relative in IMAGE_DIRS + (VIDEO_DIRS if args.media == "video" else ()):
        directory = output / relative
        directory.mkdir(parents=True, exist_ok=True)
        if not any(directory.iterdir()):
            (directory / ".gitkeep").touch()

    if args.media == "video":
        env = output / ".env"
        if not env.exists():
            shutil.copyfile(output / ".env.example", env)
            env.chmod(0o600)

    print(f"Initialized SN Motion HTML project: {output}")
    print(f"Media mode: {args.media}")
    print(f"Style preset: {args.style}")
    print(f"Interface preset: {args.ui}")
    print(f"Content language: {args.lang}")
    if skipped:
        print("Preserved existing files (never overwritten):")
        for relative in skipped:
            print(f"- {relative}")
    if stripped:
        print("Removed video-only scaffolding for image mode:")
        for relative in stripped:
            print(f"- {relative}")
    if args.media == "images":
        print("No video manifest, video credentials, or video directories were created.")
        print("Next: replace the example chapters in content/story.json and add scene images.")
    else:
        print("Next: replace content/story.json and prompts/video-manifest.json, write the clip and anchor prompts, then run scripts/agnes_video.py.")
    print(
        'Check the project with: "<PYTHON>" '
        f'"{output / "scripts" / "verify_media.py"}" "{output}"'
    )
    print(
        'Export the storyboard with: "<PYTHON>" '
        f'"{output / "scripts" / "export_storyboard.py"}" "{output}"'
    )
    print(
        'Preview safely with: "<PYTHON>" '
        f'"{output / "scripts" / "serve_project.py"}" "{output}" --port 8080'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
