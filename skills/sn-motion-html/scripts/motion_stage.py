#!/usr/bin/env python3
"""Stage executor for the sn-motion-html review gates.

Standard library only. This is the controlled entry point for story image
calls: it reads ``.motion-state/review.json``, checks the current phase, the
approval scope, and every requested target, and only then calls the existing
SenseNova runner. Every rejection happens before a provider request, so a
blocked batch reports ``provider_calls: 0``.

Honest scope of the guarantee: this is a program check at the normal entry
point, not an unblockable host gate. An Agent with arbitrary shell access, the
ability to edit the state file, or direct credentials can bypass it, and a
decision transcribed from the conversation is recorded as ``agent-recorded``
trust, which cannot prove a real user event. There is deliberately no
``--yes``, ``--force``, or ``--approved`` escape: a direct-completion
delegation is expressed as a scoped decision record, never as a bypass flag.

Exit codes: 0 = allowed and completed, 2 = blocked by a gate, 1 = bad input or
a state/project problem.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_model import (  # noqa: E402
    ProjectError,
    chapters_of,
    load_story,
    relative_media_path,
    resolve_media_mode,
    validate_story,
)

SCHEMA_VERSION = 3
WORKFLOW_PROTOCOL = 2
STATE_REL = ".motion-state/review.json"
LOCK_REL = ".motion-state/review.lock"

PHASES = (
    "drafting",
    "awaiting_story_review",
    "sampling",
    "awaiting_visual_review",
    "producing",
    "delivered",
)
COPY_FIELDS = ("label", "eyebrow", "title", "subtitle")
SHOT_FIELDS = ("intent", "framing", "motionNote")
META_FIELDS = ("title", "kicker", "subtitle", "note", "style", "ui", "lang")
TRUST_LEVELS = ("agent-recorded", "host-verified")
DECISION_SCOPES = ("story", "visual", "revision", "delegation")
DELEGATION_STAGES = ("story", "visual")

# Deltas that no per-chapter revision can authorize: a reordered or added or
# removed chapter list, a new style basis, or a change in the story metadata.
# Each one retires the shown package and needs a fresh confirmation.
STRUCTURE_DELTA = "<structure>"
STYLE_DELTA = "<style>"
META_DELTA = "<meta>"

IMAGE_MODEL = "sensenova-u1.5-lite"
DEFAULT_IMAGE_SIZE = "4k"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_CALL_TIMEOUT = 900
# The runner names the file it writes from the requested format
# (save_path.with_suffix(MIME_SUFFIX[mime])), so a page asset declared as
# .webp is never what a png generation call produces. Generation always targets
# the lossless master; make_posters.py derives the page copy locally.
MASTER_SUFFIX = ".png"
PAGE_SUFFIXES = frozenset({".webp", ".jpg", ".jpeg", ".avif"})


class StageError(RuntimeError):
    """A bad request or a broken project/state the operator must fix."""


class Blocked(RuntimeError):
    """A gate refusal. Reported as structured JSON with zero provider calls."""

    def __init__(self, reason: str, allowed_action: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.allowed_action = allowed_action
        self.detail = detail or reason


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --- effective content digests ---------------------------------------------
# Digests only detect change. Whitespace, JSON formatting, key order, log
# timestamps, and state fields never invalidate a creative confirmation, while
# a real content or file change always does.


def effective_chapters(story: dict) -> list[dict]:
    entries: list[dict] = []
    for chapter in chapters_of(story):
        entry: dict = {
            "id": str(chapter.get("id") or ""),
            "copy": {key: chapter.get(key) for key in COPY_FIELDS if chapter.get(key)},
            "paragraphs": [str(item) for item in (chapter.get("paragraphs") or [])],
            "tags": [str(item) for item in (chapter.get("tags") or [])],
            "still": chapter.get("still"),
        }
        shot = chapter.get("shot")
        if isinstance(shot, dict):
            entry["shot"] = {
                key: shot[key].strip()
                for key in SHOT_FIELDS
                if isinstance(shot.get(key), str) and shot[key].strip()
            }
        entries.append(entry)
    return entries


def chapter_order(story: dict) -> list[str]:
    return [entry["id"] for entry in effective_chapters(story)]


def chapter_digest_map(story: dict) -> dict[str, str]:
    """Per-chapter digests of the copy and shot only.

    The style basis and the chapter order are compared separately so a global
    style change or a reorder cannot be waved through by authorizing chapters
    one at a time.
    """
    return {entry["id"]: sha256_text(canonical(entry)) for entry in effective_chapters(story)}


def style_basis_digest(root: Path) -> str | None:
    return sha256_file(root / "prompts" / "style-preamble.txt")


def story_digest(root: Path, story: dict, sample_ids: list[str]) -> str:
    payload = {
        "meta": meta_digest(story),
        "order": chapter_order(story),
        "chapters": effective_chapters(story),
        "style_basis": style_basis_digest(root),
        "sample_ids": list(sample_ids),
    }
    return sha256_text(canonical(payload))


def meta_digest(story: dict) -> str:
    meta = story.get("meta") if isinstance(story.get("meta"), dict) else {}
    return sha256_text(canonical({key: meta.get(key) for key in META_FIELDS if meta.get(key)}))


def content_baseline(root: Path, story: dict, sample_ids: list[str]) -> dict:
    """Everything a shown review package must remember about the content.

    Order, per-chapter copy, the style basis, and the story metadata are recorded
    apart, so a refusal can name the dimension that actually moved and a scoped
    revision can cover one chapter without hiding a different kind of change.
    """
    return {
        "story_digest": story_digest(root, story, sample_ids),
        "chapter_order": chapter_order(story),
        "chapter_digests": chapter_digest_map(story),
        "style_basis": style_basis_digest(root),
        "meta_digest": meta_digest(story),
        "sample_ids": list(sample_ids),
    }


def master_rel(declared: str) -> str:
    """The lossless master beside a declared still path.

    A page asset declared as WebP or JPEG has a ``.png`` master; a chapter that
    already declares a PNG loads its own master, so nothing is duplicated.
    """
    path = PurePosixPath(declared)
    if path.suffix.lower() in PAGE_SUFFIXES:
        return str(path.with_suffix(MASTER_SUFFIX))
    return declared


def declared_still(story: dict, chapter_id: str) -> str | None:
    """The chapter's declared still path, in the authored forward-slash form."""
    for chapter in chapters_of(story):
        if str(chapter.get("id")) == chapter_id and chapter.get("still"):
            return str(chapter["still"]).replace("\\", "/")
    return None


def real_asset_path(root: Path, declared: str) -> Path | None:
    """Whether the chapter has any usable file: the page copy, else its master."""
    page = relative_media_path(root, declared)
    if page.is_file():
        return page
    master = relative_media_path(root, master_rel(declared))
    return master if master.is_file() else None


def accepted_asset(root: Path, declared: str) -> Path | None:
    """The file that carries the accepted image: the master whenever there is one.

    A page copy is derived from the master by ``make_posters.py``, so identifying a
    sample by the page asset would let local compression look like a replaced
    image and retire confirmation B. A supplied WebP-only project has no master,
    and there the page file is the accepted original.
    """
    master = relative_media_path(root, master_rel(declared))
    if master.is_file():
        return master
    page = relative_media_path(root, declared)
    return page if page.is_file() else None


def page_copy_is_stale(page: Path, master: Path) -> bool:
    """Whether the derived page asset predates the master it came from.

    Existence alone is not freshness: after an authorized replacement the PNG
    master is new while the WebP the page still loads is the old picture, and
    shipping that would deliver a page showing an image nobody approved.
    """
    if not page.is_file() or not master.is_file():
        return False
    try:
        return master.stat().st_mtime > page.stat().st_mtime
    except OSError:
        return False


def production_needs(root: Path, story: dict) -> tuple[list[str], list[str], list[str]]:
    """(needs_generation, needs_page_copy, ready) over the chapter order."""
    generate: list[str] = []
    page_copy: list[str] = []
    ready: list[str] = []
    for chapter in chapters_of(story):
        declared = str(chapter.get("still") or "")
        if not declared:
            continue
        try:
            page = relative_media_path(root, declared)
            master = relative_media_path(root, master_rel(declared))
        except ProjectError:
            continue
        if page.is_file():
            # The declared page asset exists; it is only current if it is not
            # older than the master it was compressed from.
            if page_copy_is_stale(page, master):
                page_copy.append(str(chapter.get("id")))
            else:
                ready.append(str(chapter.get("id")))
        elif master.is_file():
            # The master exists but the declared page asset does not: a local
            # make_posters.py run creates it, never another image-model call.
            page_copy.append(str(chapter.get("id")))
        else:
            generate.append(str(chapter.get("id")))
    return generate, page_copy, ready


