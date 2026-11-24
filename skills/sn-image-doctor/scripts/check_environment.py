#!/usr/bin/env python3
"""Offline environment diagnostics for the five SenseNova image skills."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPT_DIR.parents[1]
BASE_SKILL_DIR = SKILLS_DIR / "sn-image-base"
BASE_SCRIPTS = BASE_SKILL_DIR / "scripts"
DEFAULT_IMAGE_SKILL_NAMES = (
    "sn-image-base",
    "sn-image-doctor",
    "sn-infographic",
    "sn-image-imitate",
    "sn-image-resume",
)
_inserted_scripts = str(BASE_SCRIPTS) not in sys.path
if _inserted_scripts:
    sys.path.insert(0, str(BASE_SCRIPTS))
try:
    IMAGE_SKILL_NAMES = importlib.import_module("sn_image_base").IMAGE_SKILL_NAMES
except (ImportError, AttributeError):
    IMAGE_SKILL_NAMES = DEFAULT_IMAGE_SKILL_NAMES
finally:
    if _inserted_scripts:
        sys.path.pop(0)
EXPECTED_SKILLS = frozenset(IMAGE_SKILL_NAMES)


def check_installation(verbose: bool) -> bool:
    print("[1/4] Checking image-skill installation...")
    discovered = {path.name for path in SKILLS_DIR.iterdir() if (path / "SKILL.md").is_file()}
    missing = sorted(EXPECTED_SKILLS - discovered)
    required = [
        BASE_SKILL_DIR / "SKILL.md",
        BASE_SKILL_DIR / "requirements.txt",
        BASE_SKILL_DIR / "scripts/sn_agent_runner.py",
        BASE_SKILL_DIR / "scripts/sn_image_base/generation/sensenova.py",
    ]
    version_files = [SKILLS_DIR / name / "VERSION" for name in EXPECTED_SKILLS]
    missing_files = [path for path in required + version_files if not path.is_file()]
    versions = []
    for path in version_files:
        if path.is_file():
            try:
                versions.append(path.read_text(encoding="utf-8").strip())
            except OSError:
                pass
    unique_versions = set(versions)
    invalid_versions = [
        version for version in versions if re.fullmatch(r"\d+\.\d+\.\d+", version) is None
    ]
    versions_ok = (
        len(versions) == len(version_files)
        and len(unique_versions) == 1
        and not invalid_versions
        and bool(versions and all(versions))
    )
    if not versions_ok:
        if len(unique_versions) > 1:
            print("  [FAIL] Installed skills have mixed VERSION files; update all five together")
        elif invalid_versions:
            print("  [FAIL] Installed skills need canonical X.Y.Z VERSION files")
        else:
            print("  [FAIL] Installed skills need matching readable VERSION files")
    for name in sorted(discovered & EXPECTED_SKILLS):
        if verbose:
            print(f"  [OK] {name}")
    for name in missing:
        print(f"  [FAIL] Missing skill: {name}")
    for path in missing_files:
        print(f"  [FAIL] Missing file: {path.relative_to(SKILLS_DIR)}")
    ok = not (missing or missing_files or not versions_ok)
    if ok and verbose and versions:
        print(f"  [INFO] Bundle version: {versions[0]}")
    if ok and not verbose:
        print("  [OK] All required image and visualization skills are installed")
    return ok


def check_dependencies(verbose: bool) -> bool:
    print("[2/4] Checking Python runtime and dependencies...")
    ok = sys.version_info >= (3, 9)
    executable = Path(sys.executable).resolve()
    print(
        f"  {'[OK]' if ok else '[FAIL]'} Python "
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} ({executable})"
    )
    package_imports = {
        "httpx": "httpx",
        "pillow": "PIL",
        "python-dotenv": "dotenv",
        "typing-extensions": "typing_extensions",
    }
    missing = [
        name for name, module in package_imports.items() if importlib.util.find_spec(module) is None
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
        from sn_image_base.configs import (
            CHAT_INTERFACE_TYPES,
            global_configs,
            is_valid_base_url,
        )
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
            is_valid_base_url,
            CHAT_INTERFACE_TYPES,
        )
    finally:
        sys.path.pop(0)


def load_updates(base_skill_dir: Path | None = None):
    scripts = (base_skill_dir or BASE_SKILL_DIR) / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from sn_image_base import updates

        return updates
    finally:
        sys.path.pop(0)


def _configured_models() -> tuple[str, ...]:
    try:
        configs = _load_runtime()[0]
        candidates = (
            configs.SN_IMAGE_GEN_MODEL,
            configs.SN_IMAGE_GEN_FALLBACK_MODEL,
            configs.SN_TEXT_MODEL,
            configs.SN_VISION_MODEL,
            configs.SN_CHAT_MODEL,
        )
        return load_updates().normalize_models(candidates)
    except (ImportError, OSError, ValueError):
        return ()


def check_image_runtime(verbose: bool, require_edit: bool = False) -> bool:
    print("[3/4] Checking image models, endpoint and safe defaults...")
    try:
        (
            configs,
            primary,
            _fallback,
            generation_path,
            edit_path,
            client_type,
            runtime_error,
            _base_url_validator,
            _chat_interface_types,
        ) = _load_runtime()
    except (ImportError, OSError, ValueError) as exc:
        print(f"  [FAIL] Could not load image runtime: {exc}")
        return False

    backend = configs.SN_IMAGE_GEN_MODEL_TYPE
    checks = {
        "API key is configured": bool(configs.SN_IMAGE_GEN_API_KEY),
        "image base URL is valid": _base_url_validator(configs.SN_IMAGE_GEN_BASE_URL),
        "image backend is supported": backend in {"sensenova", "nano-banana", "openai-image"},
        "image model is configured": bool(configs.SN_IMAGE_GEN_MODEL),
        "generation endpoint is /images/generations": generation_path == "/images/generations",
        "editing endpoint is /images/edits": edit_path == "/images/edits",
    }
    if require_edit:
        checks["native image editing is available"] = backend == "sensenova"

    if verbose:
        source = getattr(configs, "env_file", None)
        print(
            f"  [INFO] Environment file: {source or 'none; using process/persistent environment'}"
        )
        print(f"  [INFO] Configured backend: {backend}")
        print(f"  [INFO] Configured primary model: {configs.SN_IMAGE_GEN_MODEL}")
        print(
            f"  [INFO] Configured fallback model: {configs.SN_IMAGE_GEN_FALLBACK_MODEL or 'none'}"
        )
    if backend != "sensenova" and not require_edit:
        print("  [WARN] Native SenseNova image editing is unavailable with this backend")
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
                "prompt extension defaults to true": payload.get("prompt_extend") is True,
                "response format defaults to b64_json": payload.get("response_format")
                == "b64_json",
                "U1.6 2K mapping is valid": client._resolve_size("2K", "16:9") == "2720x1536",
                "Retired U1.5 Fast Base64 shape is diagnostic-only": client.build_payload(
                    "diagnostic", "sensenova-u1.5-fast", size="4096x4096"
                ).get("response_format") == "b64_json",
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
        print("  [OK] U1.6 generation/editing defaults are valid (retired U1.5 IDs are unsupported)")
    return all(checks.values())


def check_optional_chat_runtime(verbose: bool, required: frozenset[str] = frozenset()) -> bool:
    print("[4/4] Checking optional external text/vision adapters...")
    runtime = _load_runtime()
    configs = runtime[0]
    base_url_validator = runtime[-2]
    chat_interface_types = runtime[-1]
    runtimes = {
        "text": {
            "model": configs.SN_TEXT_MODEL,
            "api_key": configs.SN_TEXT_API_KEY or getattr(configs, "SN_CHAT_API_KEY", ""),
            "base_url": configs.SN_TEXT_BASE_URL or getattr(configs, "SN_CHAT_BASE_URL", ""),
            "type": configs.SN_TEXT_TYPE or getattr(configs, "SN_CHAT_TYPE", ""),
        },
        "vision": {
            "model": configs.SN_VISION_MODEL,
            "api_key": configs.SN_VISION_API_KEY or getattr(configs, "SN_CHAT_API_KEY", ""),
            "base_url": configs.SN_VISION_BASE_URL or getattr(configs, "SN_CHAT_BASE_URL", ""),
            "type": configs.SN_VISION_TYPE or getattr(configs, "SN_CHAT_TYPE", ""),
        },
    }
    selected = {label: values for label, values in runtimes.items() if values["model"]}
    if not selected:
        if required:
            for label in sorted(required):
                print(f"  [FAIL] {label} adapter: model is not configured")
            return False
        print("  [OK] No external chat model selected; the host Agent will plan and review")
        return True
    valid = True
    for label, values in selected.items():
        problems = []
        if not values["api_key"]:
            problems.append("API key is missing")
        if not base_url_validator(values["base_url"]):
            problems.append("base URL is invalid")
        if values["type"] not in chat_interface_types:
            problems.append("interface type is unsupported")
        if problems:
            level = "FAIL" if label in required else "WARN"
            valid = valid and label not in required
            print(f"  [{level}] {label} adapter: {', '.join(problems)}")
        elif verbose:
            print(f"  [OK] {label} adapter is fully configured")
    if (
        not any(
            not values["api_key"]
            or not base_url_validator(values["base_url"])
            or values["type"] not in chat_interface_types
            for values in selected.values()
        )
        and not verbose
    ):
        print("  [OK] Selected external chat adapters are fully configured")
    for label in sorted(required - selected.keys()):
        valid = False
        print(f"  [FAIL] {label} adapter: model is not configured")
    return valid


def main() -> int:
    parser = argparse.ArgumentParser(description="SenseNova image-skill environment diagnostic")
    parser.add_argument("--verbose", action="store_true", help="Show each passing check")
    parser.add_argument(
        "--require-edit",
        action="store_true",
        help="Require the native SenseNova image-editing backend",
    )
    parser.add_argument("--require-text", action="store_true", help="Require a valid text adapter")
    parser.add_argument(
        "--require-vision", action="store_true", help="Require a valid vision adapter"
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="Force a repository release check and show update instructions",
    )
    parser.add_argument(
        "--no-update-check",
        action="store_true",
        help="Skip the automatic repository release check",
    )
    args = parser.parse_args()
    print("=== SenseNova Image Skills Environment Check ===\n")
    if args.check_update:
        try:
            updates = load_updates()
            result = updates.emit_update_check(
                force=True,
                models=_configured_models(),
            )
        except (ImportError, OSError, ValueError) as exc:
            print(f"[FAIL] Could not check repository updates: {exc}")
            return 1
        return updates.UPDATE_REQUIRED_EXIT_CODE if result.blocking else 0
    installation_ok = check_installation(args.verbose)
    dependencies_ok = check_dependencies(args.verbose)
    if dependencies_ok:
        image_ok = check_image_runtime(args.verbose, require_edit=args.require_edit)
        required_adapters = frozenset(
            label
            for label, enabled in (
                ("text", args.require_text),
                ("vision", args.require_vision),
            )
            if enabled
        )
        adapters_ok = check_optional_chat_runtime(args.verbose, required=required_adapters)
    else:
        print("[3/4] Checking image models, endpoint and safe defaults...")
        print("  [SKIP] Install the missing Python packages first")
        print("[4/4] Checking optional external text/vision adapters...")
        print("  [SKIP] Install the missing Python packages first")
        image_ok = adapters_ok = False
    update_check = None
    update_module = None
    if not args.no_update_check:
        try:
            update_module = load_updates()
            update_check = update_module.emit_update_check(
                models=_configured_models()
            )
        except (ImportError, OSError, ValueError) as exc:
            if args.verbose:
                print(f"  [WARN] Repository update check unavailable: {exc}")
    results = [installation_ok, dependencies_ok, image_ok, adapters_ok]
    print("\n=== Summary ===")
    if update_check is not None and update_check.blocking:
        reason = (
            update_check.notice.reason
            if update_check.notice is not None
            else "required repository policy"
        )
        remedies = (
            update_check.notice.remedies
            if update_check.notice is not None and update_check.notice.remedies
            else ("install the required release",)
        )
        print(f"[FAIL] {reason}. Required actions: {'; '.join(remedies)}")
        return update_module.UPDATE_REQUIRED_EXIT_CODE
    if all(results):
        print("[OK] Offline image configuration is ready")
        return 0
    print("[FAIL] Environment check failed; fix the items above and rerun")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
