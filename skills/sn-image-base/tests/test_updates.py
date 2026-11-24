from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from sn_image_base import updates


def release_payload(version: str = "v1.1.0") -> dict:
    return {
        "tag_name": version,
        "body": "## Repository update checks\n\nInstalled copies can check releases.",
        "html_url": f"https://github.com/Ryderey/SenseNova-Skills/releases/tag/{version}",
        "assets": [
            {
                "name": updates.MANIFEST_ASSET_NAME,
                "browser_download_url": "https://example.test/release.json",
            }
        ],
    }


def release_manifest(version: str = "1.1.0") -> dict:
    return {
        "schema_version": 1,
        "version": version,
        "min_supported_version": "1.0.0",
        "update_required": False,
        "severity": "recommended",
        "summary": "Repository release checks are available.",
        "release_notes": "https://example.test/release",
        "retired_models": [
            {
                "name": "sensenova-u1.5-*",
                "status": "retired",
                "replacement": "sensenova-u1.6-lite",
            }
        ],
    }


class VersionTests(unittest.TestCase):
    def test_parse_version_accepts_tags_and_rejects_invalid_values(self) -> None:
        self.assertEqual(updates.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(updates.parse_version(" 1.2.3 "), (1, 2, 3))
        for value in ("", "1.2", "v1.2.3-beta", "latest", None, 123):
            self.assertIsNone(updates.parse_version(value))

    def test_local_version_comes_from_the_installed_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            (base / "VERSION").write_text("1.1.0\n", encoding="utf-8")
            self.assertEqual(updates.local_version(base), "1.1.0")
            (base / "VERSION").unlink()
            self.assertEqual(updates.local_version(base), "")


    def test_model_patterns_use_exact_match_without_wildcard(self) -> None:
        self.assertTrue(updates._matches_model("sensenova-u1-fast", "sensenova-u1-fast"))
        self.assertFalse(
            updates._matches_model(
                "sensenova-u1-fast", "sensenova-u1-fast-sensenova-u1-fast"
            )
        )
        self.assertTrue(
            updates._matches_model("sensenova-u1.5-*", "sensenova-u1.5-fast")
        )


class FetchTests(unittest.TestCase):
    def test_latest_release_uses_attached_manifest(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url == updates.LATEST_RELEASE_URL:
                return httpx.Response(200, json=release_payload())
            if str(request.url) == "https://example.test/release.json":
                return httpx.Response(200, json=release_manifest())
            raise AssertionError(request.url)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            release = updates.fetch_latest_release(client)

        self.assertIsNotNone(release)
        self.assertEqual(release.version, "1.1.0")
        self.assertEqual(release.summary, "Repository release checks are available.")
        self.assertEqual(release.min_supported_version, "1.0.0")
        self.assertEqual(release.retired_models[0].pattern, "sensenova-u1.5-*")

    def test_release_without_manifest_is_not_downgraded(self) -> None:
        payload = release_payload("v1.1.0")
        payload["assets"] = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertNotIn("Authorization", request.headers)
            return httpx.Response(200, json=payload)

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            self.assertRaisesRegex(updates.UpdateCheckError, "missing"),
        ):
            updates.fetch_latest_release(client)

    def test_manifest_tag_mismatch_is_not_downgraded(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url == updates.LATEST_RELEASE_URL:
                return httpx.Response(200, json=release_payload("v1.1.0"))
            return httpx.Response(200, json=release_manifest("9.9.9"))

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            self.assertRaises(updates.UpdateCheckError),
        ):
            updates.fetch_latest_release(client)

    def test_manifest_asset_failure_is_not_downgraded(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url == updates.LATEST_RELEASE_URL:
                return httpx.Response(200, json=release_payload("v1.1.0"))
            return httpx.Response(503)

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            self.assertRaises(updates.UpdateCheckError),
        ):
            updates.fetch_latest_release(client)

    def test_manifest_download_is_bounded_while_streaming(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url == updates.LATEST_RELEASE_URL:
                return httpx.Response(200, json=release_payload("v1.1.0"))
            return httpx.Response(200, content=b"x" * 1_000_001)

        with (
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
            self.assertRaisesRegex(updates.UpdateCheckError, "too large"),
        ):
            updates.fetch_latest_release(client)

    def test_invalid_manifest_fields_are_rejected(self) -> None:
        cases = (
            {"min_supported_version": "not-a-version"},
            {"min_supported_version": "v1.0.0"},
            {"update_required": "true"},
            {"retired_models": [{"name": "old-*", "status": "deprecated"}]},
            {"version": "v1.1.0"},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                manifest = release_manifest()
                manifest.update(changes)

                def handler(
                    request: httpx.Request, manifest: dict = manifest
                ) -> httpx.Response:
                    if request.url == updates.LATEST_RELEASE_URL:
                        return httpx.Response(200, json=release_payload("v1.1.0"))
                    return httpx.Response(200, json=manifest)

                with (
                    httpx.Client(transport=httpx.MockTransport(handler)) as client,
                    self.assertRaises(updates.UpdateCheckError),
                ):
                    updates.fetch_latest_release(client)

    def test_invalid_proxy_configuration_fails_open(self) -> None:
        with (
            patch.object(
                updates.httpx,
                "Client",
                side_effect=httpx.InvalidURL("invalid proxy"),
            ),
            self.assertRaises(updates.UpdateCheckError),
        ):
            updates.fetch_latest_release()

    def test_missing_release_and_network_failure_are_distinct(self) -> None:
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(404))
        ) as client:
            self.assertIsNone(updates.fetch_latest_release(client))

        def offline(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("offline", request=request)

        with (
            httpx.Client(transport=httpx.MockTransport(offline)) as client,
            self.assertRaises(updates.UpdateCheckError),
        ):
            updates.fetch_latest_release(client)


class CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "sn-image-base"
        self.base.mkdir()
        (self.base / "VERSION").write_text("1.0.0\n", encoding="utf-8")
        self.cache = self.root / "cache" / "update-check.json"
        self.release = updates.ReleaseInfo(
            version="1.1.0",
            summary="Update available.",
            release_url="https://example.test/release",
            min_supported_version="1.0.0",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def check(self, **kwargs):
        return updates.check_for_updates(
            base_skill_dir=self.base,
            cache_path=self.cache,
            **kwargs,
        )

    def test_notice_is_deduplicated_and_force_check_repeats_it(self) -> None:
        with patch.object(
            updates, "fetch_latest_release", return_value=self.release
        ) as fetch:
            first = self.check(now=100)
            second = self.check(now=200)
            forced = self.check(force=True, now=300)

        self.assertEqual(first.status, "available")
        self.assertIsNotNone(first.notice)
        self.assertIsNone(second.notice)
        self.assertIsNotNone(forced.notice)
        self.assertEqual(fetch.call_count, 2)

    def test_expired_cache_checks_the_repository_again(self) -> None:
        with patch.object(
            updates, "fetch_latest_release", return_value=self.release
        ) as fetch:
            self.check(now=100)
            self.check(now=100 + updates.CACHE_TTL_SECONDS + 1)

        self.assertEqual(fetch.call_count, 2)

    def test_corrupt_fresh_cache_is_replaced_by_a_real_check(self) -> None:
        self.cache.parent.mkdir(parents=True)
        self.cache.write_text(
            json.dumps({"checked_at": 100, "release": {"version": 123}}),
            encoding="utf-8",
        )
        with patch.object(
            updates, "fetch_latest_release", return_value=self.release
        ) as fetch:
            result = self.check(now=101)

        self.assertEqual(result.status, "available")
        fetch.assert_called_once()

    def test_posix_cache_directory_is_owner_only_and_checked_on_read(self) -> None:
        if updates.os.name != "posix":
            self.skipTest("POSIX permissions")
        cache = self.root / "private" / "update-check.json"
        self.assertTrue(updates._prepare_cache_dir(cache.parent))
        self.assertEqual(cache.parent.stat().st_mode & 0o077, 0)
        cache.write_text(json.dumps({"checked_at": 100}), encoding="utf-8")
        self.assertEqual(updates._read_cache(cache), {"checked_at": 100})
        cache.parent.chmod(0o755)
        self.assertEqual(updates._read_cache(cache), {})

    def test_windows_ignores_shared_temp_fallback(self) -> None:
        if updates.os.name == "posix":
            self.skipTest("Windows cache policy")
        primary = self.root / "missing" / "update-check.json"
        blocked = self.root / "blocked"
        blocked.write_text("not a directory", encoding="utf-8")
        target = blocked / "other-check.json"
        temp_root = self.root / "temp"
        with patch.object(
            updates.tempfile, "gettempdir", return_value=str(temp_root)
        ):
            fallback = updates._fallback_cache_path(primary)
            fallback.parent.mkdir(parents=True, exist_ok=True)
            fallback.write_text(json.dumps({"checked_at": 100}), encoding="utf-8")
            self.assertEqual(updates._read_cache(primary), {})
            self.assertFalse(updates._write_cache(target, {"checked_at": 100}))
            self.assertFalse(updates._fallback_cache_path(target).exists())

    def test_posix_unwritable_primary_cache_uses_temp_fallback(self) -> None:
        if updates.os.name != "posix":
            self.skipTest("POSIX temp fallback")
        blocked = self.root / "blocked"
        blocked.write_text("not a directory", encoding="utf-8")
        cache = blocked / "update-check.json"
        temp_root = self.root / "temp"
        fallback = None
        with (
            patch.object(updates.tempfile, "gettempdir", return_value=str(temp_root)),
            patch.object(
                updates, "fetch_latest_release", return_value=self.release
            ) as fetch,
        ):
            fallback = updates._fallback_cache_path(cache)
            first = updates.check_for_updates(
                base_skill_dir=self.base, cache_path=cache, now=100
            )
            second = updates.check_for_updates(
                base_skill_dir=self.base, cache_path=cache, now=200
            )

        self.assertEqual(first.status, "available")
        self.assertIsNone(second.notice)
        self.assertIsNotNone(fallback)
        self.assertTrue(fallback.is_file())
        fetch.assert_called_once()

    def test_network_failure_is_negatively_cached_without_blocking_work(self) -> None:
        with patch.object(
            updates,
            "fetch_latest_release",
            side_effect=updates.UpdateCheckError("offline"),
        ) as fetch:
            first = self.check(now=100)
            second = self.check(now=200)

        self.assertEqual(first.status, "unavailable")
        self.assertEqual(second.status, "unavailable")
        self.assertFalse(first.blocking)
        self.assertFalse(second.blocking)
        fetch.assert_called_once()

    def test_required_update_repeats_reason_while_blocking(self) -> None:
        required = updates.ReleaseInfo(
            version="2.0.0",
            summary="Required update.",
            release_url="https://example.test/release",
            min_supported_version="2.0.0",
        )
        with patch.object(
            updates, "fetch_latest_release", return_value=required
        ) as fetch:
            first = self.check(now=100)
            second = self.check(now=200)
            cached = json.loads(self.cache.read_text(encoding="utf-8"))
            third = self.check(now=100 + updates.CACHE_TTL_SECONDS + 1)

        self.assertEqual(first.status, "required")
        self.assertTrue(first.blocking)
        self.assertIsNotNone(second.notice)
        self.assertTrue(second.blocking)
        self.assertEqual(cached["checked_at"], 100)
        self.assertTrue(third.blocking)
        self.assertEqual(fetch.call_count, 2)

    def test_advisory_notice_stays_deduplicated_across_network_failure(self) -> None:
        with patch.object(
            updates,
            "fetch_latest_release",
            side_effect=[self.release, updates.UpdateCheckError("offline")],
        ) as fetch:
            first = self.check(now=100)
            failed = self.check(now=100 + updates.CACHE_TTL_SECONDS + 1)
            cached = self.check(now=100 + updates.CACHE_TTL_SECONDS + 2)

        self.assertIsNotNone(first.notice)
        self.assertIsNone(failed.notice)
        self.assertIsNone(cached.notice)
        self.assertEqual(fetch.call_count, 2)

    def test_known_required_release_survives_network_failure(self) -> None:
        required = updates.ReleaseInfo(
            version="2.0.0",
            summary="Required update.",
            release_url="https://example.test/release",
            min_supported_version="2.0.0",
        )
        with patch.object(
            updates,
            "fetch_latest_release",
            side_effect=[required, updates.UpdateCheckError("offline")],
        ) as fetch:
            first = self.check(now=100)
            failed = self.check(now=100 + updates.CACHE_TTL_SECONDS + 1)
            cached = self.check(now=100 + updates.CACHE_TTL_SECONDS + 2)

        self.assertTrue(first.blocking)
        self.assertEqual(failed.status, "required")
        self.assertTrue(failed.blocking)
        self.assertEqual(cached.status, "required")
        self.assertTrue(cached.blocking)
        self.assertEqual(fetch.call_count, 2)

    def test_required_notice_lists_each_needed_remedy(self) -> None:
        release = updates.ReleaseInfo(
            version="2.0.0",
            summary="Required update.",
            release_url="https://example.test/release",
            min_supported_version="2.0.0",
            retired_models=(updates.RetiredModel("old-*", "new"),),
        )
        with patch.object(updates, "fetch_latest_release", return_value=release):
            result = self.check(models=("old-model",), now=100)

        self.assertEqual(
            result.notice.remedies,
            ("upgrade the installed bundle", "replace retired model configuration"),
        )

    def test_404_preserves_known_required_release(self) -> None:
        required = updates.ReleaseInfo(
            version="2.0.0",
            summary="Required update.",
            release_url="https://example.test/release",
            min_supported_version="2.0.0",
        )
        with patch.object(
            updates, "fetch_latest_release", side_effect=[required, None]
        ) as fetch:
            first = self.check(now=100)
            missing = self.check(now=100 + updates.CACHE_TTL_SECONDS + 1)

        self.assertTrue(first.blocking)
        self.assertEqual(missing.status, "required")
        self.assertTrue(missing.blocking)
        cached = json.loads(self.cache.read_text(encoding="utf-8"))
        self.assertIsNotNone(cached["release"])
        self.assertTrue(cached["check_failed"])
        self.assertEqual(fetch.call_count, 2)

    def test_retired_fallback_model_blocks_even_on_current_version(self) -> None:
        release = updates.ReleaseInfo(
            version="1.1.0",
            summary="U1.6 migration.",
            release_url="https://example.test/release",
            min_supported_version="1.0.0",
            retired_models=(
                updates.RetiredModel("sensenova-u1.5-*", "sensenova-u1.6-lite"),
            ),
        )
        (self.base / "VERSION").write_text("1.1.0\n", encoding="utf-8")
        with patch.object(updates, "fetch_latest_release", return_value=release):
            result = self.check(
                models=("sensenova-u1.6-lite", "sensenova-u1.5-fast"),
                now=100,
            )

        self.assertEqual(result.status, "required")
        self.assertEqual(result.notice.replacement_model, "sensenova-u1.6-lite")

    def test_informational_release_is_not_a_warning(self) -> None:
        release = updates.ReleaseInfo(
            version="1.1.0",
            summary="Optional release.",
            release_url="https://example.test/release",
            min_supported_version="1.0.0",
            severity="info",
        )
        with patch.object(updates, "fetch_latest_release", return_value=release):
            result = self.check(now=100)

        self.assertEqual(result.status, "available")
        self.assertEqual(result.notice.level, "info")
        self.assertFalse(result.blocking)

    def test_required_marker_blocks_older_install(self) -> None:
        release = updates.ReleaseInfo(
            version="1.1.0",
            summary="Required release marker.",
            release_url="https://example.test/release",
            min_supported_version="1.0.0",
            update_required=True,
        )
        with patch.object(updates, "fetch_latest_release", return_value=release):
            result = self.check(now=100)

        self.assertEqual(result.status, "required")
        self.assertTrue(result.blocking)

    def test_required_marker_does_not_block_current_or_newer_install(self) -> None:
        for flags in ({"update_required": True}, {"severity": "required"}):
            for local in ("1.1.0", "2.0.0"):
                with self.subTest(flags=flags, local=local):
                    (self.base / "VERSION").write_text(local, encoding="utf-8")
                    release = updates.ReleaseInfo(
                        version="1.1.0",
                        summary="Required release marker.",
                        release_url="https://example.test/release",
                        min_supported_version="1.0.0",
                        **flags,
                    )
                    with patch.object(
                        updates, "fetch_latest_release", return_value=release
                    ):
                        result = self.check(force=True, now=100)

                    self.assertEqual(result.status, "current")
                    self.assertFalse(result.blocking)

    def test_equal_or_older_release_is_current(self) -> None:
        (self.base / "VERSION").write_text("1.1.0\n", encoding="utf-8")
        with patch.object(updates, "fetch_latest_release", return_value=self.release):
            result = self.check(now=100)

        self.assertEqual(result.status, "current")
        self.assertIsNone(result.notice)


class InstallationTests(unittest.TestCase):
    def test_copy_inside_unrelated_git_repository_is_not_git_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            base = root / ".claude" / "skills" / "sn-image-base"
            base.mkdir(parents=True)
            self.assertEqual(updates.installation_kind(base), "copy")

    def test_canonical_repository_checkout_is_git_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            (root / "release.json").write_text("{}", encoding="utf-8")
            base = root / "skills" / "sn-image-base"
            base.mkdir(parents=True)
            self.assertEqual(updates.installation_kind(base), "git")

    def test_symlink_above_skill_parent_does_not_override_git_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ancestor = root / "linked"
            repo = ancestor / "project"
            (repo / ".git").mkdir(parents=True)
            (repo / "release.json").write_text("{}", encoding="utf-8")
            base = repo / "skills" / "sn-image-base"
            base.mkdir(parents=True)
            with patch.object(
                updates, "_is_symlink_path", side_effect=lambda path: path == ancestor
            ):
                self.assertEqual(updates.installation_kind(base), "git")

    def test_skill_or_parent_symlink_selects_symlink_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir) / "sn-image-base"
            base.mkdir()
            with patch.object(updates, "_is_symlink_path", return_value=True):
                self.assertEqual(updates.installation_kind(base), "symlink")

    def test_cache_path_is_isolated_per_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first" / "sn-image-base"
            second = root / "second" / "sn-image-base"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            with patch.dict(updates.os.environ, {"LOCALAPPDATA": str(root / "cache")}):
                self.assertNotEqual(updates._cache_path(first), updates._cache_path(second))


class NoticeTests(unittest.TestCase):
    def notice(self) -> updates.UpdateNotice:
        release = updates.ReleaseInfo(
            version="1.1.0",
            summary="Repository release checks are available.",
            release_url="https://example.test/release",
            min_supported_version="1.0.0",
            retired_models=(
                updates.RetiredModel("sensenova-u1.5-*", "sensenova-u1.6-lite"),
            ),
        )
        return updates.UpdateNotice(
            local_version="1.0.0",
            release=release,
            level="required",
            reason="configured model 'sensenova-u1.5-fast' is retired",
            replacement_model="sensenova-u1.6-lite",
        )

    def test_copy_install_notice_preserves_user_configuration(self) -> None:
        with patch.object(updates, "installation_kind", return_value="copy"):
            text = updates.format_update_notice(self.notice())

        self.assertIn("[UPDATE REQUIRED]", text)
        self.assertIn("sensenova-u1.6-lite", text)
        self.assertIn("Preserve `.env`", text)
        self.assertIn("sn-image-resume", text)

    def test_git_and_symlink_install_notices_use_their_update_path(self) -> None:
        with patch.object(updates, "installation_kind", return_value="git"):
            git_text = updates.format_update_notice(self.notice())
        with patch.object(updates, "installation_kind", return_value="symlink"):
            symlink_text = updates.format_update_notice(self.notice())

        self.assertIn("git pull --ff-only", git_text)
        self.assertIn("git checkout v1.1.0", git_text)
        self.assertIn("behind the symlink", symlink_text)

    def test_force_check_prints_status_and_returns_blocking_state(self) -> None:
        result = updates.UpdateCheck(
            local_version="1.0.0",
            latest_version="1.1.0",
            status="required",
            notice=self.notice(),
        )
        output = io.StringIO()
        with (
            patch.object(updates, "check_for_updates", return_value=result),
            patch.object(updates, "installation_kind", return_value="copy"),
        ):
            emitted = updates.emit_update_check(force=True, stream=output)

        self.assertTrue(emitted.blocking)
        self.assertIn("[UPDATE REQUIRED]", output.getvalue())

    def test_automatic_check_can_be_disabled(self) -> None:
        with (
            patch.dict(updates.os.environ, {"SN_SKILLS_NO_UPDATE_CHECK": "1"}),
            patch.object(updates, "check_for_updates") as check,
        ):
            result = updates.emit_update_check(stream=io.StringIO())

        self.assertEqual(result.status, "disabled")
        check.assert_not_called()

    def test_repository_versions_and_manifest_are_consistent(self) -> None:
        repo = Path(__file__).resolve().parents[3]
        names = (
            "sn-image-base",
            "sn-image-doctor",
            "sn-infographic",
            "sn-image-imitate",
            "sn-image-resume",
        )
        versions = {
            (repo / "skills" / name / "VERSION").read_text(encoding="utf-8").strip()
            for name in names
        }
        manifest = json.loads((repo / "release.json").read_text(encoding="utf-8"))
        self.assertEqual(len(versions), 1)
        version = next(iter(versions))
        self.assertIsNotNone(updates.parse_version(version))
        self.assertEqual(manifest["version"], version)
        self.assertIsNotNone(updates.parse_version(manifest["min_supported_version"]))
        for name in names:
            skill = (repo / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"  version: {version}\n", skill, name)


if __name__ == "__main__":
    unittest.main()