def sample_assets(root: Path, story: dict, sample_ids: list[str]) -> list[dict]:
    assets: list[dict] = []
    for chapter_id in sample_ids:
        declared = declared_still(story, chapter_id) or ""
        try:
            real = accepted_asset(root, declared) if declared else None
            digest = sha256_file(real) if real else None
            resolved = real.relative_to(root).as_posix() if real else None
        except ProjectError:
            digest, resolved = None, None
        assets.append({"id": chapter_id, "still": declared, "master": master_rel(declared) if declared else None, "file": resolved, "sha256": digest})
    return assets


def visual_digest(assets: list[dict], basis: str | None) -> str:
    return sha256_text(canonical({"samples": assets, "style_basis": basis}))


# --- state -----------------------------------------------------------------


def state_path(root: Path) -> Path:
    return root / STATE_REL


def load_state(root: Path) -> dict | None:
    path = state_path(root)
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StageError(f"{STATE_REL} is not valid JSON: {exc}") from exc
    if not isinstance(state, dict):
        raise StageError(f"{STATE_REL} must be a JSON object")
    stored = state.get("workflow_protocol")
    if stored != WORKFLOW_PROTOCOL:
        raise Blocked(
            "protocol_mismatch",
            "verify_loaded_skill_version",
            f"state records workflow_protocol {stored!r}, this executor implements {WORKFLOW_PROTOCOL}",
        )
    return state


def save_state(root: Path, state: dict) -> None:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
    payload = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), prefix=".review-", suffix=".tmp", delete=False
    )
    try:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
    except BaseException:
        handle.close()
        Path(handle.name).unlink(missing_ok=True)
        raise
    os.replace(handle.name, path)


def lock_descriptor(lock: Path) -> dict | None:
    """Best-effort record of who last wrote the lock file, for reporting only.

    Ownership is decided by the OS lock, never by this content, so a descriptor
    that lags a just-started holder can mislead nobody: it is never used to let
    anyone in or to evict anyone.
    """
    try:
        parsed = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def lock_file(handle) -> bool:
    """Take the exclusive OS lock on an open lock file, without blocking."""
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def unlock_file(handle) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def project_lock(root: Path):
    """Single-project mutex so two processes cannot spend one authorization.

    Ownership is an exclusive lock the operating system grants to this process
    and releases the moment it exits, however it exits. That is what makes the
    handover race-free: there is no stale file to compare, no age to judge, and
    nothing to unlink, so a recovering process can never delete a live holder's
    lock or slip in beside it. The file is kept only as a readable descriptor of
    whoever holds it now, and it is never removed.
    """
    lock = root / LOCK_REL
    lock.parent.mkdir(parents=True, exist_ok=True)
    handle = os.fdopen(os.open(lock, os.O_CREAT | os.O_RDWR), "r+", encoding="utf-8")
    try:
        if not lock_file(handle):
            holder = lock_descriptor(lock) or {}
            who = f" (pid {holder.get('pid')} since {holder.get('at')})" if holder.get("pid") else ""
            raise Blocked(
                "project_locked",
                "wait_for_the_holding_process_then_read_status",
                f"{LOCK_REL} is locked by another running process{who}; the operating system releases it when "
                "that process exits, so wait for it and retry instead of removing the file",
            )
        handle.seek(0)
        handle.truncate(0)
        handle.write(json.dumps({"pid": os.getpid(), "at": now_iso()}))
        handle.flush()
        os.fsync(handle.fileno())
        yield
    finally:
        unlock_file(handle)
        handle.close()


def read_project(root: Path) -> dict:
    try:
        story = load_story(root)
    except ProjectError as exc:
        raise StageError(str(exc)) from exc
    try:
        mode = resolve_media_mode(story)
    except ProjectError as exc:
        raise StageError(str(exc)) from exc
    problems = validate_story(root, story, mode)
    if problems:
        raise StageError("content/story.json is invalid: " + "; ".join(problems[:6]))
    if mode != "images":
        raise StageError(
            "the stage executor gates image production; a video project runs clips through scripts/agnes_video.py"
        )
    return story


def ensure_state(root: Path, story: dict) -> dict:
    state = load_state(root)
    if state is None:
        meta = story.get("meta") if isinstance(story.get("meta"), dict) else {}
        state = {
            "schema_version": SCHEMA_VERSION,
            "workflow_protocol": WORKFLOW_PROTOCOL,
            "project_id": uuid.uuid4().hex[:16],
            "binding": {"root": str(root.resolve()), "title": str(meta.get("title") or "")},
            "interaction_mode": "collaborative",
            "phase": "drafting",
            "story_review": None,
            "visual_review": None,
            "revision": None,
            "approvals": [],
            "operations": [],
            "generation_limits": {},
            "created_at": now_iso(),
        }
    elif (state.get("binding") or {}).get("root") != str(root.resolve()):
        raise Blocked(
            "state_project_mismatch",
            "use_the_state_owning_project_or_start_fresh_review",
            "this .motion-state/review.json belongs to a different project directory; "
            "another project's acceptance never transfers",
        )
    state.setdefault("approvals", [])
    state.setdefault("operations", [])
    return state


def package_id(kind: str, project_id: str, digest: str) -> str:
    return f"{kind}-{project_id[:8]}-{digest[:12]}"


def latest_approval(state: dict, scope: str, package: str | None = None) -> dict | None:
    """The newest decision recorded for a scope: the one that stands.

    Looking for "any accept ever recorded" would let a withdrawn approval keep
    authorizing production after the user asked for changes.
    """
    for approval in reversed(state.get("approvals", [])):
        if approval.get("scope") != scope:
            continue
        if package is None or approval.get("package") == package:
            return approval
    return None


def accepted(state: dict, scope: str, package: str | None) -> bool:
    if not package:
        return False
    approval = latest_approval(state, scope, package)
    return bool(approval and approval.get("decision") == "accept")


def delegation_covers(state: dict, stage: str) -> bool:
    """Whether a standing delegation still covers this wait.

    A delegation only has the last word until the user speaks about that stage
    again: an explicit changes-requested recorded after it retires the
    wait-skipping too, so the run stops at the real gate.
    """
    approvals = state.get("approvals", [])
    for index in range(len(approvals) - 1, -1, -1):
        approval = approvals[index]
        if approval.get("scope") != "delegation" or stage not in (approval.get("stages") or []):
            continue
        if approval.get("decision") != "accept":
            return False
        return not any(
            later.get("scope") == stage and later.get("decision") != "accept"
            for later in approvals[index + 1 :]
        )
    return False


def withdrawn_revision_ids(state: dict) -> set:
    """Revision authorizations the user has since withdrawn.

    A withdrawal names the revision id it retires, so the earlier accept stays on
    record and the withdrawal is what stands.
    """
    return {
        approval.get("revision_id")
        for approval in state.get("approvals", [])
        if approval.get("scope") == "revision"
        and approval.get("decision") != "accept"
        and approval.get("revision_id")
    }


def matching_revision(
    state: dict, package: str | None, chapter_id: str, digest: str | None = None
) -> dict | None:
    """The newest revision authorizing this chapter in this package, if it still fits.

    Binding the check to the digest recorded when the decision was made means one
    approved copy edit cannot become a standing exemption for whatever that
    chapter is later turned into.
    """
    withdrawn = withdrawn_revision_ids(state)
    for approval in reversed(state.get("approvals", [])):
        if approval.get("scope") != "revision" or approval.get("decision") != "accept":
            continue
        if approval.get("revision_id") in withdrawn:
            continue
        if package not in (approval.get("packages") or []) or chapter_id not in (approval.get("stages") or []):
            continue
        if digest is None or (approval.get("digests") or {}).get(chapter_id) == digest:
            return approval
        return None
    return None


def revision_covers(state: dict, package: str | None, chapter_id: str, digest: str) -> bool:
    return matching_revision(state, package, chapter_id, digest) is not None


