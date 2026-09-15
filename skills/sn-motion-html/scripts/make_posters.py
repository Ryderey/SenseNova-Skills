#!/usr/bin/env python3
"""Convert scene PNG masters to compact WebP posters for the web page.

Lossless masters stay untouched: each poster is written next to its master with
a .webp suffix, and the script refuses to write over any input file.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--quality", type=int, default=84, help="WebP quality, 1-100")
    parser.add_argument("--max-width", type=int, default=1800, help="downscale wider masters to this width")
    args = parser.parse_args()

    if not 1 <= args.quality <= 100:
        raise SystemExit("--quality must be between 1 and 100")
    if args.max_width < 64:
        raise SystemExit("--max-width must be at least 64")

    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("Pillow is required to build web posters")

    root = args.project_root.expanduser().resolve()
    scenes = root / "assets" / "images" / "scenes"
    if not scenes.is_dir():
        raise SystemExit(f"no scene directory found: {scenes}")
    inputs = sorted(path for path in scenes.glob("*.png") if path.is_file())
    if not inputs:
        raise SystemExit(
            f"no PNG scene masters found in {scenes}; stills are already web-ready or missing"
        )

    failures: list[str] = []
    for source in inputs:
        target = source.with_suffix(".webp")
        if target.resolve() == source.resolve():
            failures.append(f"{source.name}: refusing to overwrite a master")
            continue
        try:
            target.relative_to(scenes.resolve())
        except ValueError:
            failures.append(f"{source.name}: poster would land outside the scene directory")
            continue
        with Image.open(source) as image:
            image = image.convert("RGB")
            if image.width > args.max_width:
                height = round(image.height * args.max_width / image.width)
                image = image.resize((args.max_width, height), Image.Resampling.LANCZOS)
            image.save(target, "WEBP", quality=args.quality, method=6)
        before = source.stat().st_size
        after = target.stat().st_size
        print(
            f"saved {target.relative_to(root)} "
            f"({image.width}x{image.height}, {before // 1024} KiB -> {after // 1024} KiB)"
        )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
