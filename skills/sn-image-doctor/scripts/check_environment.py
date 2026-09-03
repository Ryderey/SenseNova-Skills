#!/usr/bin/env python3
"""Offline environment diagnostics for the five SenseNova image skills."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPT_DIR.parents[1]
BASE_SKILL_DIR = SKILLS_DIR / "sn-image-base"
EXPECTED_SKILLS = {
    "sn-image-base",
    "sn-image-doctor",
    "sn-infographic",
    "sn-image-imitate",
    "sn-image-resume",
}
SUPPORTED_CHAT_TYPES = {"anthropic-messages", "openai-completions"}


def _valid_adapter_base_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return bool(
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def check_installation(verbose: bool) -> bool:
    print("[1/4] Checking image-skill installation...")
    discovered = {
        path.name for path in SKILLS_DIR.iterdir() if (path / "SKILL.md").is_file()
    }
    missing = sorted(EXPECTED_SKILLS - discovered)
    required = [
        BASE_SKILL_DIR / "SKILL.md",
        BASE_SKILL_DIR / "requirements.txt",
        BASE_SKILL_DIR / "scripts/sn_agent_runner.py",
        BASE_SKILL_DIR / "scripts/sn_image_base/generation/sensenova.py",
    ]
    missing_files = [path for path in required if not path.is_file()]
    for name in sorted(discovered & EXPECTED_SKILLS):
        if verbose:
            print(f"  [OK] {name}")
    for name in missing:
        print(f"  [FAIL] Missing skill: {name}")
    for path in missing_files:
        print(f"  [FAIL] Missing file: {path.relative_to(SKILLS_DIR)}")
    ok = not (missing or missing_files)
    if ok and not verbose:
        print("  [OK] All required image and visualization skills are installed")
    return ok


def check_dependencies(verbose: bool) -> bool:
    print("[2/4] Checking Python runtime and dependencies...")
    ok = sys.version_info >= (3, 9)
    print(
        f"  {'[OK]' if ok else '[FAIL]'} Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    package_imports = {
        "httpx": "httpx",
        "pillow": "PIL",
        "python-dotenv": "dotenv",
        "typing-extensions": "typing_extensions",
    }
    missing = [
        name
        for name, module in package_imports.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        print(f"  [FAIL] Missing packages: {', '.join(missing)}")
        print("  Run: python -m pip install -r skills/sn-image-base/requirements.txt")
        return False
    if verbose:
        for name in package_imports:
            print(f"  [OK] {name}")
    else:
        print("  [OK] Required packages are installed")
    return ok


def _load_runtime():
    scripts = BASE_SKILL_DIR / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from sn_image_base.configs import global_configs
        from sn_image_base.exceptions import U1BaseError
        from sn_image_base.generation.sensenova import (
            DEFAULT_MODEL,
            FAST_MODEL,
            IMAGE_EDIT_ENDPOINT,
            IMAGE_GEN_ENDPOINT,
            SensenovaText2ImageClient,
        )

        return (
            global_configs,
            DEFAULT_MODEL,
            FAST_MODEL,
            IMAGE_GEN_ENDPOINT,
            IMAGE_EDIT_ENDPOINT,
            SensenovaText2ImageClient,
            U1BaseError,
        )
    finally:
        sys.path.pop(0)


def check_image_runtime(verbose: bool) -> bool:
    print("[3/4] Checking image models, endpoint and safe defaults...")
    try:
        (
            configs,
            primary,
            fallback,
            generation_path,
            edit_path,
            client_type,
            runtime_error,
        ) = _load_runtime()
    except (ImportError, OSError, ValueError) as exc:
        print(f"  [FAIL] Could not load image runtime: {exc}")
        return False

    checks = {
        "API key is configured": bool(configs.SN_IMAGE_GEN_API_KEY),
        "image backend is sensenova": configs.SN_IMAGE_GEN_MODEL_TYPE == "sensenova",
        f"primary model is {primary}": configs.SN_IMAGE_GEN_MODEL == primary,
        f"fallback model is {fallback}": configs.SN_IMAGE_GEN_FALLBACK_MODEL
        == fallback,
        "generation endpoint is /images/generations": generation_path
        == "/images/generations",
        "editing endpoint is /images/edits": edit_path == "/images/edits",
    }
    try:
        client = client_type(
            api_key=configs.SN_IMAGE_GEN_API_KEY or "diagnostic-placeholder",
            base_url=configs.SN_IMAGE_GEN_BASE_URL,
            model=primary,
        )
        payload = client.build_payload("diagnostic", primary, size="2048x2048")
        checks.update(
            {
                "watermark defaults to false": payload.get("watermark") is False,
                "prompt extension defaults to true": payload.get("prompt_extend")
                is True,
                "response format defaults to b64_json": payload.get("response_format")
                == "b64_json",
                "U1.5 2K mapping is valid": client._resolve_size("2K", "16:9")
                == "2720x1536",
                "U1 Fast 9:21 bucket is valid": client._resolve_size(
                    "2K", "9:21", fast=True
                )
                == "1344x3136",
                "4K mapping stays within API limits": client._resolve_size("4K", "1:1")
                == "4096x4096",
            }
        )
    except (runtime_error, OSError, TypeError, ValueError) as exc:
        print(f"  [FAIL] Image runtime validation failed: {exc}")
        return False

    for label, passed in checks.items():
        if verbose or not passed:
            print(f"  {'[OK]' if passed else '[FAIL]'} {label}")
    if all(checks.values()) and not verbose:
        print("  [OK] U1.5 generation/editing and U1 Fast fallback defaults are valid")
    return all(checks.values())


def check_optional_chat_runtime(verbose: bool) -> bool:
    print("[4/4] Checking optional external text/vision adapters...")
    configs, *_rest = _load_runtime()
    runtimes = {
        "text": {
            "model": configs.SN_TEXT_MODEL,
            "api_key": configs.SN_TEXT_API_KEY
            or getattr(configs, "SN_CHAT_API_KEY", ""),
            "base_url": configs.SN_TEXT_BASE_URL
            or getattr(configs, "SN_CHAT_BASE_URL", ""),
            "type": configs.SN_TEXT_TYPE or getattr(configs, "SN_CHAT_TYPE", ""),
        },
        "vision": {
            "model": configs.SN_VISION_MODEL,
            "api_key": configs.SN_VISION_API_KEY
            or getattr(configs, "SN_CHAT_API_KEY", ""),
            "base_url": configs.SN_VISION_BASE_URL
            or getattr(configs, "SN_CHAT_BASE_URL", ""),
            "type": configs.SN_VISION_TYPE or getattr(configs, "SN_CHAT_TYPE", ""),
        },
    }
    selected = {label: values for label, values in runtimes.items() if values["model"]}
    if not selected:
        print(
            "  [OK] No external chat model selected; the host Agent will plan and review"
        )
        return True
    valid = True
    for label, values in selected.items():
        problems = []
        if not values["api_key"]:
            problems.append("API key is missing")
        if not _valid_adapter_base_url(values["base_url"]):
            problems.append("base URL is invalid")
        if values["type"] not in SUPPORTED_CHAT_TYPES:
            problems.append("interface type is unsupported")
        if problems:
            valid = False
            print(f"  [FAIL] {label} adapter: {', '.join(problems)}")
        elif verbose:
            print(f"  [OK] {label} adapter is fully configured")
    if valid and not verbose:
        print("  [OK] Selected external chat adapters are fully configured")
    return valid


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SenseNova image-skill environment diagnostic"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show each passing check"
    )
    args = parser.parse_args()
    print("=== SenseNova Image Skills Environment Check ===\n")
    results = [
        check_installation(args.verbose),
        check_dependencies(args.verbose),
        check_image_runtime(args.verbose),
        check_optional_chat_runtime(args.verbose),
    ]
    print("\n=== Summary ===")
    if all(results):
        print("[OK] Image and visualization environment is ready")
        return 0
    print("[FAIL] Environment check failed; fix the items above and rerun")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
