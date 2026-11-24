"""Check repository releases without contacting model providers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from . import IMAGE_SKILL_NAMES

LATEST_RELEASE_URL = (
    "https://api.github.com/repos/Ryderey/SenseNova-Skills/releases/latest"
)
MANIFEST_ASSET_NAME = "sensenova-release.json"
CACHE_TTL_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 2.5
UPDATE_REQUIRED_EXIT_CODE = 3
NOTICE_LEVELS = frozenset({"info", "recommended", "required"})
_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class RetiredModel:
    pattern: str
    replacement: str = ""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    summary: str
    release_url: str
    min_supported_version: str | None = None
    update_required: bool = False
    severity: str = "recommended"
    retired_models: tuple[RetiredModel, ...] = ()


@dataclass(frozen=True)
class UpdateNotice:
    local_version: str
    release: ReleaseInfo
    level: str
    reason: str
    replacement_model: str | None = None
    remedies: tuple[str, ...] = ()


@dataclass(frozen=True)
class UpdateCheck:
    local_version: str
    latest_version: str | None
    status: str
    notice: UpdateNotice | None = None

    @property
    def blocking(self) -> bool:
        return self.status == "required"


class UpdateCheckError(RuntimeError):
    pass


def parse_version(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = _VERSION_PATTERN.fullmatch(value.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def normalize_models(values: tuple[str | None, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def local_version(base_skill_dir: Path | None = None) -> str:
    base = base_skill_dir or Path(__file__).resolve().parents[2]
    try:
        return (base / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _release_from_dict(value: Any) -> ReleaseInfo | None:
    if not isinstance(value, dict) or parse_version(value.get("version")) is None:
        return None
    retired = value.get("retired_models", [])
    models = [
        {
            "name": item["pattern"],
            "status": "retired",
            "replacement": item.get("replacement", ""),
        }
        for item in retired
        if isinstance(item, dict) and isinstance(item.get("pattern"), str)
    ] if isinstance(retired, list) else []
    manifest = {
        "schema_version": 1,
        "version": value["version"],
        "summary": value.get("summary", ""),
        "release_notes": value.get("release_url", ""),
        "min_supported_version": value.get("min_supported_version"),
        "update_required": value.get("update_required") is True,
        "severity": value.get("severity", "recommended"),
        "retired_models": models,
    }
    payload = {
        "tag_name": value["version"],
        "body": value.get("summary", ""),
        "html_url": value.get("release_url", ""),
    }
    try:
        return parse_release_manifest(payload, manifest)
    except ValueError:
        return None


def _cache_path(base_skill_dir: Path | None = None) -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / ".cache"
    base = base_skill_dir or Path(__file__).absolute().parents[2]
    try:
        identity = str(base.resolve())
    except OSError:
        identity = str(base.absolute())
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return root / "SenseNova-Skills" / f"update-check-{digest}.json"


def _fallback_cache_path(path: Path) -> Path:
    dirname = "sensenova-skills-cache"
    if os.name == "posix" and hasattr(os, "getuid"):
        dirname = f"{dirname}-{os.getuid()}"
    return Path(tempfile.gettempdir()) / dirname / path.name


def _cache_candidates(path: Path) -> tuple[Path, ...]:
    if os.name != "posix":
        return (path,)
    return (path, _fallback_cache_path(path))


def _cache_dir_is_private(path: Path) -> bool:
    if os.name != "posix":
        return True
    try:
        info = path.stat()
    except OSError:
        return False
    return info.st_uid == os.getuid() and not info.st_mode & 0o077


def _prepare_cache_dir(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "posix":
        return True
    try:
        info = path.stat()
        if info.st_uid != os.getuid():
            return False
        if info.st_mode & 0o077:
            os.chmod(path, 0o700)
    except OSError:
        return False
    return True


def _read_cache(path: Path) -> dict[str, Any]:
    for candidate in _cache_candidates(path):
        if not _cache_dir_is_private(candidate.parent):
            continue
        try:
            value = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    return {}


def _write_cache_file(path: Path, value: dict[str, Any]) -> bool:
    temp_path: Path | None = None
    try:
        if not _prepare_cache_dir(path.parent):
            return False
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".update-check-",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False)
        if os.name == "posix":
            temp_path.chmod(0o600)
        os.replace(temp_path, path)
        return True
    except OSError:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass
        return False


def _write_cache(path: Path, value: dict[str, Any]) -> bool:
    for candidate in _cache_candidates(path):
        if _write_cache_file(candidate, value):
            return True
    return False


def _cache_is_fresh(cache: dict[str, Any], now: float) -> bool:
    checked_at = cache.get("checked_at")
    if not isinstance(checked_at, (int, float)):
        return False
    return 0 <= now - checked_at < CACHE_TTL_SECONDS


def _cached_release(cache: dict[str, Any]) -> ReleaseInfo | None:
    return _release_from_dict(cache.get("release"))


def parse_release_manifest(
    payload: dict[str, Any], manifest: dict[str, Any]
) -> ReleaseInfo:
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or parse_version(tag) is None:
        raise ValueError("Latest release has no valid version tag")
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported release manifest schema")
    version = manifest.get("version")
    if (
        not isinstance(version, str)
        or version.startswith("v")
        or parse_version(version) is None
        or parse_version(version) != parse_version(tag)
    ):
        raise ValueError("Release manifest version must be canonical and match its tag")
    summary = manifest.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Release manifest summary must be a non-empty string")
    release_url = manifest.get("release_notes")
    if not isinstance(release_url, str) or not release_url.startswith("https://"):
        raise ValueError("Release manifest release_notes must be an HTTPS URL")
    minimum = manifest.get("min_supported_version")
    if (
        not isinstance(minimum, str)
        or minimum.startswith("v")
        or parse_version(minimum) is None
    ):
        raise ValueError("Release manifest min_supported_version must be canonical X.Y.Z")
    update_required = manifest.get("update_required")
    if not isinstance(update_required, bool):
        raise ValueError("Release manifest update_required must be a boolean")
    severity = manifest.get("severity")
    if severity not in NOTICE_LEVELS:
        raise ValueError("Release manifest has an invalid severity")
    changes = manifest.get("retired_models")
    if not isinstance(changes, list):
        raise ValueError("Release manifest retired_models must be a list")
    retired_models: list[RetiredModel] = []
    for item in changes:
        if not isinstance(item, dict) or item.get("status") != "retired":
            raise ValueError("Release manifest retired model has an invalid status")
        pattern = item.get("name")
        replacement = item.get("replacement", "")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError("Release manifest retired model has no name")
        if not isinstance(replacement, str):
            raise ValueError("Release manifest retired model replacement is invalid")
        retired_models.append(RetiredModel(pattern=pattern, replacement=replacement))
    return ReleaseInfo(
        version=version,
        summary=summary.strip(),
        release_url=release_url,
        min_supported_version=minimum,
        update_required=update_required,
        severity=severity,
        retired_models=tuple(retired_models),
    )


def _download_manifest(
    client: httpx.Client, url: str, headers: dict[str, str]
) -> dict[str, Any]:
    with client.stream("GET", url, headers=headers) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > 1_000_000:
                raise ValueError("Release manifest is too large")
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Release manifest is not an object")
    return value


def fetch_latest_release(client: httpx.Client | None = None) -> ReleaseInfo | None:
    owns_client = client is None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SenseNova-Skills-Update-Checker",
    }
    try:
        if client is None:
            client = httpx.Client(
                follow_redirects=True,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        response = client.get(LATEST_RELEASE_URL, headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Latest release response is not an object")
        assets = payload.get("assets", [])
        asset = next(
            (
                item
                for item in assets
                if isinstance(item, dict) and item.get("name") == MANIFEST_ASSET_NAME
            ),
            None,
        ) if isinstance(assets, list) else None
        if asset is None:
            raise ValueError("Latest release is missing sensenova-release.json")
        download_url = asset.get("browser_download_url")
        if not isinstance(download_url, str):
            raise ValueError("Release manifest asset has no download URL")
        manifest = _download_manifest(client, download_url, headers)
        return parse_release_manifest(payload, manifest)
    except (httpx.HTTPError, httpx.InvalidURL, ValueError, TypeError) as exc:
        raise UpdateCheckError(str(exc)) from exc
    finally:
        if owns_client and client is not None:
            client.close()


def _matches_model(pattern: str, model: str) -> bool:
    if "*" not in pattern:
        return pattern == model
    parts = pattern.split("*")
    if not model.startswith(parts[0]) or not model.endswith(parts[-1]):
        return False
    position = len(parts[0])
    for part in parts[1:-1]:
        index = model.find(part, position)
        if index < 0:
            return False
        position = index + len(part)
    return True


def _evaluate_release(
    local: str, release: ReleaseInfo, models: tuple[str, ...] = ()
) -> UpdateCheck:
    local_tuple = parse_version(local)
    latest_tuple = parse_version(release.version)
    if local_tuple is None or latest_tuple is None:
        return UpdateCheck(local, release.version, "unavailable")
    newer = latest_tuple > local_tuple
    reasons: list[str] = []
    remedies: list[str] = []
    replacement: str | None = None
    release_required = release.update_required or release.severity == "required"
    blocking = newer and release_required
    if blocking:
        reasons.append("the release is marked as required")
        remedies.append("install the required release")
    minimum = parse_version(release.min_supported_version or "")
    if minimum is not None and local_tuple < minimum:
        blocking = True
        reasons.append(f"the minimum supported version is {release.min_supported_version}")
        remedies.append("upgrade the installed bundle")
    for model in models:
        if not model:
            continue
        for retired in release.retired_models:
            if _matches_model(retired.pattern, model):
                blocking = True
                reasons.append(f"configured model {model!r} is retired")
                remedies.append("replace retired model configuration")
                replacement = retired.replacement or replacement
                break
    if not blocking and not newer:
        return UpdateCheck(local, release.version, "current")
    level = "required" if blocking else release.severity
    if level not in {"info", "recommended"}:
        level = "recommended"
    reason = "; ".join(reasons) or "a newer repository release is available"
    notice = UpdateNotice(
        local_version=local,
        release=release,
        level=level,
        reason=reason,
        replacement_model=replacement,
        remedies=tuple(dict.fromkeys(remedies)),
    )
    return UpdateCheck(
        local_version=local,
        latest_version=release.version,
        status="required" if blocking else "available",
        notice=notice,
    )


def _deduplicate_notice(result: UpdateCheck, notified_version: Any) -> UpdateCheck:
    if (
        result.notice is not None
        and not result.blocking
        and notified_version == result.latest_version
    ):
        return UpdateCheck(
            local_version=result.local_version,
            latest_version=result.latest_version,
            status=result.status,
        )
    return result


def check_for_updates(
    *,
    force: bool = False,
    models: tuple[str, ...] = (),
    cache_path: Path | None = None,
    base_skill_dir: Path | None = None,
    client: httpx.Client | None = None,
    now: float | None = None,
) -> UpdateCheck:
    local = local_version(base_skill_dir)
    if parse_version(local) is None:
        return UpdateCheck(local, None, "unavailable")
    path = cache_path or _cache_path(base_skill_dir)
    cache = _read_cache(path)
    timestamp = time.time() if now is None else now
    cached_release = _cached_release(cache)
    if not force and _cache_is_fresh(cache, timestamp) and cache.get("check_failed") is True:
        if cached_release is not None:
            result = _deduplicate_notice(
                _evaluate_release(local, cached_release, models),
                cache.get("notified_version"),
            )
            if result.notice is not None and not result.blocking:
                _write_cache(
                    path,
                    {
                        "checked_at": cache.get("checked_at", timestamp),
                        "release": asdict(cached_release),
                        "check_failed": True,
                        "notified_version": cached_release.version,
                    },
                )
            return result
        return UpdateCheck(local, None, "unavailable")
    release: ReleaseInfo | None = None
    fetched = False
    cache_usable = "release" in cache and (
        cache["release"] is None or cached_release is not None
    )
    if not force and _cache_is_fresh(cache, timestamp) and cache_usable:
        release = cached_release
    else:
        try:
            release = fetch_latest_release(client)
        except UpdateCheckError:
            notified_version = cache.get("notified_version")
            result = (
                _deduplicate_notice(
                    _evaluate_release(local, cached_release, models),
                    notified_version,
                )
                if cached_release is not None
                else UpdateCheck(local, None, "unavailable")
            )
            if (
                cached_release is not None
                and result.notice is not None
                and not result.blocking
            ):
                notified_version = cached_release.version
            _write_cache(
                path,
                {
                    "checked_at": timestamp,
                    "release": asdict(cached_release) if cached_release else None,
                    "check_failed": True,
                    "notified_version": notified_version,
                },
            )
            return result
        fetched = True
    if release is None:
        if cached_release is not None:
            notified_version = cache.get("notified_version")
            result = _deduplicate_notice(
                _evaluate_release(local, cached_release, models),
                notified_version,
            )
            if result.notice is not None and not result.blocking:
                notified_version = cached_release.version
            if fetched:
                _write_cache(
                    path,
                    {
                        "checked_at": timestamp,
                        "release": asdict(cached_release),
                        "check_failed": True,
                        "notified_version": notified_version,
                    },
                )
            return result
        if fetched:
            _write_cache(
                path,
                {
                    "checked_at": timestamp,
                    "release": None,
                    "check_failed": False,
                    "notified_version": cache.get("notified_version"),
                },
            )
        return UpdateCheck(local, None, "unpublished")
    result = _evaluate_release(local, release, models)
    notified_version = cache.get("notified_version")
    show_notice = result.notice is not None and (
        force or result.blocking or notified_version != release.version
    )
    if not show_notice:
        result = _deduplicate_notice(result, notified_version)
    if fetched or show_notice:
        _write_cache(
            path,
            {
                "checked_at": (
                    timestamp if fetched else cache.get("checked_at", timestamp)
                ),
                "release": asdict(release),
                "check_failed": False,
                "notified_version": (
                    release.version if show_notice else notified_version
                ),
            },
        )
    return result


def _is_symlink_path(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return path.is_symlink() or bool(
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        )
    except OSError:
        return False


def installation_kind(base_skill_dir: Path | None = None) -> str:
    base = base_skill_dir or Path(__file__).absolute().parents[2]
    if _is_symlink_path(base) or _is_symlink_path(base.parent):
        return "symlink"
    try:
        resolved = base.resolve()
        for parent in (resolved, *resolved.parents):
            if (
                (parent / ".git").exists()
                and (parent / "release.json").is_file()
                and (parent / "skills").is_dir()
                and resolved.is_relative_to(parent / "skills")
            ):
                return "git"
    except OSError:
        pass
    return "copy"


def format_update_notice(
    notice: UpdateNotice, base_skill_dir: Path | None = None
) -> str:
    release = notice.release
    labels = {
        "info": "UPDATE INFO",
        "recommended": "UPDATE RECOMMENDED",
        "required": "UPDATE REQUIRED",
    }
    label = labels.get(notice.level, "UPDATE AVAILABLE")
    lines = [
        f"[{label}] Installed {notice.local_version}; latest {release.version}.",
        f"Reason: {notice.reason}.",
        release.summary,
    ]
    if notice.replacement_model:
        lines.append(f"Suggested replacement model: {notice.replacement_model}.")
    if release.release_url:
        lines.append(f"Release notes: {release.release_url}")
    kind = installation_kind(base_skill_dir)
    if kind == "git":
        lines.append(
            "Update the source checkout with `git pull --ff-only`; for a pinned tag, "
            f"use `git fetch --tags` and "
            f"`git checkout v{release.version.lstrip('v')}`."
        )
    elif kind == "symlink":
        lines.append(
            "Update the repository behind the symlink, then reload the Agent Skills host."
        )
    else:
        lines.append(
            "Download the release, back up and replace "
            f"{', '.join(IMAGE_SKILL_NAMES)}. Preserve `.env` and custom "
            "configuration, then reload the Agent Skills host."
        )
    return "\n".join(lines)


def emit_update_check(
    *,
    force: bool = False,
    models: tuple[str, ...] = (),
    cache_path: Path | None = None,
    base_skill_dir: Path | None = None,
    client: httpx.Client | None = None,
    now: float | None = None,
    stream: Any = None,
) -> UpdateCheck:
    output = stream or sys.stderr
    disabled = os.environ.get("SN_SKILLS_NO_UPDATE_CHECK", "").strip().lower()
    if not force and disabled in {"1", "true", "yes", "on"}:
        return UpdateCheck(local_version(base_skill_dir), None, "disabled")
    result = check_for_updates(
        force=force,
        models=models,
        cache_path=cache_path,
        base_skill_dir=base_skill_dir,
        client=client,
        now=now,
    )
    if result.notice is not None:
        print(format_update_notice(result.notice, base_skill_dir), file=output)
    elif force:
        if result.status == "current":
            print(
                f"[OK] Installed version {result.local_version} is current "
                f"(latest {result.latest_version}).",
                file=output,
            )
        elif result.status == "unpublished":
            print("[INFO] No published repository release was found.", file=output)
        elif result.status == "unavailable":
            print(
                "[WARN] Repository update check unavailable; local version "
                f"{result.local_version or 'unknown'} will continue to run.",
                file=output,
            )
    return result
