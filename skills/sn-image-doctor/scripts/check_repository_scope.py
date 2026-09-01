#!/usr/bin/env python3
"""Fail when tracked repository content escapes the image/visualization allowlist."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_SKILLS = {
    "sn-image-base",
    "sn-image-doctor",
    "sn-image-imitate",
    "sn-image-resume",
    "sn-infographic",
}
ALLOWED_ROOT_FILES = {
    ".env.example",
    ".gitattributes",
    ".gitignore",
    "INSTALL.md",
    "INSTALL_CN.md",
    "LICENSE",
    "README.md",
    "README_CN.md",
}
ALLOWED_DOC_FILES = {
    "sn-image-generate.md",
    "sn-image-generate_en.md",
    "sn-infographic-examples.md",
    "sn-infographic-examples_CN.md",
}
ALLOWED_DOC_IMAGE_DIRS = {"infographics", "teasers"}
IMAGE_BRANCH_CLONE_COMMAND = (
    "git clone --branch image-viz --single-branch "
    "https://github.com/Ryderey/SenseNova-Skills.git"
)
FORBIDDEN_MARKDOWN_TEXT = {
    "$SN_IMAGE_BASE": "undefined image-base path variable",
    "https://platform.sensenova.cn/docs#model-": (
        "unreliable SenseNova documentation deep link"
    ),
}
FORBIDDEN_SKILL_COMMANDS = {
    "python scripts/": "runtime command depends on the current working directory",
    "pip install -r requirements.txt": (
        "dependency command depends on the current working directory"
    ),
    "pip install -r ../sn-image-base/requirements.txt": (
        "dependency command depends on the current working directory"
    ),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def violation(path: Path) -> str | None:
    parts = path.parts
    if len(parts) == 1:
        return None if path.name in ALLOWED_ROOT_FILES else "unexpected root file"
    if parts[0] in {"assets", ".github"}:
        return None
    if parts[0] == "skills":
        if len(parts) < 2 or parts[1] not in ALLOWED_SKILLS:
            return "out-of-scope skill"
        if "workbench-runtime" in parts:
            return "Workbench runtime is out of scope"
        return None
    if parts[0] == "docs":
        if len(parts) == 2 and parts[1] in ALLOWED_DOC_FILES:
            return None
        if (
            len(parts) >= 4
            and parts[1] == "images"
            and parts[2] in ALLOWED_DOC_IMAGE_DIRS
        ):
            return None
        return "out-of-scope documentation or image"
    return "unexpected top-level directory"


def documentation_violations() -> list[tuple[Path, str]]:
    failures: list[tuple[Path, str]] = []
    for name in ("INSTALL.md", "INSTALL_CN.md"):
        path = REPO_ROOT / name
        if IMAGE_BRANCH_CLONE_COMMAND not in path.read_text(encoding="utf-8"):
            failures.append(
                (
                    path.relative_to(REPO_ROOT),
                    "clone command does not select the image branch",
                )
            )

    for path in REPO_ROOT.rglob("*.md"):
        if any(part in {".git", ".venv"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for token, reason in FORBIDDEN_MARKDOWN_TEXT.items():
            if token in text:
                failures.append((path.relative_to(REPO_ROOT), reason))

    for path in (REPO_ROOT / "skills").glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        for command, reason in FORBIDDEN_SKILL_COMMANDS.items():
            if command in text:
                failures.append((path.relative_to(REPO_ROOT), reason))
    return failures


def main() -> int:
    failures = [
        (path, reason) for path in tracked_files() if (reason := violation(path))
    ]
    failures.extend(documentation_violations())
    if failures:
        for path, reason in failures:
            print(f"[FAIL] {path.as_posix()}: {reason}")
        return 1
    actual_skills = {
        path.name for path in (REPO_ROOT / "skills").iterdir() if path.is_dir()
    }
    if actual_skills != ALLOWED_SKILLS:
        print(
            f"[FAIL] skill directories: expected {sorted(ALLOWED_SKILLS)}, got {sorted(actual_skills)}"
        )
        return 1
    print(
        "[OK] Repository is limited to the five image/visualization skills and allowed assets/docs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