def active_revision_approval(state: dict) -> dict | None:
    """The decision behind the revision currently in force, if it still stands."""
    revision_id = (state.get("revision") or {}).get("revision_id")
    if not revision_id or revision_id in withdrawn_revision_ids(state):
        return None
    for approval in reversed(state.get("approvals", [])):
        if approval.get("scope") != "revision" or approval.get("decision") != "accept":
            continue
        if approval.get("revision_id") == revision_id:
            return approval
    return None


def check_revision_content(state: dict, story: dict, root: Path, chapter_ids: list[str]) -> None:
    """A revision-only run may only touch content the decision was recorded on.

    The decision binds the per-chapter copy plus the global style basis, the
    metadata, and the chapter order: editing a chapter again, restyling the
    project, or retelling the meta after that decision is a new change and needs
    its own decision, exactly as it does when B stands.
    """
    approval = active_revision_approval(state)
    if not approval:
        raise Blocked(
            "story_changed_since_package",
            "record a new scoped revision decision for the changed chapters",
            "no standing revision decision covers this run",
        )
    moved: list[str] = []
    if approval.get("chapter_order") and chapter_order(story) != approval["chapter_order"]:
        moved.append(STRUCTURE_DELTA)
    digests = chapter_digest_map(story)
    moved += [
        chapter_id
        for chapter_id in chapter_ids
        if (approval.get("digests") or {}).get(chapter_id) != digests.get(chapter_id)
    ]
    if "style_basis" in approval and style_basis_digest(root) != approval.get("style_basis"):
        moved.append(STYLE_DELTA)
    if "meta_digest" in approval and meta_digest(story) != approval.get("meta_digest"):
        moved.append(META_DELTA)
    if moved:
        raise Blocked(
            "story_changed_since_package",
            "record a new scoped revision decision for the changed chapters",
            "the revision decision no longer matches the current content: " + ", ".join(sorted(set(moved))),
        )


def produced_by_revision(state: dict, package: str | None, chapter_id: str, digest: str | None) -> bool:
    """Whether an authorized revision's own run produced exactly these bytes.

    What matters is the provenance of the file on disk: the run that placed it
    must match the bytes, and the revision that run belonged to must have
    authorized this chapter. A newer revision for the same chapter that has not
    run yet says nothing about where the current file came from, so it must not
    make a legitimately produced image look stale.
    """
    if digest is None:
        return False
    for operation in reversed(state.get("operations", [])):
        if operation.get("target") != chapter_id or effective_status(operation) != "completed":
            continue
        if operation.get("sha256") != digest:
            return False
        return revision_authorized_run(state, package, chapter_id, str(operation.get("revision_id") or ""))
    return False


def revision_authorized_run(state: dict, package: str | None, chapter_id: str, revision_id: str) -> bool:
    """Whether any standing revision decision covers a run made under ``revision_id``."""
    if not revision_id or revision_id in withdrawn_revision_ids(state):
        return False
    for approval in reversed(state.get("approvals", [])):
        if approval.get("scope") != "revision" or approval.get("decision") != "accept":
            continue
        if approval.get("revision_id") != revision_id:
            continue
        return package in (approval.get("packages") or []) and chapter_id in (approval.get("stages") or [])
    return False


def revision_already_produced(state: dict, chapter_id: str, root: Path, declared: str) -> bool:
    """Whether the active revision's replacement for this chapter is on disk.

    True only when the newest completed run for the chapter belongs to the
    revision in force and the file still holds exactly the bytes that run placed.
    """
    revision_id = (state.get("revision") or {}).get("revision_id")
    if not revision_id:
        return False
    for operation in reversed(state.get("operations", [])):
        if operation.get("target") != chapter_id or effective_status(operation) != "completed":
            continue
        if operation.get("revision_id") != revision_id:
            return False
        asset = accepted_asset(root, declared)
        return asset is not None and operation.get("sha256") == sha256_file(asset)
    return False


def revision_produced_chapters(state: dict, root: Path, story: dict, chapter_ids: list[str]) -> set:
    """Which of these chapters already hold the replacement the revision authorized."""
    produced: set = set()
    for chapter_id in chapter_ids:
        declared = declared_still(story, chapter_id) or ""
        if declared and revision_already_produced(state, chapter_id, root, declared):
            produced.add(chapter_id)
    return produced


def split_already_revised(
    state: dict, root: Path, story: dict, targets: list[tuple[str, Path]], kind: str
) -> tuple[list[tuple[str, Path]], list[dict]]:
    """(still owed, already produced) for a revision batch.

    Retrying a batch after a partial failure must not pay for the chapters a
    previous run already replaced: those are reported as reused, not regenerated.
    """
    revision = state.get("revision") or {}
    if kind != "remaining" or not revision.get("stages"):
        return targets, []
    pending: list[tuple[str, Path]] = []
    reused: list[dict] = []
    for chapter_id, prompt in targets:
        declared = declared_still(story, chapter_id) or ""
        if declared and revision_already_produced(state, chapter_id, root, declared):
            reused.append(
                op_target(
                    state, kind, chapter_id, "skipped_existing", provider_calls=0, save_path=master_rel(declared)
                )
            )
        else:
            pending.append((chapter_id, prompt))
    return pending, reused


def uncovered_content_changes(state: dict, package: dict | None, root: Path, story: dict) -> list[str]:
    """Deltas between the shown package and the real content that no scoped
    revision authorizes.

    Chapter order, the style basis, and the story metadata are checked apart from
    the per-chapter copy, so a reorder, a new global style, or a retold meta
    cannot be smuggled through by authorizing chapters one at a time.
    """
    if not package:
        return []
    package_ref = package.get("id")
    if chapter_order(story) != (package.get("chapter_order") or []):
        return [STRUCTURE_DELTA]
    deltas: list[str] = []
    stored = package.get("chapter_digests") or {}
    for chapter_id, digest in chapter_digest_map(story).items():
        if stored.get(chapter_id) != digest and not revision_covers(state, package_ref, chapter_id, digest):
            deltas.append(chapter_id)
    if style_basis_digest(root) != package.get("style_basis"):
        deltas.append(STYLE_DELTA)
    if meta_digest(story) != package.get("meta_digest"):
        deltas.append(META_DELTA)
    return sorted(set(deltas))


def uncovered_sample_changes(state: dict, package: dict | None, root: Path, story: dict) -> list[str]:
    """Sample files that changed after the package was built, minus authorized ones.

    A replaced sample counts as authorized only when a revision named that
    chapter and a run of that revision produced exactly the bytes on disk now, so
    a later manual overwrite is still refused.
    """
    if not package:
        return []
    stored = {asset.get("id"): asset.get("sha256") for asset in (package.get("assets") or [])}
    pending: list[str] = []
    for asset in sample_assets(root, story, package.get("sample_ids") or []):
        chapter_id = asset["id"]
        if asset.get("sha256") == stored.get(chapter_id):
            continue
        if produced_by_revision(state, package.get("id"), chapter_id, asset.get("sha256")):
            continue
        pending.append(chapter_id)
    return sorted(pending)



# --- runner ---------------------------------------------------------------


def resolve_runner(root: Path, state: dict, override: str | None) -> Path:
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override).expanduser())
    base_dir = os.environ.get("SN_IMAGE_BASE_DIR")
    if base_dir:
        candidates.append(Path(base_dir) / "scripts" / "sn_agent_runner.py")
    recorded = state.get("runner")
    if recorded:
        candidates.append(Path(recorded).expanduser())
    candidates.append(root.parent / "sn-image-base" / "scripts" / "sn_agent_runner.py")
    for candidate in candidates:
        if candidate.is_file():
            state["runner"] = candidate.resolve().as_posix()
            return candidate.resolve()
    raise Blocked(
        "runner_not_configured",
        "pass_runner_path_or_export_SN_IMAGE_BASE_DIR",
        "no sn_agent_runner.py found; pass --runner <absolute path> or set SN_IMAGE_BASE_DIR",
    )


def runner_command(
    runner: Path,
    prompt: Path,
    out_path: Path,
    *,
    edit_images: list[Path],
    size: str,
    aspect: str,
) -> list[str]:
    command = [sys.executable, str(runner)]
    if edit_images:
        command.append("sn-image-edit")
        command += ["--images", *[str(image) for image in edit_images]]
    else:
        command.append("sn-image-generate")
        command += ["--no-fallback", "--image-format", "png"]
    command += [
        "--prompt-path",
        str(prompt),
        "--image-size",
        size,
        "--model",
        IMAGE_MODEL,
        "--aspect-ratio",
        aspect,
        "--save-path",
        str(out_path),
        "--output-format",
        "json",
    ]
    return command


