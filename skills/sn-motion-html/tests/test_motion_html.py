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
import urllib.parse
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


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_project_model():
    return load_module(SCRIPTS / "project_model.py", "motion_project_model")


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

        for record in ("project_model.py", "verify_media.py", "contact_sheet.py",
                       "make_posters.py", "export_storyboard.py", "serve_project.py"):
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
        # The Agnes pipeline ships with a video project; the frozen Ark script stays
        # for compatibility but is not the current contract.
        self.assertTrue((project / "scripts/agnes_video.py").is_file())
        manifest = json.loads((project / "prompts/video-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["model"], "agnes-video-2.5-flash")
        self.assertEqual(manifest["resolution"], "720P")
        self.assertTrue(all("anchor_mode" in dive for dive in manifest["dives"]))
        for record in manifest["dives"]:
            for key in ("anchor_prompt", "prompt"):
                self.assertTrue((project / record[key]).is_file(), record[key])

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

    def test_shot_block_is_optional_and_typed(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="sn-motion-validate-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)

        # A chapter with no shot block stays valid: the field is optional.
        story = self.story()
        self.assertFalse(project_model.validate_story(root, story, "images"))
        self.assertEqual(project_model.shot_of(story["chapters"][0]), {})

        story["chapters"][0]["shot"] = {"intent": "  What this shot carries  ", "framing": "wide"}
        self.assertFalse(project_model.validate_story(root, story, "images"))
        self.assertEqual(
            project_model.shot_of(story["chapters"][0]),
            {"intent": "What this shot carries", "framing": "wide"},
        )

        # Unknown keys are ignored so a later version's field cannot break export.
        story["chapters"][0]["shot"]["futureField"] = "ignored"
        self.assertFalse(project_model.validate_story(root, story, "images"))
        self.assertNotIn("futureField", project_model.shot_of(story["chapters"][0]))

        for bad in ("a string", ["intent"], {"intent": ""}, {"intent": 3}, {"framing": "   "}):
            with self.subTest(shot=bad):
                story["chapters"][0]["shot"] = bad
                self.assertTrue(project_model.validate_story(root, story, "images"))


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


class StoryboardExportTests(ProjectFixture):
    def build_project(self, *, with_shot: bool = True) -> Path:
        project = self.tmp / "story project"
        self.init("--media", "images", "--lang", "zh", project=project)
        chapter_one = {
            "id": "01-a",
            "label": "第一幕",
            "eyebrow": "第一章",
            "title": "One <b>bold</b> & \"quoted\"",
            "subtitle": "起点",
            "paragraphs": ["正文第一段。", "正文第二段。"],
            "tags": ["甲", "乙"],
            "still": "assets/images/scenes/01-a.webp",
        }
        if with_shot:
            chapter_one["shot"] = {
                "intent": "让读者看懂起点状态",
                "framing": "中景，主体偏左，右侧留白",
                "motionNote": "将来可做缓慢推移",
            }
        story = {
            "meta": {
                "title": "标题 & <tag>",
                "kicker": "系列",
                "subtitle": "副标题",
                "note": "改编说明",
                "style": "cinematic",
                "ui": "folio",
                "mediaMode": "images",
                "lang": "zh",
            },
            "chapters": [
                chapter_one,
                {
                    "id": "02-b",
                    "label": "第二幕",
                    "title": "Two",
                    "paragraphs": ["第二镜正文。"],
                    "still": "assets/images/scenes/02-b.webp",
                },
            ],
            "sources": [
                {"label": "一份来源", "url": "https://example.com/a"},
                {"label": "不安全来源", "url": "javascript:alert(1)"},
            ],
        }
        (project / "content" / "story.json").write_text(
            json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        make_still(project / "assets/images/scenes/01-a.webp")
        make_still(project / "assets/images/scenes/02-b.webp")
        return project

    def export(self, project: Path) -> subprocess.CompletedProcess:
        return self.run_script(project / "scripts" / "export_storyboard.py", str(project))

    def test_export_lists_the_same_shots_in_the_same_order(self) -> None:
        project = self.build_project()
        result = self.export(project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        markdown = (project / "exports/storyboard.md").read_text(encoding="utf-8")
        html = (project / "exports/storyboard.html").read_text(encoding="utf-8")

        # Story order is the export order: shot 1 before shot 2 in both documents.
        for document in (markdown, html):
            self.assertLess(document.index("01-a"), document.index("02-b"))
            self.assertLess(document.index("正文第一段。"), document.index("第二镜正文。"))
        self.assertEqual(markdown.count("## 01 ·"), 1)
        self.assertEqual(html.count('id="shot-01"'), 1)
        self.assertEqual(html.count('class="sb-shot"'), 2)

    def test_shot_direction_appears_in_both_outputs(self) -> None:
        project = self.build_project()
        self.assertEqual(self.export(project).returncode, 0)
        markdown = (project / "exports/storyboard.md").read_text(encoding="utf-8")
        html = (project / "exports/storyboard.html").read_text(encoding="utf-8")

        for text in ("让读者看懂起点状态", "中景，主体偏左，右侧留白", "将来可做缓慢推移"):
            self.assertIn(text, markdown)
            self.assertIn(text, html)
        self.assertIn("运动意图（尚未生成）", markdown)
        self.assertIn("运动意图（尚未生成）", html)
        # The storyboard must never imply a clip was produced.
        self.assertIn("不会据此生成视频", markdown)
        self.assertNotIn("<video", html)

    def test_missing_shot_block_omits_the_region(self) -> None:
        project = self.build_project(with_shot=False)
        self.assertEqual(self.export(project).returncode, 0)
        markdown = (project / "exports/storyboard.md").read_text(encoding="utf-8")
        html = (project / "exports/storyboard.html").read_text(encoding="utf-8")

        # The advisory line names these labels, so check the rendered rows only.
        for label in ("镜头意图", "构图与景别", "运动意图（尚未生成）"):
            self.assertNotIn(f"- **{label}**", markdown, label)
            self.assertNotIn(f"<dt>{label}</dt>", html, label)
        # The chapter ID and nav label are identity, not commentary, so they stay.
        self.assertIn("01-a", markdown)
        self.assertIn("<dt>章节 ID</dt><dd>01-a</dd>", html)
        self.assertIn("<dt>导航标签</dt><dd>第一幕</dd>", html)

    def test_output_escapes_html_and_keeps_cjk_editable(self) -> None:
        project = self.build_project()
        self.assertEqual(self.export(project).returncode, 0)
        markdown = (project / "exports/storyboard.md").read_text(encoding="utf-8")
        html = (project / "exports/storyboard.html").read_text(encoding="utf-8")

        self.assertIn("标题 &amp; &lt;tag&gt;", html)
        self.assertIn("One &lt;b&gt;bold&lt;/b&gt; &amp; &quot;quoted&quot;", html)
        self.assertNotIn("<b>bold</b>", html)
        self.assertIn("标题 & <tag>", markdown)
        self.assertIn("第一幕", markdown)
        self.assertIn("第一幕", html)
        # A javascript: source must not become a link in either document.
        self.assertNotIn("javascript:", html)
        self.assertIn("不安全来源", html)

    def test_media_references_resolve_from_the_export(self) -> None:
        project = self.build_project()
        self.assertEqual(self.export(project).returncode, 0)
        exports = project / "exports"
        markdown = (exports / "storyboard.md").read_text(encoding="utf-8")
        html = (exports / "storyboard.html").read_text(encoding="utf-8")

        for document, pattern in ((markdown, r"\]\((\.\./[^)]+)\)"), (html, r'src="(\.\./[^"]+)"')):
            targets = re.findall(pattern, document)
            self.assertEqual(len(targets), 2, document[:200])
            for target in targets:
                self.assertTrue(target.startswith("../assets/"), target)
                self.assertTrue((exports / target).resolve().is_file(), target)

        # The caption identifies the shot by number and chapter ID. The file path
        # stays in the Markdown and the img src, not as a long printed line that
        # would break mid-filename.
        self.assertIn("<figcaption>镜号 01 · 01-a</figcaption>", html)
        self.assertNotIn("scenes/01-a.webp</figcaption>", html)

    def test_export_refuses_missing_media_and_writes_nothing(self) -> None:
        project = self.build_project()
        (project / "assets/images/scenes/02-b.webp").unlink()
        result = self.export(project)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("missing media", result.stdout)
        self.assertFalse((project / "exports/storyboard.md").exists())
        self.assertFalse((project / "exports/storyboard.html").exists())

    def test_invalid_story_fails_before_writing(self) -> None:
        project = self.build_project()
        story = json.loads((project / "content" / "story.json").read_text(encoding="utf-8"))
        story["chapters"][0]["shot"] = {"intent": ""}
        (project / "content" / "story.json").write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")

        result = self.export(project)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("shot.intent", result.stdout)
        self.assertFalse((project / "exports").exists())

    def test_export_is_repeatable_and_reports_overwrite(self) -> None:
        project = self.build_project()
        first = self.export(project)
        self.assertEqual(first.returncode, 0)
        self.assertNotIn("Overwrote", first.stdout)

        second = self.export(project)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("Overwrote existing export(s): storyboard.md, storyboard.html", second.stdout)

    def test_storyboard_html_is_self_contained(self) -> None:
        project = self.build_project()
        self.assertEqual(self.export(project).returncode, 0)
        html = (project / "exports/storyboard.html").read_text(encoding="utf-8")

        # A static document: it must read offline without fetching anything.
        self.assertNotIn("<script", html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("<link", html)
        self.assertIn("@media print", html)
        self.assertIn("break-inside: avoid", html)
        # Printing must keep the still beside its copy; stacking them at paper
        # width spends a whole page per shot and defeats reviewing the sequence.
        print_block = html.split("@media print", 1)[1]
        self.assertIn(".sb-grid { grid-template-columns: minmax(210px, 40%) 1fr", print_block)


class PreviewServerTests(ProjectFixture):
    def test_path_rules(self) -> None:
        allowed = [
            "index.html", "styles.css", "src/app.js", "content/story.json",
            "content/sources.json", "assets/images/scenes/a.webp",
            "assets/images/a.png", "favicon.ico",
            *project_model.SERVED_EXPORTS,
        ]
        for relative in allowed:
            self.assertTrue(project_model.web_visible(relative, "images"), relative)

        denied = [
            ".env", ".env.example", ".gitignore", "prompts/style-preamble.txt",
            "scripts/verify_media.py", "docs/production-spec.md", "tmp/frame.png",
            "assets/../../README.md", "content/notes.txt", "src/../.env",
            "assets/video/dives/a.mp4", "prompts/video-manifest.json",
            # Only the exported deliverables are served, never the rest of exports/.
            "exports/storyboard.md", "exports/notes.html", "exports/other/storyboard.html",
            "exports/storyboard.html.bak", "exports/.storyboard.html",
            "exports/story-poster.jpg", "exports/story-poster.png.bak", "exports/poster.png",
            "exports/story-poster-clarity.webp", "exports/story-poster-other.png",
        ]
        for relative in denied:
            self.assertFalse(project_model.web_visible(relative, "images"), relative)
        self.assertTrue(project_model.web_visible("assets/video/dives/a.mp4", "video"))
        self.assertFalse(project_model.web_visible("prompts/video-manifest.json", "video"))
        self.assertTrue(project_model.web_visible("exports/storyboard.html", "video"))
        self.assertTrue(project_model.web_visible("exports/story-poster.png", "video"))

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

        # The exported storyboard is readable over the preview, and the media it
        # references resolves from the export's own directory upward.
        export = self.run_script(project / "scripts" / "export_storyboard.py", str(project))
        self.assertEqual(export.returncode, 0, export.stdout + export.stderr)
        (project / "exports" / "notes.md").write_text("private\n", encoding="utf-8")

        status, headers, body = fetch("/exports/storyboard.html")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        document = body.decode("utf-8")
        # A browser resolves "../assets/…" against the export's own URL; the raw
        # ".." path is refused by the server, which is the intended behaviour.
        for target in re.findall(r'src="(\.\./[^"]+)"', document):
            resolved = urllib.parse.urljoin(f"http://127.0.0.1:{port}/exports/storyboard.html", target)
            status, _, _ = fetch(urllib.parse.urlsplit(resolved).path)
            self.assertEqual(status, 200, f"storyboard media {target} must be served")

        for path in ("/exports/storyboard.md", "/exports/notes.md", "/exports/"):
            status, _, _ = fetch(path)
            self.assertEqual(status, 404, f"{path} must be refused")
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
        styles = (SKILL_ROOT / "assets/template/styles.css").read_text(encoding="utf-8")
        # The stylesheet must follow the runtime's resolved decision. A bare
        # prefers-reduced-motion block with !important overrides the inline
        # transform, which made ?motion=full unable to restore the drift for
        # review on a machine whose OS reports reduce.
        self.assertNotIn("@media (prefers-reduced-motion: reduce)", styles)
        self.assertIn(':root[data-motion="reduce"] .mh-shot__poster { transform: none !important; }', styles)
        self.assertIn(':root[data-motion="reduce"] .mh-hint { display: none; }', styles)
        self.assertIn("document.documentElement.dataset.motion", self.runtime)

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

    def test_chapter_navigation_lands_where_the_copy_is_readable(self) -> None:
        # A chapter's copy fades in over the first part of its own range, so jumping
        # to the raw segment start showed the right image with no words at all.
        # The jump target and the copy window must come from the same value.
        self.assertIn("scene.copySettled = index === 0", self.runtime)
        self.assertIn("const target = sceneSegments[index]?.copySettled ?? 0;", self.runtime)
        self.assertIn("const fadePx = scene.fadePx;", self.runtime)
        self.assertNotIn("sceneSegments[index]?.start || 0", self.runtime)

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
        # A phone must not shrink the copy to fit: the panel scrolls instead, so the
        # body size needs a floor that still reads as body text.
        mobile = self.css.split("@media (max-width: 760px)")[1]
        body = re.search(r"\.mh-copy__body\s*\{([^}]*)\}", mobile)
        self.assertIsNotNone(body, "mobile copy body rule is missing")
        lower = re.search(r"clamp\(\s*([\d.]+)rem", body.group(1))
        self.assertIsNotNone(lower, "mobile copy body must start from a rem floor")
        self.assertGreaterEqual(float(lower.group(1)), 0.9)

    def test_mobile_copy_does_not_scroll_from_its_own_decoration(self) -> None:
        # The desktop gradient is an oversized ::before; inside the mobile
        # overflow:auto panel its negative insets became scrollable overflow and
        # raised both scrollbars, so mobile must paint it as a background.
        mobile = self.css.split("@media (max-width: 760px)")[1]
        self.assertIn(".mh-copy::before { display: none; }", mobile)
        self.assertIn("radial-gradient", mobile)


class AgnesVideoPlannerTests(ProjectFixture):
    """Offline checks for the video pipeline's planner: no provider call is made."""

    VIDEO = SCRIPTS / "agnes_video.py"

    def build_video_project(self, *, mutate=None) -> Path:
        project = self.tmp / "video story"
        self.init("--media", "video", "--lang", "en", project=project)
        manifest_path = project / "prompts" / "video-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if mutate:
            mutate(manifest)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return project

    def plan(self, project: Path, *args: str) -> subprocess.CompletedProcess:
        # A dry run must never need credentials or the Agnes CLI.
        return self.run_script(self.VIDEO, str(project), "--dry-run", *args,
                               env={"PATH": os.environ.get("PATH", "")})

    def test_image_project_has_no_video_manifest_to_plan(self) -> None:
        project = self.tmp / "image story"
        self.init("--media", "images", project=project)
        result = self.plan(project)
        self.assertEqual(result.returncode, 1)
        self.assertIn("video mode needs a manifest", result.stdout)

    def test_shipped_video_template_plans_without_credentials(self) -> None:
        project = self.build_video_project()
        result = self.plan(project, "--write-stills")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("agnes-video-2.5-flash", result.stdout)
        self.assertIn("Clips: 3", result.stdout)
        for name in ("01-opening", "02-destination", "01-opening-to-destination"):
            self.assertIn(name, result.stdout)
        # Dives generate their anchor; the connector borrows the two chapters' anchors
        # at run time, so one invocation can produce dives and their connector.
        self.assertIn("anchor=generate", result.stdout)
        self.assertIn("anchor=reference", result.stdout)
        self.assertIn("no anchor image is recorded for 01-opening, 02-destination", result.stdout)
        self.assertIn("Dry run complete", result.stdout)
        self.assertFalse((project / "assets/video/dives/01-opening.mp4").exists())
        self.assertFalse((project / ".motion-state").exists(), "a dry run must not write run state")

    def test_planner_rejects_provider_and_parameter_mismatches(self) -> None:
        cases = {
            "wrong model": lambda m: m.update(model="doubao-seedance-2-5-260628"),
            "duration out of range": lambda m: m.update(duration=3),
            "duration not whole": lambda m: m.update(duration=4.5),
            "resolution not 720P": lambda m: m.update(resolution="1080p"),
            "bad anchor mode": lambda m: m["dives"][0].update(anchor_mode="magic"),
            "url anchor without https": lambda m: m["dives"][0].update(anchor_mode="url", first_frame="assets/x.png"),
            "anchored connector": lambda m: m["connectors"][0].update(anchor_mode="generate",
                                                                     anchor_prompt="prompts/video/anchors/01-opening.txt"),
            "text anchor with keyframes": lambda m: m["dives"][0].update(anchor_mode="text"),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                project = self.build_video_project(mutate=mutate)
                result = self.plan(project)
                self.assertEqual(result.returncode, 1, f"{name} should be refused: {result.stdout}")
                self.assertTrue(result.stdout.startswith("FAIL"), result.stdout)

    def test_missing_prompt_file_is_refused_before_any_call(self) -> None:
        project = self.build_video_project()
        (project / "prompts/video/dives/01-opening.txt").unlink()
        result = self.plan(project)
        self.assertEqual(result.returncode, 1)
        self.assertIn("prompt is missing", result.stdout)

    def test_unknown_only_id_is_refused(self) -> None:
        project = self.build_video_project()
        result = self.plan(project, "--only", "99-nope")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown dive ids", result.stdout)

    def test_existing_clip_is_skipped_without_force(self) -> None:
        project = self.build_video_project()
        clip = project / "assets/video/dives/01-opening.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"placeholder")
        result = self.plan(project)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("already exists (pass --force to replace)", result.stdout)

    def test_only_limits_the_plan(self) -> None:
        project = self.build_video_project()
        result = self.plan(project, "--only", "02-destination")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Clips: 1", result.stdout)
        self.assertNotIn("== dive 01-opening", result.stdout)

    def test_write_stills_plans_stills_for_dives_only(self) -> None:
        # A connector has no page still of its own; asking for stills must not
        # claim one for it (a live run crashed on exactly this).
        project = self.build_video_project()
        result = self.plan(project, "--write-stills")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        dive_block = result.stdout.split("== dive 01-opening", 1)[1].split("== dive 02-destination", 1)[0]
        self.assertIn("would write still assets/images/scenes/01-opening.webp", dive_block)
        connector_block = result.stdout.split("== connector 01-opening-to-destination", 1)[1]
        self.assertNotIn("would write still", connector_block)

    def test_reference_images_are_validated(self) -> None:
        def with_references(values):
            def mutate(manifest):
                manifest["connectors"][0].update(anchor_mode="reference", reference_images=values)
            return mutate

        good = "https://cos-platform-outputs.agnes-ai.cn/images/t2i/task_x/output.png"
        project = self.build_video_project(mutate=with_references([good, good]))
        result = self.plan(project)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"would use reference image {good}", result.stdout)

        for name, values in {
            "local path": ["assets/images/scenes/01-opening.png"],
            "too many": [f"https://example.com/{index}.png" for index in range(6)],
        }.items():
            with self.subTest(case=name):
                project = self.build_video_project(mutate=with_references(values))
                result = self.plan(project)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertTrue(result.stdout.startswith("FAIL"), result.stdout)

    def test_url_connector_can_anchor_its_destination_frame_only(self) -> None:
        # Hosting only the destination frame is the zero-render option for a seam:
        # the connector lands exactly on the next chapter's opening frame.
        def mutate(manifest):
            manifest["connectors"][0].update(
                anchor_mode="url", last_frame="https://example.com/next-chapter-first-frame.png")
        project = self.build_video_project(mutate=mutate)
        result = self.plan(project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("would use last_frame https://example.com/next-chapter-first-frame.png", result.stdout)
        self.assertIn("--mode keyframe", result.stdout)

    def test_reference_resolution_reads_recorded_anchors(self) -> None:
        project = self.build_video_project()
        module = load_module(SCRIPTS / "agnes_video.py", "agnes_video_module")
        record = {
            "id": "01-opening-to-destination",
            "references": [],
            "references_from": ["01-opening", "02-destination"],
        }
        with self.assertRaises(module.PipelineError) as missing:
            module.resolve_references(project, record)
        self.assertIn("no anchor image is recorded", str(missing.exception))

        state = project / ".motion-state" / "video-anchors.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"clips": {
            "01-opening": {"anchor_url": "https://example.com/a.png"},
            "02-destination": {"anchor_url": "https://example.com/b.png"},
        }}), encoding="utf-8")
        self.assertEqual(module.resolve_references(project, record),
                         ["https://example.com/a.png", "https://example.com/b.png"])

        state.write_text('{"clips": {"01-opening": {"anchor_url": "http://insecure/a.png"}}}', encoding="utf-8")
        with self.assertRaises(module.PipelineError):
            module.resolve_references(project, record)


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
