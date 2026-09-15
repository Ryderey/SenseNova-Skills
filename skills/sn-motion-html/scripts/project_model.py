#!/usr/bin/env python3
"""Shared story-project model: media-mode resolution and safe path handling.

Copied into every generated project and imported by the sibling project
scripts. Keep it dependency-free beyond the standard library.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MEDIA_MODES = ("images", "video")
STYLES = ("anime", "cinematic", "cgi")
UI_PRESETS = ("folio", "caption", "graphic")
COPY_POSITIONS = ("left", "right", "bottom", "center")
LANGS = ("zh", "en")

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# Media the page itself may request. Nothing else belongs in a public directory.
WEB_IMAGE_SUFFIXES = {".webp", ".png", ".jpg", ".jpeg", ".avif", ".gif", ".svg"}
WEB_VIDEO_SUFFIXES = {".mp4", ".webm"}

VIDEO_ONLY_TEMPLATE_PATHS = (
    "prompts/video-manifest.json",
    "prompts/video",
    ".env.example",
)
VIDEO_ONLY_TEMPLATE_DIRS = (
    "assets/video/dives",
    "assets/video/connectors",
    "assets/video/frames",
)
# Refreshing a project with --force must never touch these.
PROTECTED_TEMPLATE_PATHS = ("content/story.json", "assets", ".env", "tmp", ".motion-state")


class ProjectError(RuntimeError):
    """A project layout or story-data problem the caller must report."""


def load_story(root: Path) -> dict[str, Any]:
    path = root / "content" / "story.json"
    if not path.is_file():
        raise ProjectError(f"missing story file: {path}")
    try:
        story = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectError(f"content/story.json is not valid JSON: {exc}") from exc
    if not isinstance(story, dict):
        raise ProjectError("content/story.json must be a JSON object")
    return story


def chapters_of(story: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = story.get("chapters")
    if not isinstance(chapters, list):
        raise ProjectError("content/story.json needs a 'chapters' list")
    return [chapter for chapter in chapters if isinstance(chapter, dict)]


def resolve_media_mode(story: dict[str, Any]) -> str:
    """Resolve the project's media mode.

    An explicit ``images`` always wins so a legacy ``clip`` field cannot make an
    image project load video. A project without the field is only treated as
    video when it actually declares clips or connectors.
    """
    meta = story.get("meta") if isinstance(story.get("meta"), dict) else {}
    declared = meta.get("mediaMode")
    if declared is not None:
        if declared not in MEDIA_MODES:
            raise ProjectError(
                f"meta.mediaMode must be one of {MEDIA_MODES}, got {declared!r}"
            )
        return str(declared)

    chapters = chapters_of(story)
    connectors = story.get("connectors")
    has_clips = any(chapter.get("clip") for chapter in chapters)
    has_connectors = isinstance(connectors, list) and any(connectors)
    return "video" if (has_clips or has_connectors) else "images"


def relative_media_path(root: Path, raw: str) -> Path:
    """Resolve a project-relative media path, rejecting escapes."""
    if not isinstance(raw, str) or not raw.strip():
        raise ProjectError("media path must be a non-empty string")
    candidate = Path(raw)
    if candidate.is_absolute() or candidate.drive or raw.startswith(("\\\\", "//")):
        raise ProjectError(f"media path must be project-relative: {raw}")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ProjectError(f"media path escapes the project directory: {raw}") from exc
    return resolved


def still_paths(root: Path, story: dict[str, Any]) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for chapter in chapters_of(story):
        raw = chapter.get("still")
        if raw:
            found.append((str(chapter.get("id") or "?"), relative_media_path(root, raw)))
    return found


def clip_paths(root: Path, story: dict[str, Any], manifest: dict[str, Any] | None = None) -> list[tuple[str, Path]]:
    """Collect clips from the story and, when present, the manifest.

    The page reads the story while the pipeline reads the manifest, so checking
    the union catches a clip the page expects but the manifest never produces.
    Duplicates resolve to a single entry.
    """
    found: list[tuple[str, Path]] = []

    def add(label: str, raw: Any) -> None:
        if not raw:
            return
        path = relative_media_path(root, raw)
        if any(existing == path for _, existing in found):
            return
        found.append((label, path))

    for chapter in chapters_of(story):
        add(str(chapter.get("id") or "?"), chapter.get("clip"))
    connectors = story.get("connectors")
    if isinstance(connectors, list):
        for index, raw in enumerate(connectors):
            add(f"connector-{index}", raw)
    if manifest:
        for record in manifest.get("dives") or []:
            if isinstance(record, dict):
                add(str(record.get("id") or "?"), record.get("output"))
        for record in manifest.get("connectors") or []:
            if isinstance(record, dict):
                add(str(record.get("id") or "?"), record.get("output"))
    return found


def validate_story(root: Path, story: dict[str, Any], mode: str) -> list[str]:
    """Return human-readable problems; an empty list means the story is usable."""
    problems: list[str] = []
    meta = story.get("meta") if isinstance(story.get("meta"), dict) else {}
    if not meta:
        problems.append("meta block is missing")
    if not str(meta.get("title") or "").strip():
        problems.append("meta.title is empty")

    style = meta.get("style")
    if style is not None and style not in STYLES:
        problems.append(f"meta.style must be one of {STYLES}, got {style!r}")
    ui = meta.get("ui")
    if ui is not None and ui not in UI_PRESETS:
        problems.append(f"meta.ui must be one of {UI_PRESETS}, got {ui!r}")
    lang = meta.get("lang")
    if lang is not None and lang not in LANGS:
        problems.append(f"meta.lang must be one of {LANGS}, got {lang!r}")

    chapters = chapters_of(story)
    if not chapters:
        problems.append("at least one chapter is required")

    seen: set[str] = set()
    for index, chapter in enumerate(chapters):
        label = f"chapters[{index}]"
        chapter_id = chapter.get("id")
        if not chapter_id or not SAFE_ID.match(str(chapter_id)):
            problems.append(f"{label}.id must be filename-safe and non-empty")
        elif str(chapter_id) in seen:
            problems.append(f"{label}.id is duplicated: {chapter_id}")
        else:
            seen.add(str(chapter_id))

        if not str(chapter.get("label") or chapter.get("title") or "").strip():
            problems.append(f"{label} needs a label or title")

        position = chapter.get("copyPosition")
        if position is not None and position not in COPY_POSITIONS:
            problems.append(f"{label}.copyPosition must be one of {COPY_POSITIONS}, got {position!r}")

        for key in ("span", "linger"):
            if chapter.get(key) is None:
                continue
            value = chapter[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                problems.append(f"{label}.{key} must be a number")
            elif value != value or value in (float("inf"), float("-inf")):
                problems.append(f"{label}.{key} must be finite")
            elif value < 0:
                problems.append(f"{label}.{key} must not be negative")
        if isinstance(chapter.get("span"), (int, float)) and not isinstance(chapter.get("span"), bool):
            if chapter["span"] <= 0:
                problems.append(f"{label}.span must be greater than zero")

        if not chapter.get("still"):
            problems.append(f"{label}.still is required")
        else:
            try:
                relative_media_path(root, chapter["still"])
            except ProjectError as exc:
                problems.append(f"{label}.still: {exc}")

        paragraphs = chapter.get("paragraphs")
        if paragraphs is not None and not isinstance(paragraphs, list):
            problems.append(f"{label}.paragraphs must be a list")

        if mode == "video" and not chapter.get("clip"):
            problems.append(f"{label}.clip is required in video mode")

    if mode == "video":
        connectors = story.get("connectors")
        expected = max(0, len(chapters) - 1)
        if not isinstance(connectors, list):
            problems.append("connectors must be a list in video mode")
        elif len(connectors) < expected:
            problems.append(
                f"video mode needs {expected} connector(s) for {len(chapters)} chapter(s); "
                "accept a visible cut explicitly to omit one"
            )
        else:
            for index, raw in enumerate(connectors):
                if raw is None:
                    continue
                try:
                    relative_media_path(root, raw)
                except ProjectError as exc:
                    problems.append(f"connectors[{index}]: {exc}")
    return problems


def web_visible(relative: str, mode: str) -> bool:
    """Whether a project-relative path may be served to the browser."""
    path = Path(relative.replace("\\", "/"))
    parts = path.parts
    if not parts or any(part.startswith(".") for part in parts):
        return False
    if path.suffix.lower() in WEB_VIDEO_SUFFIXES:
        return mode == "video" and parts[0] == "assets"
    if path.name in {"index.html", "favicon.ico"}:
        return len(parts) == 1
    if path.suffix.lower() == ".css" and len(parts) == 1:
        return True
    if path.suffix.lower() == ".js":
        return parts[0] == "src"
    if path.suffix.lower() == ".json":
        return parts[0] == "content"
    if path.suffix.lower() in WEB_IMAGE_SUFFIXES:
        return parts[0] == "assets"
    return False