def call_runner(command: list[str], timeout: int) -> tuple[str, int, str, str]:
    """Return (status, exit code, provider payload summary, note)."""
    env = dict(os.environ)
    env["SN_IMAGE_GEN_MODEL_TYPE"] = "sensenova"
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env
        )
    except subprocess.TimeoutExpired:
        # The provider may already have accepted and billed the request.
        return ("unknown", -1, "", f"timeout after {timeout}s; reconcile before any resubmission")
    except OSError as exc:
        return ("failed", -1, "", f"could not start runner: {exc}")
    summary = summarize_payload(completed.stdout)
    if completed.returncode != 0:
        return ("failed", completed.returncode, summary, (completed.stderr or "").strip()[-800:])
    return ("completed", completed.returncode, summary, "")


def summarize_payload(stdout: str) -> str:
    text = (stdout or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text[:500]
    if isinstance(parsed, dict):
        keep = {key: parsed[key] for key in ("model", "id", "created", "path", "save_path", "url") if key in parsed}
        return json.dumps(keep or parsed, ensure_ascii=False, default=str)[:500]
    return text[:500]


# --- operations -----------------------------------------------------------


def op_target(state: dict, kind: str, chapter_id: str, status: str, **extra) -> dict:
    operation = {
        "id": uuid.uuid4().hex[:12],
        "kind": kind,
        "target": chapter_id,
        "status": status,
        "at": now_iso(),
        "provider_calls": 1 if status in ("committed", "completed", "failed", "unknown") else 0,
    }
    operation.update(extra)
    state["operations"].append(operation)
    return operation


def effective_status(operation: dict) -> str:
    """An operation left as ``committed`` was cut short after it was sent.

    Its provider outcome is genuinely unknown, so it is reported and gated as
    unknown rather than trusted as a success or silently resent.
    """
    status = operation.get("status")
    return "unknown" if status == "committed" else str(status)


def unacknowledged_unknown(state: dict, chapter_id: str) -> dict | None:
    for operation in reversed(state["operations"]):
        if operation.get("target") == chapter_id and effective_status(operation) == "unknown":
            if not operation.get("reconciled"):
                return operation
    return None


def parse_targets(specs: list[str]) -> list[tuple[str, Path]]:
    parsed: list[tuple[str, Path]] = []
    for spec in specs:
        if "=" not in spec:
            raise StageError(f"--target expects chapter-id=prompt-file, got {spec!r}")
        chapter_id, prompt = spec.split("=", 1)
        parsed.append((chapter_id.strip(), Path(prompt.strip()).expanduser()))
    return parsed


def check_batch(
    story: dict,
    root: Path,
    targets: list[tuple[str, Path]],
    allowed_ids: list[str],
    gate: str,
) -> None:
    """Refuse the whole batch before a single provider call is made."""
    known = {str(chapter.get("id")) for chapter in chapters_of(story)}
    problems: list[str] = []
    seen: set[str] = set()
    for chapter_id, prompt in targets:
        if chapter_id in seen:
            problems.append(f"{chapter_id} is requested twice in one batch")
            continue
        seen.add(chapter_id)
        if chapter_id not in known:
            problems.append(f"{chapter_id} is not a chapter id in content/story.json")
            continue
        if chapter_id not in allowed_ids:
            problems.append(
                f"{chapter_id} is outside the {gate} scope actually shown in the review package "
                f"(allowed: {', '.join(allowed_ids) or 'none'})"
            )
            continue
        if not prompt.is_file():
            problems.append(f"prompt file is missing for {chapter_id}: {prompt}")
    if problems:
        raise Blocked(
            "targets_outside_allowed_scope",
            f"limit_the_request_to_{gate}_ids_and_retry",
            "; ".join(problems),
        )


def resolve_produced(staging: Path, token: str, expected: Path) -> Path | None:
    """Find what the runner actually wrote.

    The runner names the output from the format it produced, so a staged
    ``.png`` request can come back as a differently named sibling. Matching on
    the unique token prefix keeps that from being read as a missing result.
    """
    if expected.is_file():
        return expected
    candidates = sorted(
        (item for item in staging.glob(f"{token}-*") if item.is_file()),
        key=lambda item: item.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def generate_one(
    state: dict,
    root: Path,
    runner: Path,
    chapter_id: str,
    prompt: Path,
    *,
    kind: str,
    size: str,
    aspect: str,
    timeout: int,
    edit_images: list[Path],
    declared: str,
) -> dict:
    master = master_rel(declared)
    final = relative_media_path(root, master)
    already = real_asset_path(root, declared)
    # An accepted sample is a final asset: it is reused, never silently
    # regenerated. Only an explicitly authorized revision target is replaced.
    if kind == "samples" and already is not None:
        return op_target(
            state, kind, chapter_id, "skipped_existing", provider_calls=0, save_path=master
        )
    staging = root / "tmp" / "staged"
    staging.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:8]
    staged = staging / f"{token}-{final.name}"
    command = runner_command(runner, prompt.resolve(), staged, edit_images=edit_images, size=size, aspect=aspect)
    # The attempt is persisted, with its quota, before the request leaves: a run
    # cut short after submission still shows up on resume as an unknown result
    # instead of vanishing and being billed a second time.
    record = op_target(
        state,
        kind,
        chapter_id,
        "committed",
        save_path=master,
        prompt=str(prompt),
        token=token,
        revision_id=(state.get("revision") or {}).get("revision_id"),
    )
    state["total_provider_calls"] = state.get("total_provider_calls", 0) + 1
    save_state(root, state)
    status, code, payload, note = call_runner(command, timeout)
    produced = resolve_produced(staging, token, staged)
    if status == "completed" and produced is None:
        status, note = "unknown", "the runner reported success but wrote no file; reconcile before resubmitting"
    record["page_copy_needed"] = master != declared
    record["ended_at"] = now_iso()
    record["exit_code"] = code
    record["result"] = payload
    if status == "completed":
        replaced = ""
        if final.is_file():
            archive = root / "tmp" / "replaced"
            archive.mkdir(parents=True, exist_ok=True)
            target = archive / f"{int(time.time())}-{final.name}"
            final.replace(target)
            replaced = target.relative_to(root).as_posix()
        final.parent.mkdir(parents=True, exist_ok=True)
        produced.replace(final)
        record["replaced"] = replaced
        # The fingerprint of what was placed, so a later overwrite of the same
        # path is not mistaken for this authorized run.
        record["sha256"] = sha256_file(final)
    else:
        for leftover in staging.glob(f"{token}-*"):
            leftover.unlink(missing_ok=True)
        if status == "failed":
            note = note or "the request failed; nothing was written into the project"
    if note:
        record["note"] = note
    record["status"] = status
    save_state(root, state)
    return record


def summarize_run(state: dict, kind: str, records: list[dict], phase_after: str, hints: list[str]) -> dict:
    calls = sum(1 for record in records if record.get("provider_calls"))
    troubled = [effective_status(record) for record in records if effective_status(record) in ("failed", "unknown")]
    return {
        "status": "attention" if troubled else "ok",
        "operation": kind,
        "phase": phase_after,
        "provider_calls": calls,
        "failed_or_unknown": troubled,
        "results": [
            {
                "id": record.get("id"),
                "target": record.get("target"),
                "status": effective_status(record),
                "save_path": record.get("save_path"),
                "page_copy_needed": bool(record.get("page_copy_needed")),
            }
            for record in records
        ],
        "total_provider_calls": state.get("total_provider_calls", 0),
        "hints": hints,
    }


def check_limits(state: dict, planned: int) -> None:
    limits = state.get("generation_limits") or {}
    ceiling = limits.get("max_image_calls")
    if not isinstance(ceiling, (int, float)):
        return
    used = state.get("total_provider_calls", 0)
    if used + planned > ceiling:
        raise Blocked(
            "image_call_limit_reached",
            "report_the_blocker_and_ask_for_more_authorization",
            f"{used} of {int(ceiling)} authorized image calls are already spent; {planned} more would exceed it",
        )


# --- commands -------------------------------------------------------------


def command_status(args: argparse.Namespace) -> dict:
    root = args.project
    story = read_project(root)
    state = ensure_state(root, story)
    story_review = state.get("story_review") or {}
    visual_review = state.get("visual_review") or {}
    phase = state.get("phase", "drafting")
    sample_ids = story_review.get("sample_ids") or []
    needs_generation, needs_page_copy, _ready = production_needs(root, story)
    revision = state.get("revision") or {}
    allowed: list[str] = []
    if phase == "sampling":
        allowed = [f"run-samples targets from: {', '.join(sample_ids) or 'none'}"]
    elif phase == "producing":
        scope = needs_generation if visual_review else list(revision.get("stages") or [])
        allowed = [f"run-remaining targets from: {', '.join(scope) or 'none'}"]
    elif phase in PHASES:
        allowed = [f"show the current stage artifact and end the turn ({phase})"]
    if needs_page_copy:
        allowed.append("run scripts/make_posters.py for: " + ", ".join(needs_page_copy))
    return {
        "status": "ok",
        "operation": "status",
        "provider_calls": 0,
        "phase": phase,
        "project_id": state.get("project_id"),
        "interaction_mode": state.get("interaction_mode"),
        "story_package": story_review.get("id"),
        "story_displayed": bool(story_review.get("displayed")),
        "story_accepted": accepted(state, "story", story_review.get("id")),
        "sample_ids": sample_ids,
        "visual_package": visual_review.get("id"),
        "visual_displayed": bool(visual_review.get("displayed")),
        "visual_accepted": accepted(state, "visual", visual_review.get("id")),
        "revision": revision.get("stages") or [],
        "revision_return_to": revision.get("return_to"),
        "needs_generation": needs_generation,
        "needs_page_copy": needs_page_copy,
        "total_provider_calls": state.get("total_provider_calls", 0),
        "attempts": len([op for op in state.get("operations", []) if op.get("provider_calls")]),
        "in_doubt_results": [
            {"id": op.get("id"), "target": op.get("target"), "status": op.get("status")}
            for op in state.get("operations", [])
            if effective_status(op) == "unknown" and not op.get("reconciled")
        ],
        "waiting_on": waiting_on(phase, bool(story_review.get("displayed")), bool(visual_review.get("displayed"))),
        "allowed_actions": allowed,
    }


def waiting_on(phase: str, story_shown: bool, visual_shown: bool) -> str:
    if phase == "drafting":
        return "write the draft, then prepare-review --kind story and show it"
    if phase == "awaiting_story_review":
        return "user confirmation A" if story_shown else "show the draft and record-display --kind story"
    if phase == "sampling":
        return "generate the whitelisted samples, then prepare-review --kind visual"
    if phase == "awaiting_visual_review":
        return "user confirmation B" if visual_shown else "show the samples and record-display --kind visual"
    if phase == "producing":
        return "complete the remaining stills, assemble, and deliver"
    return "nothing; only an explicitly authorized local revision"


def command_prepare_review(args: argparse.Namespace) -> dict:
    root = args.project
    story = read_project(root)
    state = ensure_state(root, story)
    phase = state.get("phase", "drafting")
    if args.generation_limit is not None:
        state.setdefault("generation_limits", {})["max_image_calls"] = int(args.generation_limit)
    if args.kind == "story":
        sample_ids = _sample_ids(args, story)
        baseline = content_baseline(root, story, sample_ids)
        previous = state.get("story_review") or {}
        package = {
            "id": package_id("sr", state["project_id"], baseline["story_digest"]),
            "digest": baseline["story_digest"],
            "sample_ids": sample_ids,
            "revision": int(previous.get("revision", 0)) + 1,
            "note": args.note or "",
            "prepared_at": now_iso(),
            "displayed": None,
            **baseline,
        }
        # A new story package retires the sample set built from the old one, and
        # it never inherits a display record: the draft must be shown again.
        state["story_review"] = package
        state["visual_review"] = None
        state["revision"] = None
        state["phase"] = "awaiting_story_review"
        save_state(root, state)
        return {
            "status": "ok",
            "operation": "prepare-review",
            "provider_calls": 0,
            "phase": state["phase"],
            "story_package": package["id"],
            "sample_ids": sample_ids,
            "note": "prepared only: nothing is seen or accepted until record-display and record-decision",
        }
    # --kind visual
    if phase != "sampling":
        raise Blocked(
            f"phase_{phase}",
            "run-samples_after_confirmation_A",
            "the visual package is built from the representative stills, so the phase must be sampling",
        )
    story_review = state.get("story_review") or {}
    sample_ids = story_review.get("sample_ids") or []
    if not sample_ids:
        raise StageError("the accepted story package records no sample ids; nothing to review visually")
    pending = uncovered_content_changes(state, story_review, root, story)
    if pending:
        raise Blocked(
            "story_changed_since_package",
            "prepare-review --kind story and re-show the draft",
            "the samples cannot be reviewed against a story that moved: " + ", ".join(pending),
        )
    assets = sample_assets(root, story, sample_ids)
    absent = [asset["id"] for asset in assets if not asset["sha256"]]
    if absent:
        raise Blocked(
            "samples_missing",
            "generate_or_show_the_recorded_sample_ids",
            "no actual file behind: " + ", ".join(absent),
        )
    baseline = content_baseline(root, story, sample_ids)
    digest = visual_digest(assets, baseline["style_basis"])
    package = {
        "id": package_id("vr", state["project_id"], digest),
        "digest": digest,
        "assets": assets,
        "note": args.note or "",
        "prepared_at": now_iso(),
        "displayed": None,
        **baseline,
    }
    state["visual_review"] = package
    save_state(root, state)
    return {
        "status": "ok",
        "operation": "prepare-review",
        "provider_calls": 0,
        "phase": state["phase"],
        "visual_package": package["id"],
        "samples": [asset["id"] for asset in assets],
        "note": "prepared only: nothing is seen or accepted until record-display and record-decision",
    }


def _sample_ids(args: argparse.Namespace, story: dict) -> list[str]:
    raw = (args.sample_ids or "").strip()
    if raw in ("", "none", "None"):
        return []
    known = [str(chapter.get("id")) for chapter in chapters_of(story)]
    ids: list[str] = []
    for item in raw.split(","):
        chapter_id = item.strip()
        if not chapter_id:
            continue
        if chapter_id not in known:
            raise StageError(f"--sample-ids names an unknown chapter id: {chapter_id} (known: {', '.join(known)})")
        if chapter_id in ids:
            raise StageError(f"--sample-ids repeats chapter id: {chapter_id}")
        ids.append(chapter_id)
    return ids


def command_record_display(args: argparse.Namespace) -> dict:
    root = args.project
    story = read_project(root)
    state = ensure_state(root, story)
    phase = state.get("phase", "drafting")
    display = {"via": args.via, "ref": args.ref or "", "at": now_iso(), "proof": "agent-claimed"}
    if args.via == "host-event":
        display["proof"] = "host-verified"
    if args.kind == "story":
        package = state.get("story_review")
        if not package:
            raise StageError("run prepare-review --kind story first")
        if story_digest(root, story, package.get("sample_ids") or []) != package.get("digest"):
            raise Blocked(
                "story_changed_since_package",
                "prepare-review --kind story again",
                "the shown package must match the actual story content",
            )
        package["displayed"] = display
        state["phase"] = "awaiting_story_review"
        target = package["id"]
    else:
        package = state.get("visual_review")
        if not package:
            raise StageError("run prepare-review --kind visual first")
        if phase == "awaiting_visual_review" and package.get("displayed"):
            raise Blocked(
                "samples_already_displayed",
                "ask the focused question again, then record-decision --scope visual",
                "this same sample set is already on record as shown; a second display adds nothing",
            )
        if phase != "sampling":
            raise Blocked(f"phase_{phase}", "run-samples_after_confirmation_A", "only generated samples can be displayed")
        current = visual_digest(sample_assets(root, story, package.get("sample_ids") or []), style_basis_digest(root))
        if current != package.get("digest"):
            raise Blocked(
                "samples_changed_since_package",
                "prepare-review --kind visual again",
                "a sample file changed after the package was prepared, so the shown set is stale",
            )
        package["displayed"] = display
        state["phase"] = "awaiting_visual_review"
        target = package["id"]
    save_state(root, state)
    return {
        "status": "ok",
        "operation": "record-display",
        "provider_calls": 0,
        "phase": state["phase"],
        "package": target,
        "proof": display["proof"],
        "note": "end the turn now with the artifact shown and one focused question",
    }


def command_record_decision(args: argparse.Namespace) -> dict:
    root = args.project
    story = read_project(root)
    state = ensure_state(root, story)
    phase = state.get("phase", "drafting")
    # A withdrawal is handled before the scope dispatch: "changes-requested" on a
    # revision takes the standing authorization away, it never records a new one.
    if args.decision != "accept":
        return _record_revocation(args, root, state, phase)
    if args.scope == "revision":
        return _record_revision(args, root, story, state, phase)
    if args.scope == "delegation":
        return _record_delegation(args, root, state, phase)
    if args.scope == "story":
        package = state.get("story_review")
        if not package:
            raise StageError("run prepare-review --kind story first")
        if phase != "awaiting_story_review":
            raise Blocked(f"phase_{phase}", "show_the_draft_and_end_the_turn", "confirmation A is not pending")
        pending = uncovered_content_changes(state, package, root, story)
        if pending:
            raise Blocked(
                "story_changed_since_package",
                "prepare-review --kind story and re-show the draft",
                "the shown package no longer matches the story: " + ", ".join(pending),
            )
        if not package.get("displayed"):
            raise Blocked(
                "story_not_displayed",
                "record-display --kind story after actually showing the draft",
                "a decision cannot precede the visible review package",
            )
        _append_approval(state, "story", package["id"], args, ["story"])
        state["phase"] = "sampling"
    else:  # visual
        package = state.get("visual_review")
        if not package:
            raise StageError("run prepare-review --kind visual first")
        if phase != "awaiting_visual_review":
            raise Blocked(f"phase_{phase}", "show_the_samples_and_end_the_turn", "confirmation B is not pending")
        if not package.get("displayed"):
            raise Blocked(
                "samples_not_displayed",
                "record-display --kind visual after actually showing the samples",
                "a decision cannot precede the visible sample set",
            )
        pending = uncovered_content_changes(state, package, root, story) + uncovered_sample_changes(
            state, package, root, story
        )
        if pending:
            raise Blocked(
                "review_package_stale",
                "prepare-review --kind visual and re-show the samples",
                "B can only accept the images actually shown: " + ", ".join(sorted(set(pending))),
            )
        _append_approval(state, "visual", package["id"], args, ["visual"])
        state["phase"] = "producing"
    save_state(root, state)
    return {
        "status": "ok",
        "operation": "record-decision",
        "provider_calls": 0,
        "phase": state["phase"],
        "scope": args.scope,
        "trust": args.trust,
        "note": "an agent-recorded decision prevents forgetting; only a host-verified event proves a real user",
    }


def earliest_unmet_gate(state: dict) -> str:
    """The first gate that no longer has a decision behind it."""
    story_package = state.get("story_review") or {}
    visual_package = state.get("visual_review") or {}
    if not story_package:
        return str(state.get("phase", "drafting"))
    if not (accepted(state, "story", story_package.get("id")) or delegation_covers(state, "story")):
        return "awaiting_story_review"
    if not visual_package:
        return "sampling"
    if not (accepted(state, "visual", visual_package.get("id")) or delegation_covers(state, "visual")):
        return "awaiting_visual_review"
    return "producing"


def _record_revocation(args: argparse.Namespace, root: Path, state: dict, phase: str) -> dict:
    """Persist that the user withdrew an approval, and close the gate it opened.

    Recording nothing would leave the earlier accept as the newest word on the
    package, so production would keep running after the user asked for changes.
    """
    scope = args.scope
    if scope == "revision":
        revision = state.get("revision") or {}
        if not revision.get("stages"):
            raise StageError("no revision authorization is on record to withdraw")
        package = (state.get("story_review") or {}).get("id") or (state.get("visual_review") or {}).get("id")
        approval = _append_approval(state, "revision", package, args, revision.get("stages") or [])
        # Naming the withdrawn revision id is what retires its authorization:
        # matching_revision() refuses any accept the user has since revoked.
        approval["revision_id"] = revision.get("revision_id")
        state["revision"] = None
    elif scope == "delegation":
        stages = [item.strip() for item in (args.stages or "story,visual").split(",") if item.strip()]
        unknown = [item for item in stages if item not in DELEGATION_STAGES]
        if unknown:
            raise StageError(f"--stages accepts {DELEGATION_STAGES}, got: {', '.join(unknown)}")
        package = (state.get("story_review") or {}).get("id") or (state.get("visual_review") or {}).get("id")
        _append_approval(state, "delegation", package, args, stages)
        state["delegation"] = None
        state["interaction_mode"] = "collaborative"
    else:
        package = state.get("story_review") if scope == "story" else state.get("visual_review")
        if not package:
            raise StageError(f"no {scope} review package is on record to withdraw")
        _append_approval(state, scope, package.get("id"), args, [scope])
        if scope in ((state.get("delegation") or {}).get("stages") or []):
            # The explicit withdrawal is newer than the delegation, so the
            # wait-skipping does not survive it.
            state["delegation"] = None
            state["interaction_mode"] = "collaborative"
        if scope == "story":
            # Anything reviewed against a withdrawn draft is void too.
            state["visual_review"] = None
            state["revision"] = None
    state["phase"] = earliest_unmet_gate(state)
    save_state(root, state)
    return {
        "status": "ok",
        "operation": "record-decision",
        "provider_calls": 0,
        "phase": state["phase"],
        "scope": scope,
        "decision": args.decision,
        "note": "the withdrawal is now the newest word on that package; nothing more generates under it",
    }


def _append_approval(state: dict, scope: str, package: str | None, args: argparse.Namespace, stages: list[str]) -> dict:
    if args.trust == "host-verified" and not (args.event_ref or "").strip():
        raise StageError("--trust host-verified requires --event-ref naming the host user event")
    approval = {
        "scope": scope,
        "package": package,
        "packages": [package] if package else [],
        "decision": args.decision,
        "stages": stages,
        "source": args.source,
        "message_ref": args.message_ref or "",
        "event_ref": args.event_ref or "",
        "trust": args.trust,
        "at": now_iso(),
    }
    state["approvals"].append(approval)
    return approval


def _record_delegation(args: argparse.Namespace, root: Path, state: dict, phase: str) -> dict:
    stages = [item.strip() for item in (args.stages or "story,visual").split(",") if item.strip()]
    unknown = [item for item in stages if item not in DELEGATION_STAGES]
    if unknown:
        raise StageError(f"--stages accepts {DELEGATION_STAGES}, got: {', '.join(unknown)}")
    for stage in stages:
        if stage == "story":
            package = state.get("story_review")
            if not package or not package.get("displayed"):
                raise Blocked("story_not_displayed", "show_the_draft_first", "a delegation still needs a draft on record")
            _append_approval(state, "delegation", package["id"], args, [stage])
            state["phase"] = "sampling"
        else:
            package = state.get("visual_review")
            _append_approval(state, "delegation", package["id"] if package else None, args, [stage])
            if state.get("phase") == "awaiting_visual_review" and package and package.get("displayed"):
                state["phase"] = "producing"
    state["interaction_mode"] = "direct-completion"
    state["delegation"] = {"stages": stages, "at": now_iso(), "scope_note": args.note or ""}
    save_state(root, state)
    return {
        "status": "ok",
        "operation": "record-decision",
        "provider_calls": 0,
        "phase": state["phase"],
        "scope": "delegation",
        "stages": stages,
        "note": "a delegation covers the waits, never the stage artifacts or the sample self-check",
    }


def _record_revision(args: argparse.Namespace, root: Path, story: dict, state: dict, phase: str) -> dict:
    """Authorize a bounded local change without reopening the whole flow.

    The decision records which chapters it covers; it never rewrites a review
    package's baseline, so an unrelated change made in the same edit still stops
    the next generation until it is covered too.
    """
    if not (args.chapters or "").strip():
        raise StageError("--scope revision requires --chapters naming the affected stable chapter ids")
    stages = [item.strip() for item in args.chapters.split(",") if item.strip()]
    known = {str(chapter.get("id")) for chapter in chapters_of(story)}
    unknown = [item for item in stages if item not in known]
    if unknown:
        raise StageError(f"--chapters names unknown chapter ids: {', '.join(unknown)}")
    story_package = state.get("story_review") or {}
    visual_package = state.get("visual_review") or {}
    legacy = not story_package and not visual_package
    if phase == "awaiting_story_review" and story_package:
        raise Blocked(
            "awaiting_story_review",
            "prepare-review --kind story and re-show the draft",
            "confirmation A is pending on the shown draft, so a change means a new package, not a silent one",
        )
    if phase == "drafting" and not legacy:
        raise Blocked("phase_drafting", "show_the_draft_and_record_display", "a story package is prepared but not shown")
    packages = [value for value in (story_package.get("id"), visual_package.get("id")) if value]
    approval = _append_approval(state, "revision", story_package.get("id") or None, args, stages)
    approval["packages"] = packages
    digests = chapter_digest_map(story)
    # The authorization is pinned to the content it was given on: a later edit to
    # the same chapter is a different change and needs its own decision.
    approval["digests"] = {chapter_id: digests[chapter_id] for chapter_id in stages if chapter_id in digests}
    # The global dimensions are bound too: a restyle or a retold meta after this
    # decision is an unapproved change even though no chapter digest moved.
    approval["chapter_order"] = chapter_order(story)
    approval["style_basis"] = style_basis_digest(root)
    approval["meta_digest"] = meta_digest(story)
    approval["revision_id"] = uuid.uuid4().hex[:8]
    if args.copy_only:
        save_state(root, state)
        return {
            "status": "ok",
            "operation": "record-decision",
            "provider_calls": 0,
            "phase": state["phase"],
            "scope": "revision",
            "authorized": stages,
            "image_calls_allowed": 0,
            "note": "copy only: no image production is authorized by this decision",
        }
    b_is_open = bool(visual_package) and not (
        accepted(state, "visual", visual_package.get("id")) or delegation_covers(state, "visual")
    )
    if b_is_open:
        # The samples are being reworked before B: A still stands, but the shown
        # sample set no longer exists, so the run has to end at a fresh B.
        return_to = "sampling"
    elif visual_package:
        return_to = "delivered"
    else:
        return_to = "producing"
    state["revision"] = {
        "stages": stages,
        "done": [],
        "packages": packages,
        "revision_id": approval["revision_id"],
        "return_to": return_to,
        "legacy": legacy,
        "at": now_iso(),
        "note": args.note or "",
    }
    state["phase"] = "producing"
    save_state(root, state)
    return {
        "status": "ok",
        "operation": "record-decision",
        "provider_calls": 0,
        "phase": state["phase"],
        "scope": "revision",
        "authorized": stages,
        "return_to": return_to,
        "note": "the authorization is scoped to these chapters and does not release other scenes",
    }


def _advance_after_run(
    root: Path, story: dict, state: dict, kind: str, records: list[dict], hints: list[str]
) -> str:
    """Move the phase forward only over what this run really produced.

    A sample run never advances the phase: B is still the next gate. A revision is
    kept open until every chapter it authorized has been produced, so finishing
    one of two authorized chapters cannot silently revoke the other.
    """
    generate, page_copy, _ready = production_needs(root, story)
    revision = state.get("revision") or {}
    troubled = [
        op
        for op in state.get("operations", [])
        if effective_status(op) == "unknown" and not op.get("reconciled")
    ]

    if kind == "samples":
        if troubled:
            hints.append("reconcile the in-doubt calls with status before resubmitting anything")
        return state["phase"]
    if revision:
        placed = {str(record.get("target")) for record in records if effective_status(record) == "completed"}
        # A run cut short after a file landed but before this bookkeeping leaves the
        # chapter finished on disk and unfinished in the record; recover it from the
        # persisted operation, or a retry that correctly reuses the file would never
        # be able to close the revision.
        recovered = revision_produced_chapters(state, root, story, revision.get("stages") or [])
        done = sorted(set(revision.get("done") or []) | placed | recovered)
        revision["done"] = done
        state["revision"] = revision
        pending = [chapter_id for chapter_id in revision.get("stages") or [] if chapter_id not in done]
        if pending:
            state["phase"] = "producing"
            hints.append("this revision still owes these chapters: " + ", ".join(pending))
            return state["phase"]
        pages_pending = [chapter_id for chapter_id in revision.get("stages") or [] if chapter_id in page_copy]
        if pages_pending:
            # The new master is not finished business until the page can load it:
            # the revision stays open so the follow-up confirmation knows its scope.
            state["phase"] = "producing"
            hints.append("refresh the page assets before this revision is done: " + ", ".join(pages_pending))
            return state["phase"]
        return_to = revision.get("return_to")
        state["revision"] = None
        if return_to == "sampling":
            # A sample was reworked before B: A still stands, but the shown sample
            # set no longer exists, so B has to be rebuilt and asked again.
            state["phase"] = "sampling"
            state["visual_review"] = None
            hints.append("rebuild B: prepare-review --kind visual, record-display --kind visual, then ask again")
            return state["phase"]
    if troubled:
        state["phase"] = "producing"
        hints.append("reconcile the in-doubt calls with status before resubmitting anything")
        return state["phase"]
    if page_copy:
        state["phase"] = "producing"
        hints.append(
            "masters are newer than the page assets the page would load; run scripts/make_posters.py with the "
            "recorded width for: " + ", ".join(page_copy)
        )
        return state["phase"]
    state["phase"] = "delivered" if not generate else "producing"
    return state["phase"]


def _finish_run(
    root: Path, story: dict, state: dict, kind: str, records: list[dict], hints: list[str], note: str
) -> dict:
    phase_after = _advance_after_run(root, story, state, kind, records, hints)
    result = summarize_run(state, f"run-{kind}", records, phase_after, hints)
    if note:
        result["note"] = note
    save_state(root, state)
    return result


def _run_images(args: argparse.Namespace, kind: str) -> dict:
    root = args.project
    story = read_project(root)
    state = ensure_state(root, story)
    phase = state.get("phase", "drafting")
    story_review = state.get("story_review") or {}
    visual_review = state.get("visual_review") or {}
    revision = state.get("revision") or {}
    sample_ids = story_review.get("sample_ids") or []
    needs_generation, needs_page_copy, _ready = production_needs(root, story)
    hints: list[str] = []

    if kind == "samples":
        if phase == "awaiting_story_review":
            raise Blocked(
                "awaiting_story_review",
                "show_current_draft_and_end_turn",
                "confirmation A is pending; the image call count must stay 0, including a 1K smoke request",
            )
        if phase != "sampling":
            raise Blocked(f"phase_{phase}", "complete_confirmation_A_first", "samples belong to the sampling phase")
        if not (accepted(state, "story", story_review.get("id")) or delegation_covers(state, "story")):
            raise Blocked(
                "story_not_accepted",
                "record-decision --scope story after the user confirms the shown draft",
                "no acceptance or delegation covers the current story package",
            )
        pending = uncovered_content_changes(state, story_review, root, story)
        if pending:
            raise Blocked(
                "story_changed_since_package",
                "record a scoped revision decision or prepare a new story package",
                "changes not covered by the accepted package: " + ", ".join(pending),
            )
        allowed = sample_ids
        gate = "sample"
        targets = parse_targets(args.target or [])
        if not targets:
            targets = [(chapter_id, _prompt_for(args, chapter_id)) for chapter_id in allowed]
        if not targets:
            raise StageError("the accepted story package records no sample ids, so there is nothing to generate")
        check_batch(story, root, targets, allowed, gate)
        planned = targets
    else:
        # A recorded delegation covers a later wait: the samples are still shown
        # and self-checked, but the turn does not stop for confirmation B.
        if phase == "awaiting_visual_review" and delegation_covers(state, "visual") and visual_review.get("displayed"):
            phase = state["phase"] = "producing"
        visual_gate_ok = bool(visual_review.get("id")) and (
            accepted(state, "visual", visual_review["id"]) or delegation_covers(state, "visual")
        )
        revision_active = bool(revision.get("stages")) and phase in ("producing", "delivered")
        if phase not in ("producing", "delivered"):
            raise Blocked(
                f"phase_{phase}",
                "complete_confirmation_B_first",
                "the remaining stills belong to the producing phase",
            )
        if not (visual_gate_ok or revision_active):
            raise Blocked(
                "visual_not_accepted",
                "show_current_samples_and_end_turn",
                "no acceptance or delegation covers the current sample set",
            )
        if visual_gate_ok:
            content_pending = uncovered_content_changes(state, visual_review, root, story)
            if content_pending:
                raise Blocked(
                    "story_changed_since_package",
                    "record a scoped revision decision for the changed chapters",
                    "changes not covered by an accepted revision: " + ", ".join(content_pending),
                )
            file_pending = uncovered_sample_changes(state, visual_review, root, story)
            if file_pending:
                raise Blocked(
                    "visual_review_stale",
                    "record a scoped revision for the replaced samples or re-show them",
                    "a sample file changed in a way B never covered: " + ", ".join(file_pending),
                )
        targets = parse_targets(args.target or [])
        if targets:
            allowed = sorted(set((needs_generation if visual_gate_ok else []) + list(revision.get("stages") or [])))
            gate = "authorized"
            check_batch(story, root, targets, allowed, gate)
            if not visual_gate_ok:
                # B is not in force, so the revision decision is the only thing
                # authorizing this work: verify it still covers the current copy,
                # style, meta, and order.
                check_revision_content(state, story, root, [chapter_id for chapter_id, _ in targets])
            planned = targets
        else:
            if not visual_gate_ok and needs_generation:
                raise StageError("with only a revision in force, list the authorized --target values explicitly")
            if not visual_gate_ok:
                # Nothing is missing and nothing is authorized: this is a zero-call
                # confirmation that the page assets caught up, not a production run.
                return _finish_run(
                    root, story, state, kind, [], hints, "nothing needs an image call; the revision is complete"
                )
            allowed = sorted(needs_generation)
            planned = [(chapter_id, _prompt_for(args, chapter_id)) for chapter_id in allowed]
            check_batch(story, root, planned, allowed, "missing")
            if needs_page_copy:
                hints.append("nothing more needs an image call; run scripts/make_posters.py for: " + ", ".join(needs_page_copy))

    planned, reused = split_already_revised(state, root, story, planned, kind)

    unknown = [
        record
        for chapter_id, _ in planned
        if (record := unacknowledged_unknown(state, chapter_id)) is not None
    ]
    if unknown and not args.retry_unknown:
        staging = root / "tmp" / "staged"
        stranded = []
        for record in unknown:
            token = record.get("token")
            if token:
                stranded.extend(item.name for item in staging.glob(f"{token}-*") if item.is_file())
        detail = (
            "a submitted request whose result was never recorded may already be billed; nothing is resent "
            "automatically"
        )
        if stranded:
            detail += "; a finished file may already be in tmp/staged, check it before paying twice: " + ", ".join(stranded)
        raise Blocked(
            "previous_result_unknown",
            f"reconcile {'/'.join(item['id'] for item in unknown)} with status, then pass --retry-unknown",
            detail,
        )
    if unknown and args.retry_unknown:
        named = {item.strip() for item in args.retry_unknown.split(",") if item.strip()}
        unexpected = named ^ {item["id"] for item in unknown}
        if unexpected:
            raise StageError(f"--retry-unknown does not name the pending in-doubt calls: {', '.join(sorted(unexpected))}")
        for record in unknown:
            record["reconciled"] = True
            record["reconciled_at"] = now_iso()
        save_state(root, state)

    check_limits(state, len(planned))
    if not planned:
        return _finish_run(
            root, story, state, kind, reused, hints, "every authorized target already has a real file; nothing was resubmitted"
        )

    runner = resolve_runner(root, state, args.runner)
    size = args.image_size or DEFAULT_IMAGE_SIZE
    aspect = args.aspect_ratio or DEFAULT_ASPECT_RATIO
    timeout = int(args.call_timeout or DEFAULT_CALL_TIMEOUT)
    if size != DEFAULT_IMAGE_SIZE and not args.allow_smaller_master:
        raise StageError(
            f"--image-size {size} is refused: story masters are 4K by default; pass --allow-smaller-master only for an explicitly requested draft pass"
        )

    records: list[dict] = list(reused)
    for chapter_id, prompt in planned:
        declared = declared_still(story, chapter_id)
        if declared is None:
            raise StageError(f"chapter {chapter_id} declares no still path in content/story.json")
        edit_images: list[Path] = []
        if args.edit:
            existing = accepted_asset(root, declared)
            if existing is None:
                raise StageError(f"--edit needs the existing still for {chapter_id}, but no file is there to edit")
            edit_images.append(existing)
        records.append(
            generate_one(
                state,
                root,
                runner,
                chapter_id,
                prompt,
                kind=kind,
                size=size,
                aspect=aspect,
                timeout=timeout,
                edit_images=edit_images,
                declared=declared,
            )
        )
    if kind == "samples":
        hints.append("show the actual sample images, then prepare-review --kind visual and record-display --kind visual")
    return _finish_run(root, story, state, kind, records, hints, "")


def _prompt_for(args: argparse.Namespace, chapter_id: str) -> Path:
    directory = args.prompts_dir
    if not directory:
        raise StageError("run-remaining without --target needs --prompts-dir <directory> holding <chapter-id>.txt files")
    candidate = Path(directory) / f"{chapter_id}.txt"
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project", type=Path, help="absolute PROJECT_ROOT of the story project")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="report the phase, packages, allowed scope, and waiting item")

    prepare = sub.add_parser("prepare-review", help="build a review package id from the real content")
    prepare.add_argument("--kind", choices=("story", "visual"), required=True)
    prepare.add_argument("--sample-ids", default="", help="comma-separated chapter ids shown with the A package, or none")
    prepare.add_argument("--note", default="", help="short revision summary for the record")
    prepare.add_argument("--generation-limit", type=int, default=None, help="cap on image calls this project may spend")

    display = sub.add_parser("record-display", help="link the host display event for a prepared package")
    display.add_argument("--kind", choices=("story", "visual"), required=True)
    display.add_argument("--via", choices=("agent-claimed", "host-event"), default="agent-claimed")
    display.add_argument("--ref", default="", help="host display event reference when available")

    decision = sub.add_parser("record-decision", help="record a user decision with its source and trust level")
    decision.add_argument("--scope", choices=DECISION_SCOPES, required=True)
    decision.add_argument("--decision", choices=("accept", "changes-requested"), default="accept")
    decision.add_argument("--source", default="conversation", help="where the decision came from")
    decision.add_argument("--message-ref", default="", help="reference to the real user message")
    decision.add_argument("--event-ref", default="", help="host user-event id for a verified approval")
    decision.add_argument("--trust", choices=TRUST_LEVELS, default="agent-recorded")
    decision.add_argument("--stages", default="", help="delegation scope: story,visual")
    decision.add_argument("--chapters", default="", help="revision scope: stable chapter ids")
    decision.add_argument("--copy-only", action="store_true", help="revision changes no image production")
    decision.add_argument("--note", default="")

    for name in ("samples", "remaining"):
        run = sub.add_parser(f"run-{name}", help="validate the gate and call the runner for the allowed targets")
        run.add_argument("--target", action="append", default=[], help="chapter-id=prompt-file, repeatable")
        run.add_argument("--prompts-dir", default=None, help="directory of <chapter-id>.txt prompts for run-remaining")
        run.add_argument("--runner", default=None, help="absolute path to sn_agent_runner.py")
        run.add_argument("--image-size", default=None)
        run.add_argument("--aspect-ratio", default=None)
        run.add_argument("--call-timeout", type=int, default=None)
        run.add_argument("--allow-smaller-master", action="store_true", help="only for an explicitly requested draft pass")
        run.add_argument("--edit", action="store_true", help="edit from the existing still instead of generating fresh")
        run.add_argument("--retry-unknown", default="", help="comma-separated operation ids already reconciled")

    args = parser.parse_args(argv)
    args.project = args.project.expanduser().resolve()
    if not args.project.is_dir():
        print(json.dumps({"status": "error", "reason": f"project directory not found: {args.project}"}))
        return 1

    handlers = {
        "status": command_status,
        "prepare-review": command_prepare_review,
        "record-display": command_record_display,
        "record-decision": command_record_decision,
        "run-samples": lambda parsed: _run_images(parsed, "samples"),
        "run-remaining": lambda parsed: _run_images(parsed, "remaining"),
    }
    try:
        if args.command == "status":
            result = handlers[args.command](args)
        else:
            with project_lock(args.project):
                result = handlers[args.command](args)
    except Blocked as blocked:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": blocked.reason,
                    "allowed_action": blocked.allowed_action,
                    "detail": blocked.detail,
                    "provider_calls": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    except (StageError, ProjectError) as error:
        print(json.dumps({"status": "error", "reason": str(error)}, ensure_ascii=False, indent=2))
        return 1
    except OSError as error:
        print(json.dumps({"status": "error", "reason": f"{type(error).__name__}: {error}"}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") == "attention":
        return 1
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
