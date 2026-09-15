#!/usr/bin/env python3
"""Create a labeled review sheet for the project's declared media.

Image mode tiles the chapter stills with Pillow and never calls FFmpeg.
Video mode extracts the midpoint frame of every clip first, then tiles those.
Working files live in the system temporary directory and are removed afterwards.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_model import (  # noqa: E402
    ProjectError,
    chapters_of,
    clip_paths,
    load_story,
    resolve_media_mode,
    still_paths,
)

CJK_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def load_label_font(size: int):
    from PIL import ImageFont

    for candidate in CJK_FONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return None


def video_midpoint_frames(root: Path, manifest: dict, workdir: Path) -> list[tuple[str, Path]]:
    if shutil.which("ffmpeg") is None:
        raise ProjectError("FFmpeg is required to review video clips; image mode does not need it")
    duration = float(manifest.get("duration", 4))
    frames: list[tuple[str, Path]] = []
    records = [("scene", item) for item in manifest.get("dives", []) or []]
    records += [("connector", item) for item in manifest.get("connectors", []) or []]
    for index, (kind, item) in enumerate(records):
        source = root / item["output"]
        if not source.is_file():
            raise ProjectError(f"missing clip: {item['output']}")
        frame = workdir / f"{index:03d}-{kind}-{item['id']}.jpg"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(duration / 2), "-i", str(source),
             "-frames:v", "1", str(frame)],
            check=True,
        )
        frames.append((f"{kind}: {item['id']}", frame))
    return frames


def still_frames(root: Path, story: dict) -> list[tuple[str, Path]]:
    """Return (label, path) pairs. Labels carry no index; the sheet adds it."""
    chapters = chapters_of(story)
    by_id = {str(chapter.get("id")): chapter for chapter in chapters}
    frames: list[tuple[str, Path]] = []
    for chapter_id, path in still_paths(root, story):
        if not path.is_file():
            raise ProjectError(f"missing still: {path.name}")
        chapter = by_id.get(chapter_id, {})
        title = str(chapter.get("label") or chapter.get("title") or chapter_id).strip()
        frames.append((title, path))
    return frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--cell-width", type=int, default=384)
    parser.add_argument("--output", type=Path, help="defaults to a file in the system temporary directory")
    args = parser.parse_args()

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise SystemExit("Pillow is required to build a contact sheet")

    root = args.project_root.expanduser().resolve()
    try:
        story = load_story(root)
        mode = resolve_media_mode(story)
    except ProjectError as exc:
        raise SystemExit(str(exc))

    workdir = Path(tempfile.mkdtemp(prefix="sn-motion-contact-sheet-"))
    try:
        if mode == "images":
            frames = still_frames(root, story)
            print(f"Media mode: images ({len(frames)} still(s), no FFmpeg used)")
        else:
            manifest_path = root / "prompts" / "video-manifest.json"
            if not manifest_path.is_file():
                raise SystemExit(f"video mode needs a manifest: {manifest_path}")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            frames = video_midpoint_frames(root, manifest, workdir)
            print(f"Media mode: video ({len(frames)} clip(s))")
        if not frames:
            raise SystemExit("nothing to review: the project declares no media")

        columns = max(1, args.columns)
        cell_width = max(64, args.cell_width)
        cell_height = round(cell_width * 9 / 16)
        label_height = 34
        rows = (len(frames) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * cell_width, rows * (cell_height + label_height)), "#f2ebdd")
        draw = ImageDraw.Draw(sheet)
        font = load_label_font(15)

        for index, (label, frame) in enumerate(frames):
            with Image.open(frame) as image:
                tile = image.convert("RGB").resize((cell_width, cell_height), Image.Resampling.LANCZOS)
            x = (index % columns) * cell_width
            y = (index // columns) * (cell_height + label_height)
            sheet.paste(tile, (x, y))
            text = f"{index + 1:02d} {label}".strip() if font else f"{index + 1:02d}"
            draw.text((x + 8, y + cell_height + 9), text, fill="#25231f", font=font if font else None)

        if font is None:
            print("Note: no CJK-capable font was found, so labels use index numbers only.")

        if args.output:
            output = args.output.expanduser().resolve()
        else:
            output = Path(tempfile.gettempdir()) / f"sn-motion-contact-sheet-{root.name}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output)
        print(output)
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
