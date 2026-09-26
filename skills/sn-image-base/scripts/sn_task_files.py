"""Task file manager shared by the SenseNova image skills.

Provides four subcommands over per-task directories under
``<system temp>/sensenova-tasks``:

- ``begin``   create a task directory (gc first), guarded by an ownership marker
- ``publish`` copy the selected candidate to a formal location, then remove the task directory
- ``abort``   remove the whole task directory on failure or cancellation
- ``gc``      collect expired task directories (marked, unmarked, or half-created)

Only directories created by ``begin`` with a valid ownership marker may be
published or aborted; ``gc`` additionally collects unmarked leftovers older
than the retention threshold. API keys never enter markers, logs, or files.

Usage:
    python sn_task_files.py begin
    python sn_task_files.py publish <task-dir> <selected-image> [--final-path <target>]
    python sn_task_files.py abort <task-dir>
    python sn_task_files.py gc
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

SCRIPT_DIR = Path(__file__).resolve().parent
if (d := str(SCRIPT_DIR)) not in sys.path:
    sys.path.insert(0, d)

from sn_image_base.configs import default_formal_output_dir
from sn_image_base.image_utils import MAX_IMAGE_BYTES, validate_image_file

TASKS_DIRNAME = "sensenova-tasks"
LOCK_DIRNAME = ".locks"
MARKER_NAME = ".sensenova-task.json"
MARKER_FORMAT_VERSION = 1
DEFAULT_RETENTION_HOURS = 48
STAGING_PREFIX = ".begin-"


def _root_dirname(platform: str, uid: int | None) -> str:
    """Per-user root name.

    POSIX temporary directories are shared between local users, so the root is
    scoped by uid and created with owner-only permissions; the Windows user
    temp directory is already private, so the plain name is kept.
    """
    if platform == "nt":
        return TASKS_DIRNAME
    return f"{TASKS_DIRNAME}-{uid}" if uid is not None else TASKS_DIRNAME


def task_root(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    uid = os.getuid() if hasattr(os, "getuid") else None
    return Path(tempfile.gettempdir()) / _root_dirname(os.name, uid)


def retention_hours() -> int:
    raw = os.environ.get("SN_TASK_RETENTION_HOURS", "").strip()
    return int(raw) if raw else DEFAULT_RETENTION_HOURS


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_reparse(path: Path) -> bool:
    """True for symlinks, junctions, and reparse points; missing paths count as plain."""
    if path.is_symlink():
        return True
    if os.name == "nt":
        try:
            st = os.lstat(path)
        except OSError:
            return False
        return bool(st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    return False


def _read_marker(task_dir: Path) -> dict[str, Any] | None:
    try:
        data = json.loads((task_dir / MARKER_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("format_version") != MARKER_FORMAT_VERSION:
        return None
    return data


def _marker_owns(child: Path, marker: dict[str, Any]) -> bool:
    """A marker only vouches for the directory it was created for."""
    return marker.get("task_id") == child.name


def _created_at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _mtime_of(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(os.lstat(path).st_mtime, timezone.utc)
    except OSError:
        return None


def _lock_path(task_dir: Path) -> Path:
    """Lock files live outside the task directory, under the shared lock root."""
    return task_dir.parent / LOCK_DIRNAME / f"{task_dir.name}.lock"


def _discard_lock_file(task_dir: Path) -> None:
    try:
        _lock_path(task_dir).unlink(missing_ok=True)
    except OSError:
        pass  # an orphaned lock file is swept by the next gc


def _iter_tree(root: Path):
    """Yield every entry under ``root`` (inclusive) without following links.

    Junctions and reparse points are yielded but never descended into, so a
    self-referencing link cannot cause an endless walk and external targets
    cannot influence the activity estimate.
    """
    stack = [root]
    while stack:
        current = stack.pop()
        yield current
        if _is_reparse(current):
            continue
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    yield path
                    if entry.is_dir(follow_symlinks=False) and not _is_reparse(path):
                        stack.append(path)
        except OSError:
            continue


def _newest_activity(child: Path) -> datetime:
    """Latest evidence that this directory was still in use.

    Sources: the creation time of an ownership marker that matches the
    directory name, plus the modification time of every entry under the
    directory (lstat, links not followed). Rewriting an existing prompt or
    image refreshes that file's own modification time, so an in-progress task
    keeps the estimate fresh even when only existing files change; a
    directory is collected only after this whole set has been inactive for
    the retention window. A marker whose task ID does not match the
    directory name vouches for nothing.
    """
    candidates: list[datetime] = []
    marker = _read_marker(child)
    if marker is not None and _marker_owns(child, marker):
        created = _created_at(marker.get("created_at"))
        if created is not None:
            candidates.append(created)
    for path in _iter_tree(child):
        mtime = _mtime_of(path)
        if mtime is not None:
            candidates.append(mtime)
    return max(candidates) if candidates else datetime.now(timezone.utc)


_RETRYING_PATHS: set[str] = set()


def _on_rmtree_error(func, path, exc):
    """Retry a permission-blocked entry once with owner access; re-raise otherwise.

    ``shutil`` reports ``(func, path, exc)`` on 3.12+ and ``(func, path,
    exc_info)`` before that. The entry is inspected with ``lstat`` so a
    symlink is never followed: deleting one depends on its parent directory,
    never on the link target, and chmod must not silently change the
    permissions of a user's own file outside the task tree. Directories need
    their read and execute bits back (write-only access cannot be traversed).
    ``func`` may be ``os.open``: the caller failed to open the entry and would
    otherwise skip it silently, so the deletion is retried here instead.
    """
    if isinstance(exc, tuple):  # legacy onerror passes sys.exc_info()
        exc = exc[1]
    if not isinstance(exc, PermissionError):
        raise exc
    try:
        st = os.lstat(path)
    except OSError:
        raise exc
    if stat.S_ISLNK(st.st_mode):
        parent = os.path.dirname(os.fspath(path))
        try:
            os.chmod(parent, 0o700)
        except OSError:
            raise exc
        if func is os.unlink:
            func(path)
        else:
            raise exc
        return
    try:
        os.chmod(path, 0o700 if stat.S_ISDIR(st.st_mode) else 0o600)
    except OSError:
        raise exc
    if func is os.open:
        key = os.fspath(path)
        if key in _RETRYING_PATHS:
            raise exc
        _RETRYING_PATHS.add(key)
        try:
            _rmtree(Path(path))
        finally:
            _RETRYING_PATHS.discard(key)
    else:
        func(path)


def _rmtree(path: Path) -> None:
    kwargs = {"onexc": _on_rmtree_error} if sys.version_info >= (3, 12) else {"onerror": _on_rmtree_error}
    shutil.rmtree(path, **kwargs)


def _acquire_lock(lock_path: Path):
    """Return an open exclusively-locked handle, or None when a task holds it.

    The lock lives in its own file: locking the ownership marker would block
    Windows readers of the locked byte range, hiding the marker from gc.
    """
    try:
        handle = open(lock_path, "r+b")
    except OSError:
        return None
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def _release_lock(handle) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        handle.close()


def _release_quietly(handle) -> None:
    try:
        _release_lock(handle)
    except OSError:
        pass


def _acquire_task_lock(task_dir: Path):
    """Lock a task directory, failing fast when another process holds it.

    Lock files live in a sibling ``.locks`` directory: Windows cannot rename or
    unlink files inside a directory that holds open handles, so an in-directory
    lock could never stay held across the deletion it is meant to protect.
    Returns the handle, or None when the directory has no lock file (foreign or
    legacy directories).
    """
    lock_path = _lock_path(task_dir)
    if _is_reparse(lock_path):
        raise OSError(f"Lock file must not be a symlink, junction, or reparse point: {lock_path}")
    if not lock_path.is_file():
        return None
    handle = _acquire_lock(lock_path)
    if handle is None:
        raise OSError(f"Task directory is locked by another process: {task_dir}")
    return handle


def _in_root(child: Path, root_resolved: Path) -> bool:
    try:
        return child.resolve().parent == root_resolved
    except OSError:
        return False


def _require_plain_root(root: Path) -> Path:
    """Resolve the task root, refusing a root that is itself a link.

    A linked root would make the scan and the deletions inside it operate on
    the link target, so it is rejected before anything is read or removed.
    """
    if _is_reparse(root):
        raise ValueError(f"Task root must not be a symlink, junction, or reparse point: {root}")
    if root.exists() and not root.is_dir():
        raise ValueError(f"Task root is not a directory: {root}")
    return root.resolve()


def _root_is_private(st_uid: int, st_mode: int, uid: int) -> bool:
    """True when the root belongs to this user and grants no group/other access."""
    return st_uid == uid and not (st_mode & 0o077)


def _require_private_root(root_resolved: Path) -> None:
    """POSIX: refuse a task root that cannot be made owner-only.

    POSIX temporary directories are shared, so another local user can
    pre-create the predictable root path. Unless the root is owned by this
    user and free of group/other access (existing roots are tightened first),
    reading or writing task files through it could leak prompts and analysis
    files, so the operation is refused instead.
    """
    if os.name == "nt" or not hasattr(os, "getuid") or not root_resolved.exists():
        return
    uid = os.getuid()
    try:
        st = os.lstat(root_resolved)
        if not _root_is_private(st.st_uid, st.st_mode, uid):
            os.chmod(root_resolved, 0o700)
            st = os.lstat(root_resolved)
    except OSError as exc:
        raise ValueError(
            f"Task root {root_resolved} cannot be secured for this user: {exc}"
        ) from exc
    if not _root_is_private(st.st_uid, st.st_mode, uid):
        raise ValueError(
            f"Task root {root_resolved} is not owned by this user or remains accessible "
            "to others; refusing to store task files there"
        )


def _require_plain_locks_dir(root_resolved: Path) -> Path:
    """Validate the lock directory, refusing a link or a non-directory.

    Lock files are created and unlinked through this path, so a linked or
    replaced ``.locks`` entry would place those operations outside the
    dedicated root.
    """
    locks_dir = root_resolved / LOCK_DIRNAME
    if _is_reparse(locks_dir):
        raise ValueError(
            f"Lock directory must not be a symlink, junction, or reparse point: {locks_dir}"
        )
    if locks_dir.exists() and not locks_dir.is_dir():
        raise ValueError(f"Lock directory is not a directory: {locks_dir}")
    return locks_dir


def _collect_expired(child: Path, root_resolved: Path, threshold: datetime, report: dict[str, list]) -> None:
    """Collect one inactive candidate while holding its lock end to end.

    The lock spans the activity re-check and the deletion, so a concurrent
    publish or abort either wins the lock first (this scan skips the
    directory) or finds the directory already gone. Deleting under the lock is
    possible because the lock file lives outside the task directory.
    """
    lock_path = _lock_path(child)
    if _is_reparse(lock_path):
        report["skipped"].append(str(child))
        return
    handle = _acquire_lock(lock_path) if lock_path.is_file() else None
    if handle is None and lock_path.is_file():
        report["kept"].append(str(child))
        return
    try:
        if not child.is_dir() or _is_reparse(child) or not _in_root(child, root_resolved):
            report["skipped"].append(str(child))
            return
        if _newest_activity(child) > threshold:
            report["kept"].append(str(child))
            return
        try:
            _rmtree(child)
        except FileNotFoundError as exc:
            if child.exists():
                report["errors"].append(f"{child}: removal aborted on a vanished entry: {exc}")
                return
        except OSError as exc:
            report["errors"].append(f"{child}: {exc}")
            return
    finally:
        if handle is not None:
            _release_quietly(handle)
    if child.exists():
        report["errors"].append(f"{child}: still exists after removal")
        return
    _discard_lock_file(child)
    report["removed"].append(str(child))


def _sweep_lock_files(root_resolved: Path, report: dict[str, list]) -> None:
    """Remove expired lock files whose task directory no longer exists.

    A lock file is only orphaned once it is older than the retention window:
    during ``begin`` the lock file is created just before the task directory,
    so a freshly created lock without a directory may belong to a task that is
    still being created and must never be swept by a concurrent run.
    """
    locks_dir = root_resolved / LOCK_DIRNAME
    if not locks_dir.is_dir() or _is_reparse(locks_dir):
        return
    threshold = datetime.now(timezone.utc) - timedelta(hours=retention_hours())
    for entry in sorted(locks_dir.iterdir()):
        if not entry.is_file() or entry.suffix != ".lock" or _is_reparse(entry):
            continue
        if (root_resolved / entry.stem).exists():
            continue
        mtime = _mtime_of(entry)
        if mtime is None or mtime > threshold:
            report["kept"].append(str(entry))
            continue
        handle = _acquire_lock(entry)
        if handle is None:
            report["kept"].append(str(entry))
            continue
        _release_quietly(handle)
        try:
            entry.unlink(missing_ok=True)
            report["locks_removed"].append(str(entry))
        except OSError as exc:
            report["errors"].append(f"{entry}: {exc}")


def _collect_stale_staging(child: Path, threshold: datetime, report: dict[str, list]) -> None:
    """Collect a leftover staging directory without scanning it.

    A live ``begin`` renames its staging directory into place within
    milliseconds; walking it here (or deleting it by a fresh timestamp) would
    race with that rename. Only the directory's own timestamp is inspected,
    so just crashed leftovers qualify.
    """
    if not child.is_dir():
        return  # vanished (renamed into place) or not a directory
    if _is_reparse(child):
        report["skipped"].append(str(child))
        return
    mtime = _mtime_of(child)
    if mtime is None or mtime > threshold:
        return
    try:
        _rmtree(child)
    except FileNotFoundError as exc:
        if child.exists():
            report["errors"].append(f"{child}: removal aborted on a vanished entry: {exc}")
        # else: a concurrent begin renamed it into its final name instead
        return
    except OSError as exc:
        report["errors"].append(f"{child}: {exc}")
        return
    if child.exists():
        report["errors"].append(f"{child}: still exists after removal")
        return
    report["removed"].append(str(child))


def gc(root: Path | None = None) -> dict[str, list]:
    """Collect task directories that have been inactive for the retention window."""
    report: dict[str, list] = {"removed": [], "kept": [], "skipped": [], "errors": [], "locks_removed": []}
    root_resolved = _require_plain_root(task_root(root))
    if not root_resolved.is_dir():
        return report
    _require_private_root(root_resolved)
    _require_plain_locks_dir(root_resolved)
    threshold = datetime.now(timezone.utc) - timedelta(hours=retention_hours())
    for child in sorted(root_resolved.iterdir()):
        if child.name == LOCK_DIRNAME:
            continue
        if child.name.startswith(STAGING_PREFIX):
            _collect_stale_staging(child, threshold, report)
            continue
        if not child.is_dir():
            report["skipped"].append(str(child))
            continue
        if _is_reparse(child) or not _in_root(child, root_resolved):
            report["skipped"].append(str(child))
            continue
        if _newest_activity(child) > threshold:
            continue
        _collect_expired(child, root_resolved, threshold, report)
    _sweep_lock_files(root_resolved, report)
    return report


def begin(root: Path | None = None) -> Path:
    """Create a guarded task directory (running gc first) and return its path.

    Everything that can fail runs before the staging directory is renamed, so
    a failure never leaves a task directory behind: the lock directory is
    validated and the lock file is created first, and the final atomic rename
    is the last operation.
    """
    root_resolved = _require_plain_root(task_root(root))
    gc(root=root_resolved)
    root_resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    _require_private_root(root_resolved)
    locks_dir = _require_plain_locks_dir(root_resolved)
    locks_dir.mkdir(exist_ok=True)
    task_id = uuid4().hex
    lock_path = locks_dir / f"{task_id}.lock"
    lock_path.touch()
    staging = root_resolved / f"{STAGING_PREFIX}{task_id}"
    final = root_resolved / task_id
    try:
        marker = {
            "format_version": MARKER_FORMAT_VERSION,
            "task_id": task_id,
            "created_at": _utc_now_iso(),
        }
        staging.mkdir()
        marker_path = staging / MARKER_NAME
        with open(marker_path, "w", encoding="utf-8") as handle:
            json.dump(marker, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(staging, final)
    except Exception:
        # Rollback failures must stay visible: a silently kept staging
        # directory or lock file would look like a clean failure.
        if staging.is_dir() and not _is_reparse(staging):
            try:
                _rmtree(staging)
            except OSError as cleanup_exc:
                print(
                    f"Warning: could not remove staging directory {staging}: {cleanup_exc}",
                    file=sys.stderr,
                )
        try:
            lock_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            print(f"Warning: could not remove lock file {lock_path}: {cleanup_exc}", file=sys.stderr)
        raise
    return final


def _unique_name(selected: Path) -> str:
    suffix = selected.suffix or ".png"
    return f"{selected.stem}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{suffix}"


def publish(
    task_dir: Path | str,
    selected_image: Path | str,
    *,
    final_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    root: Path | None = None,
) -> Path:
    """Copy the selected image to its formal destination, then remove the task directory.

    Raises without touching the formal destination when validation fails; the
    task directory stays intact for a retry. Returns the formal path.
    """
    resolved_task = _require_owned_dir(Path(task_dir), root)
    lock = _acquire_task_lock(resolved_task)
    temp_path: Path | None = None
    try:
        try:
            selected = Path(selected_image).resolve()
            if not selected.is_relative_to(resolved_task):
                raise ValueError(f"Selected image must live inside the task directory: {selected}")
            if not selected.is_file():
                raise ValueError(f"Selected image does not exist: {selected}")
            if selected.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError(f"Selected image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MiB limit.")
            validate_image_file(selected)

            if final_path is not None:
                final = Path(final_path).expanduser()
                target_dir = final.parent
            else:
                target_dir = Path(output_dir).expanduser() if output_dir else default_formal_output_dir()
                final = target_dir / _unique_name(selected)
            target_resolved = target_dir.resolve()
            if target_resolved.is_relative_to(resolved_task):
                raise ValueError(f"Formal target must live outside the task directory: {target_dir}")
            target_resolved.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                dir=target_resolved, prefix=f".{final.name}.", suffix=".tmp", delete=False
            ) as temporary:
                temp_path = Path(temporary.name)
                temporary.write(selected.read_bytes())
                temporary.flush()
                os.fsync(temporary.fileno())
            validate_image_file(temp_path)
            os.replace(temp_path, final)
            temp_path = None
            if not final.is_file() or final.stat().st_size != selected.stat().st_size:
                raise OSError(f"Formal image verification failed after publish: {final}")
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

        # Deletion stays inside the locked critical section: the lock file lives
        # outside the task directory, so it can remain held while the directory
        # is removed. A concurrent gc therefore either wins the lock first
        # (publish fails fast and retries) or finds the directory already gone.
        try:
            _rmtree(resolved_task)
        except FileNotFoundError as exc:
            if resolved_task.exists():
                raise OSError(
                    f"Published to {final}, but removal aborted on a vanished entry and the "
                    f"task directory still exists: {exc}"
                ) from exc
        except OSError as exc:
            raise OSError(
                f"Published to {final}, but the task directory could not be removed: {exc}"
            ) from exc
        if resolved_task.exists():
            raise OSError(
                f"Published to {final}, but the task directory still exists after removal: "
                f"{resolved_task}"
            )
    finally:
        if lock is not None:
            _release_quietly(lock)
    _discard_lock_file(resolved_task)
    return final


def abort(task_dir: Path | str, root: Path | None = None) -> Path:
    """Remove a guarded task directory after failure or cancellation."""
    resolved = _require_owned_dir(Path(task_dir), root)
    lock = _acquire_task_lock(resolved)
    try:
        _rmtree(resolved)
    except FileNotFoundError as exc:
        if resolved.exists():
            raise OSError(
                f"Failed to remove the task directory {resolved}: removal aborted on a "
                f"vanished entry and the directory still exists"
            ) from exc
    except OSError as exc:
        raise OSError(f"Failed to remove the task directory {resolved}: {exc}") from exc
    else:
        if resolved.exists():
            raise OSError(
                f"Failed to remove the task directory {resolved}: it still exists after removal"
            )
    finally:
        if lock is not None:
            _release_quietly(lock)
    _discard_lock_file(resolved)
    return resolved


def _require_owned_dir(task_dir: Path, root: Path | None = None) -> Path:
    root_resolved = _require_plain_root(task_root(root))
    if not root_resolved.is_dir():
        raise ValueError(f"Task root does not exist: {root_resolved}")
    _require_private_root(root_resolved)
    _require_plain_locks_dir(root_resolved)
    if _is_reparse(task_dir):
        raise ValueError(f"Task directory must not be a symlink, junction, or reparse point: {task_dir}")
    resolved = task_dir.resolve()
    if resolved.parent != root_resolved:
        raise ValueError(
            f"Task directory must be a direct child of the task root {root_resolved}: {task_dir}"
        )
    if not resolved.is_dir():
        raise ValueError(f"Task directory does not exist: {resolved}")
    if _is_reparse(resolved):
        raise ValueError(f"Task directory must not be a symlink, junction, or reparse point: {resolved}")
    marker = _read_marker(resolved)
    if marker is None:
        raise ValueError(f"Missing or invalid ownership marker in task directory: {resolved}")
    if marker.get("task_id") != resolved.name:
        raise ValueError(
            f"Ownership marker task ID {marker.get('task_id')!r} does not match directory name {resolved.name!r}"
        )
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SenseNova skill task file manager")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-o", "--output-format", choices=["text", "json"], default="text")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "begin", parents=[common], help="Create a guarded task directory and print its path"
    )

    publish_parser = subparsers.add_parser(
        "publish", parents=[common], help="Deliver the selected image and clean up"
    )
    publish_parser.add_argument("task_dir", help="Task directory created by begin")
    publish_parser.add_argument("image", help="Selected image inside the task directory")
    publish_parser.add_argument("--final-path", default=None, help="Explicit formal destination path")

    abort_parser = subparsers.add_parser(
        "abort", parents=[common], help="Remove a failed or cancelled task directory"
    )
    abort_parser.add_argument("task_dir", help="Task directory created by begin")

    subparsers.add_parser("gc", parents=[common], help="Collect expired task directories")
    return parser


def _emit(output_format: str, payload: dict) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False))
        return
    for key, value in payload.items():
        if isinstance(value, list):
            for item in value:
                print(f"{key}: {item}")
        elif isinstance(value, dict):
            _emit(output_format, value)
        else:
            print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "begin":
            task_dir = begin()
            _emit(args.output_format, {"task_dir": str(task_dir)})
        elif args.command == "publish":
            final = publish(args.task_dir, args.image, final_path=args.final_path)
            _emit(args.output_format, {"final_path": str(final), "task_dir_removed": True})
        elif args.command == "abort":
            removed = abort(args.task_dir)
            _emit(args.output_format, {"task_dir": str(removed), "removed": True})
        elif args.command == "gc":
            _emit(args.output_format, gc())
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 1
        return 0
    except (OSError, ValueError) as exc:
        if args.output_format == "json":
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
