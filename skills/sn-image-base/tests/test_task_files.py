from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import sn_task_files as tf
from sn_image_base.image_utils import validate_image_file


def make_png(path: Path, width: int = 32, height: int = 32) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), color=(200, 120, 40)).save(path, format="PNG")
    return path


def write_marker(
    task_dir: Path, *, task_id: str | None = None, created_at: datetime | None = None
) -> None:
    payload = {
        "format_version": tf.MARKER_FORMAT_VERSION,
        "task_id": task_id or task_dir.name,
        "created_at": (created_at or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
    }
    (task_dir / tf.MARKER_NAME).write_text(json.dumps(payload), encoding="utf-8")


def touch_lock(task_dir: Path) -> Path:
    """Create the external lock file a real task directory would have."""
    path = tf._lock_path(task_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def backdate(task_dir: Path, hours: float) -> None:
    """Simulate a directory that has been inactive for the given time."""
    stamp = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
    targets = [task_dir]
    for base, dirs, files in os.walk(task_dir):
        for name in dirs + files:
            targets.append(Path(base) / name)
    for path in targets:
        try:
            os.utime(path, (stamp, stamp))
        except OSError:
            pass


class TaskFilesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        env_patcher = patch.dict(
            os.environ,
            {"SN_TASK_RETENTION_HOURS": "48", "SN_IMAGE_OUTPUT_DIR": "", "SN_ENV_FILE": ""},
            clear=False,
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self._tmp = Path(tmp.name)
        self.root = self._tmp / "sensenova-tasks"
        self.root.mkdir(parents=True)
        self._counter = 0

    def next_name(self) -> str:
        self._counter += 1
        return f"dir{self._counter:03d}"

    def begin(self) -> Path:
        return tf.begin(root=self.root)


class TestBegin(TaskFilesTestCase):
    def test_creates_guarded_dir_with_matching_marker(self) -> None:
        task_dir = self.begin()
        self.assertTrue(task_dir.is_dir())
        self.assertEqual(task_dir.parent, self.root.resolve())
        marker = json.loads((task_dir / tf.MARKER_NAME).read_text(encoding="utf-8"))
        self.assertEqual(marker["format_version"], tf.MARKER_FORMAT_VERSION)
        self.assertEqual(marker["task_id"], task_dir.name)
        created = tf._created_at(marker["created_at"])
        self.assertIsNotNone(created)
        self.assertLess(datetime.now(timezone.utc) - created, timedelta(minutes=1))

    def test_task_ids_are_unique(self) -> None:
        self.assertNotEqual(self.begin(), self.begin())

    def test_begin_leaves_nothing_when_lock_setup_fails(self) -> None:
        (self.root / tf.LOCK_DIRNAME).write_text("occupied", encoding="utf-8")
        with self.assertRaises(ValueError):
            tf.begin(root=self.root)
        leftovers = sorted(path.name for path in self.root.iterdir())
        self.assertEqual(leftovers, [tf.LOCK_DIRNAME])

    def test_runs_gc_first_and_collects_expired_leftovers(self) -> None:
        stale = self.root / "stale0001"
        stale.mkdir()
        write_marker(stale, created_at=datetime.now(timezone.utc) - timedelta(hours=72))
        backdate(stale, 72)
        stale_staging = self.root / f"{tf.STAGING_PREFIX}old"
        stale_staging.mkdir()
        write_marker(stale_staging, task_id="old", created_at=datetime.now(timezone.utc) - timedelta(hours=72))
        backdate(stale_staging, 72)
        task_dir = self.begin()
        self.assertFalse(stale.exists())
        self.assertFalse(stale_staging.exists())
        self.assertTrue(task_dir.is_dir())


class TestGc(TaskFilesTestCase):
    def prepare(self, *, hours: float, marked: bool = True, with_files: bool = False) -> Path:
        child = self.root / self.next_name()
        child.mkdir()
        if with_files:
            (child / "prompt.txt").write_text("p", encoding="utf-8")
            make_png(child / "round_1.png")
        if marked:
            write_marker(child, created_at=datetime.now(timezone.utc) - timedelta(hours=hours))
            touch_lock(child)
        if hours > 0:
            backdate(child, hours)
        return child

    def next_name(self) -> str:
        self._counter += 1
        return f"dir{self._counter:03d}"

    def test_removes_expired_marked_dir_with_contents(self) -> None:
        child = self.prepare(hours=72, with_files=True)
        report = tf.gc(root=self.root)
        self.assertIn(str(child), report["removed"])
        self.assertFalse(child.exists())

    def test_removes_expired_unmarked_dir(self) -> None:
        child = self.prepare(hours=72, marked=False)
        report = tf.gc(root=self.root)
        self.assertIn(str(child), report["removed"])
        self.assertFalse(child.exists())

    def test_keeps_recent_marked_dir(self) -> None:
        child = self.prepare(hours=0)
        report = tf.gc(root=self.root)
        self.assertNotIn(str(child), report["removed"])
        self.assertTrue(child.exists())

    def test_keeps_recent_unmarked_dir(self) -> None:
        child = self.prepare(hours=0, marked=False)
        report = tf.gc(root=self.root)
        self.assertNotIn(str(child), report["removed"])
        self.assertTrue(child.exists())

    def test_keeps_dir_locked_by_active_task_until_released(self) -> None:
        child = self.prepare(hours=72)
        handle = tf._acquire_lock(tf._lock_path(child))
        self.assertIsNotNone(handle)
        try:
            report = tf.gc(root=self.root)
            self.assertIn(str(child), report["kept"])
            self.assertTrue(child.exists())
        finally:
            tf._release_quietly(handle)
        report = tf.gc(root=self.root)
        self.assertIn(str(child), report["removed"])
        self.assertFalse(child.exists())

    def test_keeps_recently_active_dir_with_old_creation_time(self) -> None:
        child = self.prepare(hours=72)
        os.utime(child, None)  # a fresh in-progress write refreshed the directory activity
        report = tf.gc(root=self.root)
        self.assertNotIn(str(child), report["removed"])
        self.assertTrue(child.exists())

    def test_keeps_dir_when_an_existing_file_was_modified(self) -> None:
        child = self.prepare(hours=72, with_files=True)
        # Rewriting an existing prompt refreshes only the file's own timestamp.
        os.utime(child / "prompt.txt", None)
        report = tf.gc(root=self.root)
        self.assertNotIn(str(child), report["removed"])
        self.assertTrue(child.exists())

    def test_rejects_linked_task_root_and_keeps_target_files(self) -> None:
        target = self._tmp / "real-store"
        old_dir = target / "old-task"
        old_dir.mkdir(parents=True)
        (old_dir / "keep.txt").write_text("user data", encoding="utf-8")
        stamp = (datetime.now(timezone.utc) - timedelta(hours=72)).timestamp()
        os.utime(old_dir, (stamp, stamp))
        os.utime(old_dir / "keep.txt", (stamp, stamp))
        linked_root = self._tmp / "linked-root"
        try:
            linked_root.symlink_to(target, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is not available on this host")
        self.addCleanup(linked_root.unlink)
        with self.assertRaises(ValueError):
            tf.gc(root=linked_root)
        with self.assertRaises(ValueError):
            tf.begin(root=linked_root)
        with self.assertRaises(ValueError):
            tf.abort(linked_root / "old-task", root=linked_root)
        self.assertTrue(old_dir.exists())
        self.assertTrue((old_dir / "keep.txt").is_file())

    def test_removes_old_dir_whose_marker_does_not_match(self) -> None:
        child = self.root / self.next_name()
        child.mkdir()
        (child / "prompt.txt").write_text("p", encoding="utf-8")
        write_marker(child, task_id="someone-else")
        touch_lock(child)
        backdate(child, 72)
        report = tf.gc(root=self.root)
        self.assertIn(str(child), report["removed"])
        self.assertFalse(child.exists())

    def test_keeps_mismatched_marker_dir_with_recent_activity(self) -> None:
        child = self.root / self.next_name()
        child.mkdir()
        write_marker(child, task_id="someone-else")
        touch_lock(child)
        report = tf.gc(root=self.root)
        self.assertNotIn(str(child), report["removed"])
        self.assertTrue(child.exists())

    def test_partial_removal_is_not_reported_as_success(self) -> None:
        child = self.prepare(hours=72)
        with patch.object(tf, "_rmtree", side_effect=FileNotFoundError(2, "vanished entry")):
            report = tf.gc(root=self.root)
        self.assertTrue(any(str(child) in item for item in report["errors"]))
        self.assertNotIn(str(child), report["removed"])
        self.assertTrue(child.exists())

    def test_stale_staging_partial_removal_is_reported(self) -> None:
        staging = self.root / f"{tf.STAGING_PREFIX}stale"
        staging.mkdir()
        backdate(staging, 72)
        with patch.object(tf, "_rmtree", side_effect=FileNotFoundError(2, "vanished entry")):
            report = tf.gc(root=self.root)
        self.assertTrue(any(str(staging) in item for item in report["errors"]))
        self.assertNotIn(str(staging), report["removed"])
        self.assertTrue(staging.exists())

    def test_no_op_removal_is_reported_as_still_existing(self) -> None:
        child = self.prepare(hours=72)
        with patch.object(tf, "_rmtree", side_effect=lambda path: None):
            report = tf.gc(root=self.root)
        self.assertTrue(any("still exists" in item for item in report["errors"]))
        self.assertNotIn(str(child), report["removed"])
        self.assertTrue(child.exists())

    def test_gc_sweeps_orphaned_lock_files(self) -> None:
        orphan = touch_lock(self.root / "ghost0001")
        stamp = (datetime.now(timezone.utc) - timedelta(hours=72)).timestamp()
        os.utime(orphan, (stamp, stamp))
        recent = self.prepare(hours=0)
        recent_lock = tf._lock_path(recent)
        report = tf.gc(root=self.root)
        self.assertIn(str(orphan), report["locks_removed"])
        self.assertFalse(orphan.exists())
        self.assertTrue(recent_lock.exists())

    def test_sweep_keeps_fresh_lock_without_task_dir(self) -> None:
        # The window between `begin` creating the lock file and renaming the
        # task directory into place: a concurrent gc must not sweep it.
        creating = touch_lock(self.root / "creating001")
        report = tf.gc(root=self.root)
        self.assertTrue(creating.exists())
        self.assertNotIn(str(creating), report["locks_removed"])
        self.assertIn(str(creating), report["kept"])

    def test_collected_dir_lock_file_is_removed(self) -> None:
        child = self.prepare(hours=72)
        lock = tf._lock_path(child)
        report = tf.gc(root=self.root)
        self.assertIn(str(child), report["removed"])
        self.assertFalse(lock.exists())

    def test_skips_symlink_child_and_keeps_target(self) -> None:
        target = self._tmp / "outside-target"
        target.mkdir()
        (target / "keep.txt").write_text("user data", encoding="utf-8")
        link = self.root / self.next_name()
        try:
            link.symlink_to(target, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is not available on this host")
        self.addCleanup(link.unlink)
        report = tf.gc(root=self.root)
        self.assertTrue(any(str(link) in item for item in report["skipped"]))
        self.assertTrue(target.exists())
        self.assertTrue((target / "keep.txt").is_file())

    def test_rejects_linked_lock_directory(self) -> None:
        external = self._tmp / "external-locks"
        external.mkdir()
        (external / "victim.lock").write_text("external", encoding="utf-8")
        link = self.root / tf.LOCK_DIRNAME
        try:
            link.symlink_to(external, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is not available on this host")
        self.addCleanup(link.unlink)
        with self.assertRaises(ValueError):
            tf.begin(root=self.root)
        with self.assertRaises(ValueError):
            tf.gc(root=self.root)
        owned = self.root / "ownedtask"
        owned.mkdir()
        write_marker(owned)
        with self.assertRaises(ValueError):
            tf.abort(owned, root=self.root)
        self.assertTrue((external / "victim.lock").is_file())
        self.assertTrue(owned.exists())

    def test_skips_linked_lock_file_without_touching_target(self) -> None:
        child = self.prepare(hours=72)
        external = self._tmp / "external.lock"
        external.write_text("external", encoding="utf-8")
        lock = tf._lock_path(child)
        lock.unlink()
        try:
            lock.symlink_to(external)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is not available on this host")
        self.addCleanup(lock.unlink)
        report = tf.gc(root=self.root)
        self.assertTrue(child.exists())
        self.assertTrue(external.is_file())
        self.assertTrue(any(str(child) in item for item in report["skipped"]))

    def test_missing_root_is_a_noop(self) -> None:
        report = tf.gc(root=self._tmp / "missing-root")
        self.assertEqual(report["removed"], [])


class TestAbort(TaskFilesTestCase):
    def test_removes_owned_dir_with_contents(self) -> None:
        task_dir = self.begin()
        make_png(task_dir / "round_1.png")
        (task_dir / "prompt.txt").write_text("p", encoding="utf-8")
        removed = tf.abort(task_dir, root=self.root)
        self.assertEqual(removed.resolve(), task_dir.resolve())
        self.assertFalse(task_dir.exists())

    def test_tolerates_concurrent_removal(self) -> None:
        task_dir = self.begin()
        real_rmtree = tf._rmtree

        def remove_then_vanish(path: Path) -> None:
            real_rmtree(path)
            raise FileNotFoundError(2, "removed concurrently")

        with patch.object(tf, "_rmtree", side_effect=remove_then_vanish):
            removed = tf.abort(task_dir, root=self.root)
        self.assertEqual(removed.resolve(), task_dir.resolve())
        self.assertFalse(task_dir.exists())

    def test_reports_partial_removal(self) -> None:
        task_dir = self.begin()
        with patch.object(
            tf, "_rmtree", side_effect=FileNotFoundError(2, "vanished entry")
        ), self.assertRaises(OSError):
            tf.abort(task_dir, root=self.root)
        self.assertTrue(task_dir.exists())

    def test_fails_fast_while_task_dir_is_locked(self) -> None:
        task_dir = self.begin()
        handle = tf._acquire_lock(tf._lock_path(task_dir))
        try:
            with self.assertRaises(OSError) as ctx:
                tf.abort(task_dir, root=self.root)
            self.assertIn("locked", str(ctx.exception))
        finally:
            tf._release_quietly(handle)
        self.assertTrue(task_dir.exists())

    def test_rejects_unmarked_dir(self) -> None:
        unmarked = self.root / "unmarked"
        unmarked.mkdir()
        with self.assertRaises(ValueError):
            tf.abort(unmarked, root=self.root)
        self.assertTrue(unmarked.exists())

    def test_rejects_out_of_root_dir(self) -> None:
        outside = self._tmp / "outside"
        outside.mkdir()
        write_marker(outside)
        with self.assertRaises(ValueError):
            tf.abort(outside, root=self.root)
        self.assertTrue(outside.exists())

    def test_rejects_missing_dir(self) -> None:
        with self.assertRaises(ValueError):
            tf.abort(self.root / "ghost", root=self.root)

    def test_rejects_task_id_mismatch(self) -> None:
        task_dir = self.begin()
        write_marker(task_dir, task_id="other-id")
        with self.assertRaises(ValueError):
            tf.abort(task_dir, root=self.root)
        self.assertTrue(task_dir.exists())


class TestPublish(TaskFilesTestCase):
    def prepare_task_with_image(self) -> tuple[Path, Path]:
        task_dir = self.begin()
        image = make_png(task_dir / "round_1.png")
        return task_dir, image

    def test_delivers_to_explicit_final_path_and_cleans_task_dir(self) -> None:
        task_dir, image = self.prepare_task_with_image()
        expected_size = image.stat().st_size
        with tempfile.TemporaryDirectory() as out:
            final = Path(out) / "delivered.png"
            result = tf.publish(task_dir, image, final_path=final, root=self.root)
            self.assertEqual(result, final)
            self.assertTrue(final.is_file())
            validate_image_file(result)
            self.assertEqual(final.stat().st_size, expected_size)
            self.assertFalse(task_dir.exists())

    def test_unique_name_lands_in_output_dir(self) -> None:
        task_dir, image = self.prepare_task_with_image()
        with tempfile.TemporaryDirectory() as out:
            result = tf.publish(task_dir, image, output_dir=Path(out), root=self.root)
            self.assertEqual(result.parent, Path(out).resolve())
            self.assertTrue(result.stem.startswith(image.stem))
            validate_image_file(result)
            self.assertFalse(task_dir.exists())

    def test_tolerates_concurrent_task_dir_removal(self) -> None:
        task_dir, image = self.prepare_task_with_image()
        real_rmtree = tf._rmtree

        def remove_then_vanish(path: Path) -> None:
            real_rmtree(path)
            raise FileNotFoundError(2, "removed concurrently")

        with tempfile.TemporaryDirectory() as out, patch.object(tf, "_rmtree", side_effect=remove_then_vanish):
            result = tf.publish(task_dir, image, output_dir=Path(out), root=self.root)
            self.assertTrue(result.is_file())
        self.assertFalse(task_dir.exists())

    def test_rejects_selected_image_outside_task_dir(self) -> None:
        task_dir, _ = self.prepare_task_with_image()
        stranger = make_png(self._tmp / "stranger.png")
        with self.assertRaises(ValueError):
            tf.publish(task_dir, stranger, output_dir=self.root, root=self.root)
        self.assertTrue(task_dir.exists())

    def test_rejects_target_inside_task_dir(self) -> None:
        task_dir, image = self.prepare_task_with_image()
        with self.assertRaises(ValueError):
            tf.publish(task_dir, image, final_path=task_dir / "final.png", root=self.root)

    def test_keeps_task_dir_when_target_parent_is_a_file(self) -> None:
        task_dir, image = self.prepare_task_with_image()
        blocker = self._tmp / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        with self.assertRaises(OSError):
            tf.publish(task_dir, image, final_path=blocker / "out.png", root=self.root)
        self.assertTrue(task_dir.exists())
        self.assertFalse((blocker / "out.png").exists())

    def test_keeps_task_dir_and_no_partial_file_when_final_is_a_directory(self) -> None:
        task_dir, image = self.prepare_task_with_image()
        with tempfile.TemporaryDirectory() as out:
            final_dir = Path(out) / "occupied"
            final_dir.mkdir()
            with self.assertRaises(OSError):
                tf.publish(task_dir, image, final_path=final_dir, root=self.root)
            self.assertTrue(task_dir.exists())
            self.assertEqual(list(Path(out).iterdir()), [final_dir])

    def test_rejects_non_image_selection(self) -> None:
        task_dir, _ = self.prepare_task_with_image()
        fake = task_dir / "fake.png"
        fake.write_text("this is not an image", encoding="utf-8")
        with self.assertRaises((ValueError, OSError)):
            tf.publish(task_dir, fake, output_dir=self.root, root=self.root)
        self.assertTrue(task_dir.exists())

    def test_rejects_missing_selection(self) -> None:
        task_dir, _ = self.prepare_task_with_image()
        with self.assertRaises(ValueError):
            tf.publish(task_dir, task_dir / "missing.png", output_dir=self.root, root=self.root)

    def test_reports_partial_task_dir_removal(self) -> None:
        task_dir, image = self.prepare_task_with_image()
        with tempfile.TemporaryDirectory() as out, patch.object(
            tf, "_rmtree", side_effect=FileNotFoundError(2, "vanished entry")
        ):
            out_path = Path(out)
            with self.assertRaises(OSError) as ctx:
                tf.publish(task_dir, image, output_dir=out_path, root=self.root)
            self.assertIn("still exists", str(ctx.exception))
            self.assertEqual(len(list(out_path.iterdir())), 1)
        self.assertTrue(task_dir.exists())

    def test_publish_leaves_no_tmp_when_copy_fails(self) -> None:
        task_dir, image = self.prepare_task_with_image()
        with tempfile.TemporaryDirectory() as out, patch.object(
            tf.os, "fsync", side_effect=OSError("simulated fsync failure")
        ):
            out_path = Path(out)
            with self.assertRaises(OSError):
                tf.publish(task_dir, image, output_dir=out_path, root=self.root)
            self.assertEqual(list(out_path.iterdir()), [])
        self.assertTrue(task_dir.exists())

    def test_fails_fast_while_task_dir_is_locked(self) -> None:
        task_dir, image = self.prepare_task_with_image()
        handle = tf._acquire_lock(tf._lock_path(task_dir))
        try:
            with self.assertRaises(OSError) as ctx:
                tf.publish(task_dir, image, output_dir=self.root, root=self.root)
            self.assertIn("locked", str(ctx.exception))
        finally:
            tf._release_quietly(handle)
        self.assertTrue(task_dir.exists())


class TestPlatformBehavior(TaskFilesTestCase):
    def test_root_dirname_scopes_posix_roots_to_the_user(self) -> None:
        self.assertEqual(tf._root_dirname("nt", 1001), "sensenova-tasks")
        self.assertEqual(tf._root_dirname("posix", 1001), "sensenova-tasks-1001")
        self.assertEqual(tf._root_dirname("posix", None), "sensenova-tasks")

    def test_rmtree_retries_read_only_entries(self) -> None:
        target = self._tmp / "readonly-dir"
        target.mkdir()
        blocked = target / "blocked.txt"
        blocked.write_text("x", encoding="utf-8")
        os.chmod(blocked, stat.S_IREAD)
        self.addCleanup(lambda: os.path.exists(blocked) and os.chmod(blocked, stat.S_IWRITE))
        tf._rmtree(target)
        self.assertFalse(target.exists())

    def test_rmtree_error_callback_retries_deletion_for_os_open(self) -> None:
        target = self._tmp / "open-failed-dir"
        target.mkdir()
        (target / "inner.txt").write_text("x", encoding="utf-8")
        tf._on_rmtree_error(os.open, target, PermissionError(13, "denied"))
        self.assertFalse(target.exists())

    def test_rmtree_error_callback_accepts_legacy_exc_info_tuple(self) -> None:
        target = self._tmp / "legacy-dir"
        target.mkdir()
        tf._on_rmtree_error(
            os.open, target, (PermissionError, PermissionError(13, "denied"), None)
        )
        self.assertFalse(target.exists())

    def test_rmtree_error_callback_never_chmods_a_link_target(self) -> None:
        tree = self._tmp / "tree"
        tree.mkdir()
        external = self._tmp / "external-user-file.txt"
        external.write_text("user data", encoding="utf-8")
        os.chmod(external, stat.S_IREAD)  # a marker any following chmod would clear
        self.addCleanup(lambda: os.chmod(external, stat.S_IWRITE))
        link = tree / "link.txt"
        try:
            link.symlink_to(external)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is not available on this host")
        before = os.stat(external).st_mode
        tf._on_rmtree_error(os.unlink, link, PermissionError(13, "denied"))
        self.assertFalse(os.path.lexists(link))
        self.assertEqual(os.stat(external).st_mode, before)
        self.assertEqual(external.read_text(encoding="utf-8"), "user data")

    def test_rmtree_error_callback_reraises_other_errors(self) -> None:
        path = self._tmp / "kept.txt"
        path.write_text("x", encoding="utf-8")
        with self.assertRaises(IsADirectoryError):
            tf._on_rmtree_error(os.unlink, path, IsADirectoryError(21, "not a file"))

    def test_root_privacy_predicate(self) -> None:
        self.assertTrue(tf._root_is_private(1000, 0o40700, 1000))
        self.assertFalse(tf._root_is_private(1001, 0o40700, 1000))
        self.assertFalse(tf._root_is_private(1000, 0o40755, 1000))

    def test_private_root_check_is_a_noop_on_windows(self) -> None:
        tf._require_private_root(self._tmp)  # must not raise on nt


class TestFormalOutputDir(unittest.TestCase):
    def test_env_override_wins(self) -> None:
        from sn_image_base import configs as configs_module

        original = configs_module.global_configs.SN_IMAGE_OUTPUT_DIR
        configs_module.global_configs.SN_IMAGE_OUTPUT_DIR = "X:/custom-out"
        try:
            self.assertEqual(configs_module.default_formal_output_dir(), Path("X:/custom-out"))
        finally:
            configs_module.global_configs.SN_IMAGE_OUTPUT_DIR = original

    def test_default_is_pictures(self) -> None:
        from sn_image_base import configs as configs_module

        original = configs_module.global_configs.SN_IMAGE_OUTPUT_DIR
        configs_module.global_configs.SN_IMAGE_OUTPUT_DIR = ""
        try:
            self.assertEqual(
                configs_module.default_formal_output_dir(),
                Path.home() / "Pictures" / "SenseNova",
            )
        finally:
            configs_module.global_configs.SN_IMAGE_OUTPUT_DIR = original


if __name__ == "__main__":
    unittest.main()
