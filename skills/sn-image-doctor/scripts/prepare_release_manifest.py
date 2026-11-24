#!/usr/bin/env python3
"""Validate and generate the GitHub Release manifest asset."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from check_environment import load_updates

REPO_ROOT = Path(__file__).resolve().parents[3]


def validate_manifest(updates: Any) -> dict[str, Any]:
    path = REPO_ROOT / "release.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise TypeError("release.json must contain an object")
    errors: list[str] = []
    version = manifest.get("version")
    tag = version if isinstance(version, str) and version.startswith("v") else f"v{version}"
    try:
        updates.parse_release_manifest({"tag_name": tag}, manifest)
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
    for name in updates.IMAGE_SKILL_NAMES:
        skill_dir = REPO_ROOT / "skills" / name
        try:
            installed = (skill_dir / "VERSION").read_text(encoding="utf-8").strip()
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{name}: {exc}")
            continue
        if installed != version:
            errors.append(f"{name}/VERSION is {installed!r}, expected {version!r}")
        match = re.search(r"(?m)^  version: (.+)$", text)
        if match is None or match.group(1).strip() != version:
            errors.append(f"{name}/SKILL.md metadata.version does not match {version!r}")
    if errors:
        raise ValueError("\n".join(errors))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="Manifest asset path")
    args = parser.parse_args()
    try:
        updates = load_updates(REPO_ROOT / "skills" / "sn-image-base")
        if args.output.name != updates.MANIFEST_ASSET_NAME:
            raise ValueError(f"output filename must be {updates.MANIFEST_ASSET_NAME}")
        manifest = validate_manifest(updates)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (ImportError, OSError, TypeError, ValueError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Wrote {args.output} for v{manifest['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
