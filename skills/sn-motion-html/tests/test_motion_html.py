"""Offline checks for the sn-motion-html skills, focused on image mode.

These run the project scripts the same way a host Agent would: as subprocesses
against a temporary project, with no network access and no generation calls.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
REPO_ROOT = SKILL_ROOT.parents[1]
INIT = SCRIPTS / "init_project.py"

TRICKY_TITLE = 'He said "hi" & <b>x</b> \\ 中文标题'
VIDEO_REQUIRED_RELATIVE = (
    "prompts/video-manifest.json",
    ".env",
    ".env.example",
    "assets/video/dives",
    "scripts/seedance_pipeline.py",
)


def load_project_model():
    spec = importlib.util.spec_from_file_location("motion_project_model", SCRIPTS / "project_model.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


project_model = load_project_model()


def make_still(path: Path, colour: str = "#204060", size: tuple[int, int] = (640, 360)) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, colour).save(path)


class ProjectFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sn-motion-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def init(self, *extra: str, project: Path | None = None) -> subprocess.CompletedProcess:
        target = project or (self.tmp / "story project")
        return self.run_script(
            INIT, str(target), "--title", TRICKY_TITLE, *extra
        )

    def run_script(self, script: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=180,
        )


class InitProjectTests(ProjectFixture):
    def test_image_project_ships_no_video_scaffolding(self) -> None:
        project = self.tmp / "story project"
        result = self.init("--media", "images", "--lang", "zh")
        self.assertEqual(result.returncode, 0, result.stderr)

        for relative in VIDEO_REQUIRED_RELATIVE:
            self.assertFalse((project / relative).exists(), f"image project created {relative}")
        self.assertFalse((project / "tmp").exists(), "image project created a tmp directory")

        for record in ("project_model.py", "verify_media.py", "contact_sheet.py", "make_posters.py", "serve_project.py"):
            self.assertTrue((project / "scripts" / record).is_file(), record)

        story = json.loads((project / "content" / "story.json").read_text(encoding="utf-8"))
        self.assertEqual(story["meta"]["mediaMode"], "images")
        self.assertEqual(story["meta"]["lang"], "zh")
        self.assertEqual(story["meta"]["title"], TRICKY_TITLE)
        self.assertNotIn("connectors", story)
        self.assertTrue(all("clip" not in chapter for chapter in story["chapters"]))

    def test_video_project_keeps_video_scaffolding(self) -> None:
        project = self.tmp / "video story"
        result = self.init("--media", "video", "--lang", "en", project=project)
        self.assertEqual(result.returncode, 0, result.stderr)
        for relative in VIDEO_REQUIRED_RELATIVE:
            self.assertTrue((project / relative).exists(), f"video project is missing {relative}")

    def test_title_is_json_and_html_safe(self) -> None:
        project = self.tmp / "story project"
        self.init("--media", "images", "--lang", "en")
        story = json.loads((project / "content" / "story.json").read_text(encoding="utf-8"))
        self.assertEqual(story["meta"]["title"], TRICKY_TITLE)

        index = (project / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("{{TITLE}}", index)
        self.assertIn("&quot;", index)
        self.assertIn("&lt;b&gt;", index)
        self.assertIn("&amp;", index)
        self.assertIn('lang="en"', index)

    def test_non_empty_directory_is_refused_then_force_preserves_content(self) -> None:
        project = self.tmp / "story project"
        self.init("--media", "images")
        story_path = project / "content" / "story.json"
        story_path.write_text('{"meta": {"title": "mine"}, "chapters": []}', encoding="utf-8")
        make_still(project / "assets/images/scenes/keep.webp")

        again = self.run_script(INIT, str(project), "--title", "Other")
        self.assertNotEqual(again.returncode, 0)

        forced = self.run_script(INIT, str(project), "--title", "Other", "--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertIn("mine", story_path.read_text(encoding="utf-8"))
        self.assertTrue((project / "assets/images/scenes/keep.webp").is_file())
        self.assertIn("Preserved existing files", forced.stdout)

    def test_file_output_path_is_refused(self) -> None:
        target = self.tmp / "afile"
        target.write_text("x", encoding="utf-8")
        result = self.run_script(INIT, str(target), "--title", "x")
        self.assertNotEqual(result.returncode, 0)


class StoryValidationTests(unittest.TestCase):
    def story(self, **overrides) -> dict:
        base = {
            "meta": {"title": "T", "style": "cinematic", "ui": "folio", "mediaMode": "images", "lang": "en"},
            "chapters": [{"id": "01-a", "label": "A", "still": "assets/images/scenes/a.webp"}],
        }
        base.update(overrides)
        return base

    def test_explicit_images_wins_over_legacy_video_fields(self) -> None:
        story = self.story(connectors=["assets/video/connectors/a.mp4"])
        story["chapters"][0]["clip"] = "assets/video/dives/a.mp4"
        self.assertEqual(project_model.resolve_media_mode(story), "images")

    def test_missing_mode_falls_back_to_declared_media(self) -> None:
        without_video = self.story()
        without_video["meta"].pop("mediaMode")
        self.assertEqual(project_model.resolve_media_mode(without_video), "images")

        story = self.story(connectors=["assets/video/connectors/a.mp4"])
        story["meta"].pop("mediaMode")
        story["chapters"][0]["clip"] = "assets/video/dives/a.mp4"
        self.assertEqual(project_model.resolve_media_mode(story), "video")

        empty = self.story(connectors=[])
        empty["meta"].pop("mediaMode")
        self.assertEqual(project_model.resolve_media_mode(empty), "images")

    def test_unknown_mode_is_rejected(self) -> None:
        story = self.story()
        story["meta"]["mediaMode"] = "gallery"
        with self.assertRaises(project_model.ProjectError):
            project_model.resolve_media_mode(story)

    def test_story_problems_are_reported(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="sn-motion-validate-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)

        cases = {
            "empty chapters": {"chapters": []},
            "duplicate id": {"chapters": [
                {"id": "a", "label": "A", "still": "assets/images/scenes/a.webp"},
                {"id": "a", "label": "A2", "still": "assets/images/scenes/a.webp"},
            ]},
            "unsafe id": {"chapters": [{"id": "../x", "label": "A", "still": "assets/images/scenes/a.webp"}]},
            "escaping still": {"chapters": [{"id": "a", "label": "A", "still": "../../etc/passwd"}]},
            "absolute still": {"chapters": [{"id": "a", "label": "A", "still": "C:/x/a.webp"}]},
            "zero span": {"chapters": [{"id": "a", "label": "A", "still": "assets/images/scenes/a.webp", "span": 0}]},
            "bad copyPosition": {"chapters": [
                {"id": "a", "label": "A", "still": "assets/images/scenes/a.webp", "copyPosition": "top"}
            ]},
            "bad style": {"meta": {"title": "T", "style": "watercolor"}},
            "bad lang": {"meta": {"title": "T", "lang": "fr"}},
        }
        for name, override in cases.items():
            with self.subTest(case=name):
                story = self.story()
                story.update(override)
                if "meta" in override:
                    story["meta"] = {**story["meta"], **override["meta"]}
                problems = project_model.validate_story(root, story, "images")
                self.assertTrue(problems, f"{name} should be rejected")

        self.assertFalse(project_model.validate_story(root, self.story(), "images"))

    def test_video_mode_requires_adjacent_connectors(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="sn-motion-validate-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        story = self.story()
        story["meta"]["mediaMode"] = "video"
        story["chapters"] = [
            {"id": "a", "label": "A", "still": "assets/images/scenes/a.webp", "clip": "assets/video/dives/a.mp4"},
            {"id": "b", "label": "B", "still": "assets/images/scenes/b.webp", "clip": "assets/video/dives/b.mp4"},
        ]
        problems = project_model.validate_story(root, story, "video")
        self.assertTrue(any("connector" in problem for problem in problems))
        story["connectors"] = ["assets/video/connectors/a-b.mp4"]
        self.assertFalse(project_model.validate_story(root, story, "video"))


class ImageModeToolingTests(ProjectFixture):
    def build_project(self) -> Path:
        project = self.tmp / "story project"
        self.init("--media", "images", "--lang", "en", project=project)
        story = json.loads((project / "content" / "story.json").read_text(encoding="utf-8"))
        story["chapters"] = [
            {"id": "01-a", "label": "第一幕", "title": "One", "still": "assets/images/scenes/01-a.webp"},
            {"id": "02-b", "label": "第二幕", "title": "Two", "still": "assets/images/scenes/02-b.webp"},
        ]
        story["meta"]["title"] = "T"
        (project / "content" / "story.json").write_text(
            json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        make_still(project / "assets/images/scenes/01-a.webp")
        make_still(project / "assets/images/scenes/02-b.webp")
        return project

    def no_ffmpeg_env(self) -> dict:
        env = dict(os.environ)
        empty = self.tmp / "emptybin"
        empty.mkdir(exist_ok=True)
        env["PATH"] = str(empty)
        env["PATHEXT"] = ""
        return env

    def test_still_checks_do_not_need_ffmpeg(self) -> None:
        project = self.build_project()
        env = self.no_ffmpeg_env()
        self.assertIsNone(shutil.which("ffmpeg", path=env["PATH"]))
        self.assertIsNone(shutil.which("ffprobe", path=env["PATH"]))

        verify = self.run_script(project / "scripts" / "verify_media.py", str(project), env=env)
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
        self.assertIn("Media mode: images", verify.stdout)

        output = self.tmp / "sheet.png"
        sheet = self.run_script(
            project / "scripts" / "contact_sheet.py", str(project), "--output", str(output), env=env
        )
        self.assertEqual(sheet.returncode, 0, sheet.stdout + sheet.stderr)
        self.assertTrue(output.is_file())
        self.assertIn("no FFmpeg used", sheet.stdout)
        self.assertFalse((project / "tmp").exists(), "contact sheet wrote into the project")

    def test_missing_and_unreadable_stills_fail(self) -> None:
        project = self.build_project()
        (project / "assets/images/scenes/02-b.webp").unlink()
        verify = self.run_script(project / "scripts" / "verify_media.py", str(project))
        self.assertEqual(verify.returncode, 2)
        self.assertIn("Missing media", verify.stdout)

        (project / "assets/images/scenes/02-b.webp").write_text("not an image", encoding="utf-8")
        verify = self.run_script(project / "scripts" / "verify_media.py", str(project))
        self.assertEqual(verify.returncode, 1)
        self.assertIn("readable image", verify.stdout)

    def test_posters_never_overwrite_masters(self) -> None:
        project = self.build_project()
        scenes = project / "assets/images/scenes"
        make_still(scenes / "03-c.png", "#336633")
        master_bytes = (scenes / "03-c.png").read_bytes()

        result = self.run_script(project / "scripts" / "make_posters.py", str(project))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((scenes / "03-c.webp").is_file())
        self.assertEqual((scenes / "03-c.png").read_bytes(), master_bytes)


class PreviewServerTests(ProjectFixture):
    def test_path_rules(self) -> None:
        allowed = [
            "index.html", "styles.css", "src/app.js", "content/story.json",
            "content/sources.json", "assets/images/scenes/a.webp",
            "assets/images/a.png", "favicon.ico",
        ]
        for relative in allowed:
            self.assertTrue(project_model.web_visible(relative, "images"), relative)

        denied = [
            ".env", ".env.example", ".gitignore", "prompts/style-preamble.txt",
            "scripts/verify_media.py", "docs/production-spec.md", "tmp/frame.png",
            "assets/../../README.md", "content/notes.txt", "src/../.env",
            "assets/video/dives/a.mp4", "prompts/video-manifest.json",
        ]
        for relative in denied:
            self.assertFalse(project_model.web_visible(relative, "images"), relative)
        self.assertTrue(project_model.web_visible("assets/video/dives/a.mp4", "video"))
        self.assertFalse(project_model.web_visible("prompts/video-manifest.json", "video"))

    def test_live_server_serves_only_the_page(self) -> None:
        project = self.tmp / "story project"
        self.init("--media", "images", "--lang", "en", project=project)
        make_still(project / "assets/images/scenes/01-opening.webp")
        make_still(project / "assets/images/scenes/02-destination.webp")
        (project / ".env").write_text("ARK_API_KEY=must-not-be-served\n", encoding="utf-8")

        # Claim a free port up front: the server block-buffers its banner when
        # stdout is a pipe, so reading the printed line back would deadlock.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        server = subprocess.Popen(
            [sys.executable, str(project / "scripts" / "serve_project.py"), str(project), "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(server.kill)

        def fetch(path: str, headers: dict | None = None):
            request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {})
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    return response.status, dict(response.headers), response.read()
            except urllib.error.HTTPError as error:
                return error.code, dict(error.headers), error.read()

        deadline = time.monotonic() + 20
        while True:
            try:
                fetch("/index.html")
                break
            except Exception:  # noqa: BLE001 - the socket may not be listening yet
                if time.monotonic() > deadline:
                    self.fail("preview server did not start listening")
                time.sleep(0.1)

        status, headers, _ = fetch("/index.html")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))

        status, headers, _ = fetch("/assets/images/scenes/01-opening.webp")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "image/webp")

        for path in ("/.env", "/prompts/style-preamble.txt", "/scripts/verify_media.py", "/content/", "/assets/images/"):
            status, _, _ = fetch(path)
            self.assertEqual(status, 404, f"{path} must be refused")

        status, headers, body = fetch(
            "/assets/images/scenes/01-opening.webp", headers={"Range": "bytes=0-9"}
        )
        self.assertEqual(status, 206)
        self.assertEqual(headers.get("Content-Range", "").split("/")[0], "bytes 0-9")
        self.assertEqual(len(body), 10)
        server.kill()


class RuntimeSourceTests(unittest.TestCase):
    """Static guards for behaviour that needs a browser to observe directly."""

    def setUp(self) -> None:
        self.runtime = (SKILL_ROOT / "assets/template/src/motion-runtime.js").read_text(encoding="utf-8")
        self.app = (SKILL_ROOT / "assets/template/src/app.js").read_text(encoding="utf-8")

    def test_image_mode_cannot_load_or_seek_video(self) -> None:
        self.assertIn("config.mediaMode === 'video' && !reduced", self.runtime)
        self.assertIn("if (!videoEnabled || destroyed", self.runtime)
        self.assertIn("if (destroyed || !videoEnabled) return;", self.runtime)
        # The only fetch of a clip sits behind the videoEnabled gate.
        self.assertEqual(self.runtime.count("fetch(segment.clip"), 1)

    def test_reduced_motion_skips_zoom_and_video(self) -> None:
        self.assertIn("if (!reduced && !segment.ready)", self.runtime)
        self.assertIn("@media (prefers-reduced-motion: reduce)", (SKILL_ROOT / "assets/template/styles.css").read_text(encoding="utf-8"))

    def test_image_mode_transition_is_tuned_for_stills_not_clips(self) -> None:
        # A frame-matched video seam only needs a short fade; two unrelated stills
        # need a dissolve long enough to read, and a drift big enough to see.
        self.assertIn("videoEnabled ? 0.14 : 0.8", self.runtime)
        self.assertIn("videoEnabled ? 0.06 : 0.16", self.runtime)

    def test_only_the_arriving_scene_ramps(self) -> None:
        # Ramping both layers down together would let the dark stage bleed through
        # and dip the frame toward black mid-transition.
        self.assertIn("opacity = smooth(1 - (segment.start - y) / dissolve)", self.runtime)
        self.assertIn("opacity = smooth(1 - (y - segment.end) / handoff)", self.runtime)
        self.assertNotIn("opacity = smooth(1 - (segment.start - y) / handoff)", self.runtime)

    def test_motion_can_be_forced_for_review_without_changing_the_default(self) -> None:
        # A machine with OS animations off reports reduce, which hides the designed
        # motion; reviewers need a way past that, but the OS preference still wins.
        self.assertIn("resolveReducedMotion", self.runtime)
        self.assertIn("if (forced === 'full') return false;", self.runtime)
        self.assertIn("if (forced === 'reduce') return true;", self.runtime)
        self.assertIn("matchMedia('(prefers-reduced-motion: reduce)').matches", self.runtime)

    def test_teardown_aborts_work_and_cancels_the_loop(self) -> None:
        for token in ("controller.abort()", "cancelAnimationFrame", "destroyed = true", "removeEventListener"):
            self.assertIn(token, self.runtime)
        self.assertIn("AbortError", self.runtime)

    def test_inactive_chapters_leave_the_accessibility_tree(self) -> None:
        self.assertIn("inert", self.runtime)
        self.assertIn("aria-hidden", self.runtime)

    def test_app_validates_structure_and_source_protocols(self) -> None:
        self.assertIn("SAFE_PROTOCOLS", self.app)
        self.assertIn("must contain at least one chapter", self.app)
        self.assertIn("not valid JSON", self.app)

    def test_missing_lang_falls_back_to_the_content_script(self) -> None:
        # A story authored outside this skill may omit meta.lang; defaulting to
        # English would give Chinese content an English interface.
        self.assertIn("detectLang", self.app)
        self.assertIn("\\u4e00-\\u9fff", self.app)
        self.assertIn("meta.lang === undefined", self.app)
        self.assertIn("lang,\n      mediaMode,", self.app)

    def test_template_is_bilingual(self) -> None:
        self.assertIn("zh:", self.app)
        self.assertIn("en:", self.app)


class LayoutGuardTests(unittest.TestCase):
    """Guards for template layout defects that only show up once rendered."""

    def setUp(self) -> None:
        self.css = (SKILL_ROOT / "assets/template/styles.css").read_text(encoding="utf-8")

    def test_route_labels_can_collapse(self) -> None:
        # A flex item defaults to min-width:auto, which ignores width:0 and left
        # every chapter label permanently expanded in the rendered page.
        rule = re.search(r"\.mh-route__item i\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(rule, "route label rule is missing")
        self.assertIn("width: 0", rule.group(1))
        self.assertIn("min-width: 0", rule.group(1))

    def test_right_positioned_copy_clears_the_route_index(self) -> None:
        rule = re.search(r'\.mh-copy\[data-position="right"\]\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(rule, "right-positioned copy rule is missing")
        self.assertIn("max(", rule.group(1), "right copy must reserve the route gutter")

    def test_mobile_copy_is_scrollable_rather_than_shrunk(self) -> None:
        self.assertIn("max-height: 48svh", self.css)
        self.assertIn("overflow: auto", self.css)

    def test_mobile_copy_does_not_scroll_from_its_own_decoration(self) -> None:
        # The desktop gradient is an oversized ::before; inside the mobile
        # overflow:auto panel its negative insets became scrollable overflow and
        # raised both scrollbars, so mobile must paint it as a background.
        mobile = self.css.split("@media (max-width: 760px)")[1]
        self.assertIn(".mh-copy::before { display: none; }", mobile)
        self.assertIn("radial-gradient", mobile)


class RepositoryScopeTests(unittest.TestCase):
    def test_skill_has_no_current_directory_commands(self) -> None:
        for path in (SKILL_ROOT / "SKILL.md",):
            text = path.read_text(encoding="utf-8")
            for token in ("python scripts/", "pip install -r requirements.txt", "$SN_IMAGE_BASE"):
                self.assertNotIn(token, text, f"{path.name} contains {token}")

    def test_skill_markdown_links_resolve(self) -> None:
        link = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
        for markdown in SKILL_ROOT.rglob("*.md"):
            for target in link.findall(markdown.read_text(encoding="utf-8")):
                raw = target.strip().split(" ", 1)[0].strip("<>")
                if raw.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                resolved = (markdown.parent / raw.split("#", 1)[0]).resolve()
                self.assertTrue(resolved.exists(), f"{markdown.name} -> {target}")


if __name__ == "__main__":
    unittest.main()
