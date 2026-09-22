"""Offline gate tests for scripts/motion_stage.py.

A fake runner stands in for the SenseNova client so every assertion is about
the gate, not the provider: a blocked call must report zero provider calls and
must leave no file behind. These tests prove the local program refuses
out-of-scope work; they do not prove that any host model stops and ends its
turn, which is a separate behavioural check.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
INIT = SCRIPTS / "init_project.py"
STAGE = SCRIPTS / "motion_stage.py"

CHAPTERS = [
    "01-opening",
    "02-forest",
    "03-cottage",
    "04-grandma",
    "05-wolf",
    "06-bed",
    "07-hunter",
    "08-rescue",
    "09-home",
]
SAMPLES = ["01-opening", "05-wolf"]

FAKE_RUNNER = '''#!/usr/bin/env python3
"""Stand in for sn_agent_runner.py, including its output naming.

The real runner names the file it writes from the format it produced
(save_path.with_suffix(MIME_SUFFIX[mime])), so this fake must do the same:
a gate that only ever worked with a matching suffix would otherwise pass here
and fail against the real client.
"""
import json, os, sys, time
argv = sys.argv[1:]
mode = os.environ.get("FAKE_RUNNER_MODE", "ok")
delay = float(os.environ.get("FAKE_RUNNER_DELAY", "0"))
delay_match = os.environ.get("FAKE_RUNNER_DELAY_MATCH", "")
save = argv[argv.index("--save-path") + 1] if "--save-path" in argv else None
fmt = argv[argv.index("--image-format") + 1] if "--image-format" in argv else "png"
if delay and (not delay_match or (save and delay_match in save)):
    time.sleep(delay)
fail_match = os.environ.get("FAKE_RUNNER_FAIL_MATCH", "")
if fail_match and save and fail_match in save:
    sys.stderr.write("provider rejected the request\\n")
    raise SystemExit(1)
if mode == "fail" and save:
    sys.stderr.write("provider rejected the request\\n")
    raise SystemExit(1)
if mode == "empty":
    print(json.dumps({"ok": True}))
    raise SystemExit(0)
if save:
    from PIL import Image
    final = os.path.splitext(save)[0] + {"png": ".png", "webp": ".webp", "jpeg": ".jpg"}[fmt]
    os.makedirs(os.path.dirname(final), exist_ok=True)
    Image.new("RGB", (128, 72), os.environ.get("FAKE_RUNNER_COLOUR", "#224466")).save(final)
    print(json.dumps({"ok": True, "model": "fake", "path": final}))
'''


def story_payload(title: str = "Little Red Riding Hood", suffix: str = ".png") -> dict:
    return {
        "meta": {"title": title, "style": "cinematic", "ui": "folio", "mediaMode": "images", "lang": "zh"},
        "chapters": [
            {
                "id": chapter_id,
                "label": chapter_id.split("-", 1)[1].title(),
                "title": f"Scene {index}",
                "paragraphs": [f"Paragraph one for {chapter_id}."],
                "tags": ["test"],
                "still": f"assets/images/scenes/{chapter_id}{suffix}",
            }
            for index, chapter_id in enumerate(CHAPTERS, start=1)
        ],
    }


class StageGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="motion-stage-"))
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.project = self.temp / "story"
        self.runner = self.temp / "fake_runner.py"
        self.runner.write_text(FAKE_RUNNER, encoding="utf-8")
        self.prompts = self.temp / "prompts"
        self.prompts.mkdir()
        for chapter_id in CHAPTERS:
            (self.prompts / f"{chapter_id}.txt").write_text(f"prompt for {chapter_id}\n", encoding="utf-8")
        subprocess.run(
            [sys.executable, str(INIT), str(self.project), "--title", "Gate Test", "--style", "cinematic", "--lang", "zh"],
            check=True,
            capture_output=True,
        )
        self.write_story(story_payload())
        self.assertTrue((self.project / "scripts" / "motion_stage.py").is_file(), "the initializer must ship the executor")

    # --- helpers ----------------------------------------------------------

    def write_story(self, story: dict) -> None:
        path = self.project / "content" / "story.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(story, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def stage(self, *args: str, mode: str = "ok", delay: str = "0", fail_match: str = "", check: bool | None = None) -> tuple[int, dict]:
        env = dict(os.environ)
        env["FAKE_RUNNER_MODE"] = mode
        env["FAKE_RUNNER_DELAY"] = delay
        env["FAKE_RUNNER_FAIL_MATCH"] = fail_match
        proc = subprocess.run(
            [sys.executable, str(STAGE), str(self.project), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"motion_stage did not print JSON: {proc.stdout!r} {proc.stderr!r}")
        if check is not None:
            self.assertEqual(check, proc.returncode, f"{args} -> {payload}")
        return proc.returncode, payload

    def state(self) -> dict:
        return json.loads((self.project / ".motion-state" / "review.json").read_text(encoding="utf-8"))

    def still(self, chapter_id: str, suffix: str = ".png") -> Path:
        return self.project / "assets" / "images" / "scenes" / f"{chapter_id}{suffix}"

    def to_sampling(self, samples: list[str] | None = None) -> None:
        chosen = samples or SAMPLES
        self.stage("prepare-review", "--kind", "story", "--sample-ids", ",".join(chosen))
        self.stage("record-display", "--kind", "story")
        self.stage("record-decision", "--scope", "story", "--message-ref", "user-msg-1")

    def to_producing(self) -> None:
        self.to_sampling()
        self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.stage("prepare-review", "--kind", "visual")
        self.stage("record-display", "--kind", "visual")
        self.stage("record-decision", "--scope", "visual", "--message-ref", "user-msg-2")
        self.assertEqual(self.state()["phase"], "producing")

    # --- G01 / G06: nothing may be generated before confirmation A --------

    def test_samples_are_blocked_before_confirmation_A(self) -> None:
        self.stage("prepare-review", "--kind", "story", "--sample-ids", ",".join(SAMPLES))
        self.stage("record-display", "--kind", "story")
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("awaiting_story_review", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])
        self.assertFalse(self.still(SAMPLES[0]).exists())

    def test_smoke_generation_is_blocked_before_confirmation_A(self) -> None:
        # A "just one 1K image to check the link" request has no phase that allows it:
        # before A the only legal answer is zero provider calls.
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--target", f"{SAMPLES[0]}={self.prompts / (SAMPLES[0] + '.txt')}")
        self.assertEqual(2, code)
        self.assertEqual(0, payload["provider_calls"])
        self.assertTrue(payload["reason"].startswith("phase_"))
        self.assertFalse(self.still(SAMPLES[0]).exists())

    def test_status_never_calls_the_provider(self) -> None:
        code, payload = self.stage("status")
        self.assertEqual(0, code)
        self.assertEqual("drafting", payload["phase"])
        self.assertEqual(0, payload["provider_calls"])

    # --- G04: only the sample list shown with A may be generated ----------

    def test_only_the_recorded_sample_ids_are_generated(self) -> None:
        self.to_sampling()
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(2, payload["provider_calls"])
        for chapter_id in SAMPLES:
            self.assertTrue(self.still(chapter_id).is_file(), chapter_id)
        for chapter_id in CHAPTERS:
            if chapter_id not in SAMPLES:
                self.assertFalse(self.still(chapter_id).exists(), f"{chapter_id} was generated before B")

    def test_an_unlisted_character_board_is_refused(self) -> None:
        self.to_sampling()
        extra = "99-character-board"
        code, payload = self.stage(
            "run-samples",
            "--runner",
            str(self.runner),
            "--target",
            f"{SAMPLES[0]}={self.prompts / (SAMPLES[0] + '.txt')}",
            "--target",
            f"{extra}={self.prompts / (SAMPLES[0] + '.txt')}",
        )
        self.assertEqual(2, code)
        self.assertEqual(0, payload["provider_calls"])
        self.assertFalse(self.still(SAMPLES[0]).exists(), "a refused batch may not generate its valid prefix")

    # --- G07: a whole batch is refused, not partially executed ------------

    def test_submitting_all_chapters_at_the_sample_stage_is_refused_whole(self) -> None:
        self.to_sampling()
        args = ["run-samples", "--runner", str(self.runner)]
        for chapter_id in CHAPTERS:
            args += ["--target", f"{chapter_id}={self.prompts / (chapter_id + '.txt')}"]
        code, payload = self.stage(*args)
        self.assertEqual(2, code)
        self.assertEqual(0, payload["provider_calls"])
        self.assertEqual([], [name.stem for name in (self.project / "assets" / "images" / "scenes").glob("*.png")])

    def test_renaming_every_target_sample_does_not_widen_the_scope(self) -> None:
        self.to_sampling(samples=["01-opening"])
        args = ["run-samples", "--runner", str(self.runner)]
        for chapter_id in CHAPTERS[1:]:
            args += ["--target", f"{chapter_id}={self.prompts / (chapter_id + '.txt')}"]
        code, payload = self.stage(*args)
        self.assertEqual(2, code)
        self.assertEqual(0, payload["provider_calls"])

    # --- G09: a story change after A does not inherit the old acceptance --

    def test_editing_the_story_after_A_invalidates_the_shown_package(self) -> None:
        self.to_sampling()
        story = story_payload()
        story["chapters"][1]["paragraphs"] = ["a different event in the forest"]
        self.write_story(story)
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("story_changed_since_package", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])

    def test_a_scoped_revision_decision_covers_the_changed_chapter(self) -> None:
        self.to_sampling()
        story = story_payload()
        story["chapters"][1]["paragraphs"] = ["a different event in the forest"]
        self.write_story(story)
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "02-forest", "--copy-only")
        self.assertEqual(0, code)
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(2, payload["provider_calls"])

    # --- G10: replacing a sample file retires the old acceptance ----------

    def test_a_replaced_sample_file_invalidates_confirmation_B(self) -> None:
        self.to_producing()
        self.write_png(self.still(SAMPLES[1]), "#990000")
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("visual_review_stale", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])

    # --- G15: resuming must not resubmit finished work --------------------

    def test_resuming_skips_files_that_already_exist(self) -> None:
        self.to_sampling()
        self.write_png(self.still(SAMPLES[0]), "#009900")
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(1, payload["provider_calls"], "the existing sample is reused, not regenerated")
        self.assertEqual("skipped_existing", payload["results"][0]["status"])

    # --- G19: two processes cannot spend one authorization ----------------

    # --- G20: an unknown provider result is reconciled, never resent ------

    def test_a_result_without_a_file_is_recorded_as_unknown_and_not_resent(self) -> None:
        self.to_sampling()
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts), mode="empty")
        self.assertEqual(1, code, "an unverified result is reported, not treated as success")
        self.assertEqual({"unknown"}, {item["status"] for item in payload["results"]})
        unknown_ids = [item["id"] for item in payload["results"]]
        code, second = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("previous_result_unknown", second["reason"])
        self.assertEqual(0, second["provider_calls"])
        code, third = self.stage(
            "run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts), "--retry-unknown", ",".join(unknown_ids)
        )
        self.assertEqual(0, code)
        self.assertEqual(2, third["provider_calls"], "resending requires an explicit reconciliation")

    def test_a_failed_provider_call_keeps_the_previous_asset(self) -> None:
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        before = self.still("02-forest").read_bytes()
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "02-forest")
        self.assertEqual(0, code)
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"02-forest={self.prompts / '02-forest.txt'}", mode="fail"
        )
        self.assertEqual(1, code, "a spent-but-failed call is reported, not silently accepted")
        self.assertEqual("attention", payload["status"])
        self.assertEqual("failed", payload["results"][0]["status"])
        self.assertEqual(before, self.still("02-forest").read_bytes(), "a rejected candidate never overwrites an adopted asset")

    # --- G21: a model-written approval is never treated as verified -------

    def test_decisions_default_to_agent_recorded_trust(self) -> None:
        self.stage("prepare-review", "--kind", "story", "--sample-ids", SAMPLES[0])
        self.stage("record-display", "--kind", "story")
        self.stage("record-decision", "--scope", "story")
        approval = self.state()["approvals"][-1]
        self.assertEqual("agent-recorded", approval["trust"])
        self.assertEqual("", approval["event_ref"])

    def test_a_host_verified_decision_requires_an_event_reference(self) -> None:
        self.stage("prepare-review", "--kind", "story", "--sample-ids", SAMPLES[0])
        self.stage("record-display", "--kind", "story")
        code, payload = self.stage("record-decision", "--scope", "story", "--trust", "host-verified")
        self.assertEqual(1, code)
        self.assertIn("event-ref", payload["reason"])
        code, _ = self.stage("record-decision", "--scope", "story", "--trust", "host-verified", "--event-ref", "evt-42")
        self.assertEqual(0, code)
        self.assertEqual("host-verified", self.state()["approvals"][-1]["trust"])

    def test_there_is_no_force_or_yes_flag(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(STAGE), str(self.project), "run-samples", "--force-approved"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("--force-approved", proc.stderr)

    # --- G22 / G24: state cannot travel between projects or versions ------

    def test_a_copied_state_file_cannot_authorize_another_project(self) -> None:
        self.to_sampling()
        other = self.temp / "other"
        shutil.copytree(self.project, other)
        (other / "content" / "story.json").write_text(json.dumps(story_payload("Copied state"), ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(STAGE), str(other), "run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(2, proc.returncode)
        payload = json.loads(proc.stdout)
        self.assertIn(payload["reason"], {"state_project_mismatch", "story_changed_since_package"})
        self.assertEqual(0, payload["provider_calls"])

    def test_a_state_written_by_another_protocol_is_refused(self) -> None:
        self.to_sampling()
        path = self.project / ".motion-state" / "review.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["workflow_protocol"] = 1
        path.write_text(json.dumps(state), encoding="utf-8")
        code, payload = self.stage("status")
        self.assertEqual(2, code)
        self.assertEqual("protocol_mismatch", payload["reason"])

    # --- the full path, counted ------------------------------------------

    def test_the_full_path_spends_exactly_nine_calls(self) -> None:
        self.to_producing()
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(7, payload["provider_calls"], "the two accepted samples are reused")
        self.assertEqual("delivered", payload["phase"])
        _, status = self.stage("status")
        self.assertEqual(9, status["total_provider_calls"])
        self.assertEqual([], status["needs_generation"])
        self.assertEqual([], status["needs_page_copy"])

    def test_an_explicitly_authorized_single_image_revision_touches_one_asset(self) -> None:
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        keep = self.still("03-cottage").read_bytes()
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "06-bed")
        self.assertEqual(0, code)
        code, payload = self.stage(
            "run-remaining",
            "--runner",
            str(self.runner),
            "--target",
            f"06-bed={self.prompts / '06-bed.txt'}",
            "--target",
            f"03-cottage={self.prompts / '03-cottage.txt'}",
        )
        self.assertEqual(2, code)
        self.assertEqual(0, payload["provider_calls"])
        self.assertEqual(keep, self.still("03-cottage").read_bytes())

    def test_a_copy_only_revision_makes_no_image_call(self) -> None:
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        story = story_payload()
        story["chapters"][0]["paragraphs"] = ["shorter copy"]
        self.write_story(story)
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "01-opening", "--copy-only")
        self.assertEqual(0, code)
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(0, payload["provider_calls"])
        self.assertEqual("delivered", self.state()["phase"])

    def test_the_review_state_is_never_web_visible(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            from project_model import web_visible
        finally:
            sys.path.pop(0)
        self.assertFalse(web_visible(".motion-state/review.json", "images"))
        self.assertFalse(web_visible(".motion-state/review.lock", "images"))

    def test_a_delegation_covers_the_waits_but_not_the_artifacts(self) -> None:
        self.stage("prepare-review", "--kind", "story", "--sample-ids", ",".join(SAMPLES))
        self.stage("record-display", "--kind", "story")
        code, payload = self.stage("record-decision", "--scope", "delegation", "--stages", "story,visual")
        self.assertEqual(0, code)
        self.assertEqual("sampling", payload["phase"])
        self.assertEqual("direct-completion", self.state()["interaction_mode"])
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(2, payload["provider_calls"])
        self.stage("prepare-review", "--kind", "visual")
        self.stage("record-display", "--kind", "visual")
        self.assertEqual("awaiting_visual_review", self.state()["phase"])
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(7, payload["provider_calls"])

    def test_a_generation_limit_blocks_the_call_that_would_exceed_it(self) -> None:
        self.stage("prepare-review", "--kind", "story", "--sample-ids", ",".join(SAMPLES), "--generation-limit", "1")
        self.stage("record-display", "--kind", "story")
        self.stage("record-decision", "--scope", "story")
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("image_call_limit_reached", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])

    # --- review round 2: the paths a naive gate gets wrong ----------------

    def test_generation_targets_the_png_master_when_the_page_asset_is_webp(self) -> None:
        # The runner names its output from the format it produced, so aiming a
        # png request at a declared .webp used to report success as unknown and
        # strand the image in the temporary directory.
        self.write_story(story_payload(suffix=".webp"))
        self.to_sampling()
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(2, payload["provider_calls"])
        for chapter_id in SAMPLES:
            self.assertTrue(self.still(chapter_id).is_file(), f"{chapter_id} master is missing")
            self.assertFalse(self.still(chapter_id, ".webp").exists(), "the page copy is make_posters.py work")
        self.assertTrue(all(item["page_copy_needed"] for item in payload["results"]))
        self.assertEqual([], list((self.project / "tmp" / "staged").glob("*")), "nothing is stranded in staging")
        _, status = self.stage("status")
        self.assertEqual(sorted(SAMPLES), sorted(status["needs_page_copy"]))
        self.assertEqual(7, len(status["needs_generation"]))

    def test_a_call_killed_mid_flight_is_not_resent(self) -> None:
        self.to_sampling()
        env = dict(os.environ)
        env["FAKE_RUNNER_MODE"] = "ok"
        env["FAKE_RUNNER_DELAY"] = "5"
        proc = subprocess.Popen(
            [
                sys.executable, str(STAGE), str(self.project), "run-samples",
                "--runner", str(self.runner), "--prompts-dir", str(self.prompts), "--call-timeout", "60",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        time.sleep(1.5)
        proc.kill()
        proc.communicate()
        committed = [op for op in self.state()["operations"] if op["status"] == "committed"]
        self.assertTrue(committed, "the attempt must be on disk before the request is sent")
        self.assertEqual(1, self.state()["total_provider_calls"])
        # The killed process's lock died with it: the next run acquires the project
        # at once, and the in-doubt call — not a stale lock — is what stops it.
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("previous_result_unknown", payload["reason"])
        self.assertEqual(0, payload["provider_calls"], "an interrupted call is reconciled, never silently resent")

    def test_a_live_holder_keeps_the_lock(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            import motion_stage
        finally:
            sys.path.pop(0)
        self.to_sampling()
        with motion_stage.project_lock(self.project):
            code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("project_locked", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])
        self.assertFalse(self.still(SAMPLES[0]).exists(), "age alone must never let a second process in")

    def test_two_processes_cannot_enter_at_once(self) -> None:
        # The reviewer's interleaving: one process is inside a long batch while a
        # second one starts. The OS lock lets exactly one of them in, so the second
        # reports project_locked with zero provider calls instead of double-spending.
        self.to_sampling()
        env = dict(os.environ)
        env["FAKE_RUNNER_MODE"] = "ok"
        env["FAKE_RUNNER_DELAY"] = "4"
        holder = subprocess.Popen(
            [
                sys.executable, str(STAGE), str(self.project), "run-samples",
                "--runner", str(self.runner), "--prompts-dir", str(self.prompts), "--call-timeout", "60",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        try:
            time.sleep(1.5)
            code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        finally:
            held_stdout, _ = holder.communicate(timeout=120)
        self.assertEqual(2, code)
        self.assertEqual("project_locked", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])
        json.loads(held_stdout)
        _, status = self.stage("status")
        self.assertEqual(2, status["total_provider_calls"], "only the holder may spend the authorization")

    def test_a_lock_file_left_by_a_dead_process_does_not_block(self) -> None:
        # A crash leaves the descriptor behind; the OS lock died with the process,
        # so the next run acquires normally instead of hunting a stale file.
        self.to_sampling()
        lock = self.project / ".motion-state" / "review.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": 4_000_000, "at": "2020-01-01T00:00:00+00:00"}), encoding="utf-8")
        os.utime(lock, (time.time() - 7200, time.time() - 7200))
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code, payload.get("detail"))
        self.assertEqual(2, payload["provider_calls"])

    def test_a_revision_does_not_bless_an_unauthorized_chapter(self) -> None:
        self.to_sampling()
        story = story_payload()
        story["chapters"][1]["paragraphs"] = ["authorized change to chapter two"]
        story["chapters"][8]["paragraphs"] = ["an unauthorized new ending"]
        self.write_story(story)
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "02-forest", "--copy-only")
        self.assertEqual(0, code)
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("story_changed_since_package", payload["reason"])
        self.assertIn("09-home", payload["detail"])
        self.assertEqual(0, payload["provider_calls"])

    def test_reordering_chapters_retires_confirmation_A(self) -> None:
        self.to_sampling()
        story = story_payload()
        story["chapters"] = list(reversed(story["chapters"]))
        self.write_story(story)
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertIn("<structure>", payload["detail"])
        self.assertEqual(0, payload["provider_calls"])

    def test_a_metadata_change_retires_confirmation_A(self) -> None:
        self.to_sampling()
        story = story_payload()
        story["meta"]["subtitle"] = "a different direction entirely"
        self.write_story(story)
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertIn("<meta>", payload["detail"])
        self.assertEqual(0, payload["provider_calls"])

    def test_an_old_project_can_take_one_authorized_image_revision(self) -> None:
        story = story_payload()
        self.write_story(story)
        for chapter_id in CHAPTERS:
            self.write_png(self.still(chapter_id), "#0f0f0f")
        keep = self.still("01-opening").read_bytes()
        code, payload = self.stage("record-decision", "--scope", "revision", "--chapters", "03-cottage")
        self.assertEqual(0, code, payload.get("detail"))
        self.assertEqual("producing", payload["phase"])
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"03-cottage={self.prompts / '03-cottage.txt'}"
        )
        self.assertEqual(0, code, payload.get("detail"))
        self.assertEqual(1, payload["provider_calls"])
        self.assertEqual(keep, self.still("01-opening").read_bytes())
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code, "a legacy revision never implies the right to regenerate everything")
        self.assertEqual("visual_not_accepted", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])

    def test_a_sample_revision_before_B_returns_to_confirmation_B(self) -> None:
        self.to_sampling()
        self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.stage("prepare-review", "--kind", "visual")
        self.stage("record-display", "--kind", "visual")
        self.assertEqual("awaiting_visual_review", self.state()["phase"])
        code, payload = self.stage("record-decision", "--scope", "revision", "--chapters", "05-wolf")
        self.assertEqual(0, code)
        self.assertEqual("sampling", payload["return_to"])
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"05-wolf={self.prompts / '05-wolf.txt'}"
        )
        self.assertEqual(0, code, payload.get("detail"))
        self.assertEqual("sampling", payload["phase"], "the revised sample must be reviewed again, not produced past")
        _, status = self.stage("status")
        self.assertIsNone(status["visual_package"], "the old sample set is retired")
        self.assertTrue(status["story_accepted"], "confirmation A still stands")
        self.stage("prepare-review", "--kind", "visual")
        self.stage("record-display", "--kind", "visual")
        code, _ = self.stage("record-decision", "--scope", "visual", "--message-ref", "user-msg-3")
        self.assertEqual(0, code)
        self.assertEqual("producing", self.state()["phase"])

    def test_creating_page_copies_does_not_retire_confirmation_B(self) -> None:
        # make_posters.py derives the declared WebP from the accepted master. That
        # is local compression, not a replaced image, so it must not invalidate B
        # and push the project back into a re-confirmation loop.
        self.write_story(story_payload(suffix=".webp"))
        self.to_producing()
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(7, payload["provider_calls"])
        self.assertEqual("producing", payload["phase"], "the page assets are still missing")
        for chapter_id in CHAPTERS:
            self.write_png(self.still(chapter_id, ".webp"), "#224466")
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code, payload.get("detail"))
        self.assertEqual(0, payload["provider_calls"])
        self.assertEqual("delivered", payload["phase"])

    def test_a_supplied_webp_set_is_never_asked_for_a_png_master(self) -> None:
        # Compatibility rule: usable supplied images stay as they are. Neither the
        # sample round nor the completion round may invent a master or a second call.
        self.write_story(story_payload(suffix=".webp"))
        for chapter_id in CHAPTERS:
            self.write_png(self.still(chapter_id, ".webp"), "#101010")
        self.to_sampling()
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(0, payload["provider_calls"], "the supplied samples are reused as they are")
        self.assertEqual({"skipped_existing"}, {item["status"] for item in payload["results"]})
        self.stage("prepare-review", "--kind", "visual")
        self.stage("record-display", "--kind", "visual")
        self.stage("record-decision", "--scope", "visual")
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        self.assertEqual(0, payload["provider_calls"])
        self.assertEqual("delivered", payload["phase"])
        self.assertEqual([], list((self.project / "assets" / "images" / "scenes").glob("*.png")))

    # --- review round 3: freshness, lifetime, and revocation --------------

    def test_a_replacement_master_marks_the_old_page_copy_stale(self) -> None:
        # The page must not keep loading the superseded picture just because a
        # .webp file exists: an authorized replacement leaves the project short
        # of a delivered page until make_posters.py runs.
        self.write_story(story_payload(suffix=".webp"))
        for chapter_id in CHAPTERS:
            self.write_png(self.still(chapter_id, ".png"), "#101010")
            self.write_png(self.still(chapter_id, ".webp"), "#101010")
        # 03-cottage is the one chapter whose page asset predates its master.
        past = time.time() - 600
        os.utime(self.still("03-cottage", ".webp"), (past, past))
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "03-cottage")
        self.assertEqual(0, code)
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"03-cottage={self.prompts / '03-cottage.txt'}"
        )
        self.assertEqual(0, code)
        self.assertEqual(1, payload["provider_calls"])
        self.assertEqual("producing", payload["phase"], "a stale page asset is not a delivered project")
        _, status = self.stage("status")
        self.assertEqual(["03-cottage"], status["needs_page_copy"])
        self.write_png(self.still("03-cottage", ".webp"), "#202020")
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual("delivered", payload["phase"])

    def test_one_revision_covers_every_chapter_it_authorized(self) -> None:
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "02-forest,03-cottage")
        self.assertEqual(0, code)
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"02-forest={self.prompts / '02-forest.txt'}"
        )
        self.assertEqual(0, code)
        self.assertEqual("producing", payload["phase"], "the revision is not finished after one chapter")
        self.assertIn("03-cottage", " ".join(payload["hints"]))
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"03-cottage={self.prompts / '03-cottage.txt'}"
        )
        self.assertEqual(0, code, payload.get("detail"))
        self.assertEqual(1, payload["provider_calls"], "the second chapter keeps its authorization")
        self.assertEqual("delivered", payload["phase"])

    def test_a_failed_revision_target_stays_authorized_and_open(self) -> None:
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        keep = self.still("02-forest").read_bytes()
        self.stage("record-decision", "--scope", "revision", "--chapters", "02-forest")
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"02-forest={self.prompts / '02-forest.txt'}", mode="fail"
        )
        self.assertEqual("producing", payload["phase"], "a failed call must not read as a finished revision")
        self.assertEqual(keep, self.still("02-forest").read_bytes())
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"02-forest={self.prompts / '02-forest.txt'}"
        )
        self.assertEqual(0, code)
        self.assertEqual(1, payload["provider_calls"])

    def test_the_lock_file_is_never_deleted_and_stays_acquirable(self) -> None:
        # Ownership is the OS lock; the file is only a descriptor, so release never
        # unlinks a path another process may already own.
        sys.path.insert(0, str(SCRIPTS))
        try:
            import motion_stage
        finally:
            sys.path.pop(0)
        lock = self.project / ".motion-state" / "review.lock"
        with motion_stage.project_lock(self.project):
            self.assertTrue(lock.is_file())
        with motion_stage.project_lock(self.project):
            self.assertTrue(lock.is_file(), "the descriptor survives release rather than being unlinked")

    def test_an_authorized_change_does_not_exempt_later_changes_to_the_same_chapter(self) -> None:
        self.to_sampling()
        story = story_payload()
        story["chapters"][1]["paragraphs"] = ["the change the user approved"]
        self.write_story(story)
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "02-forest", "--copy-only")
        self.assertEqual(0, code)
        code, _ = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(0, code)
        story["chapters"][1]["paragraphs"] = ["a completely new plot beat, never shown to anyone"]
        self.write_story(story)
        self.still(SAMPLES[0]).unlink()
        code, payload = self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("story_changed_since_package", payload["reason"])
        self.assertIn("02-forest", payload["detail"])
        self.assertEqual(0, payload["provider_calls"])

    def test_a_withdrawn_B_stops_production(self) -> None:
        self.to_producing()
        code, payload = self.stage("record-decision", "--scope", "visual", "--decision", "changes-requested")
        self.assertEqual(0, code, payload.get("detail"))
        self.assertEqual("awaiting_visual_review", payload["phase"])
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("phase_awaiting_visual_review", payload["reason"])
        self.assertEqual(0, payload["provider_calls"], "the old approval must not survive the withdrawal")

    def test_a_withdrawn_revision_stops_generating(self) -> None:
        # "changes-requested" on a revision is a withdrawal: it must retire the
        # authorization instead of recording a fresh one that keeps spending.
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        keep = self.still("06-bed").read_bytes()
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "06-bed")
        self.assertEqual(0, code)
        code, payload = self.stage(
            "record-decision", "--scope", "revision", "--decision", "changes-requested", "--chapters", "06-bed"
        )
        self.assertEqual(0, code, payload.get("detail"))
        self.assertIsNone(self.state().get("revision"), "the withdrawal clears the standing authorization")
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"06-bed={self.prompts / '06-bed.txt'}"
        )
        self.assertEqual(2, code)
        self.assertEqual(0, payload["provider_calls"])
        self.assertEqual(keep, self.still("06-bed").read_bytes())

    def test_a_revision_while_waiting_for_B_binds_to_the_content_it_approved(self) -> None:
        # With B still pending the revision decision is the only authorization, so
        # an edit made after that decision must not ride on the earlier approval.
        self.to_sampling()
        self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.stage("prepare-review", "--kind", "visual")
        self.stage("record-display", "--kind", "visual")
        story = story_payload()
        story["chapters"][4]["paragraphs"] = ["the approved change to the wolf scene"]
        self.write_story(story)
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "05-wolf")
        self.assertEqual(0, code)
        story["chapters"][4]["paragraphs"] = ["a second, unapproved rewrite"]
        self.write_story(story)
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"05-wolf={self.prompts / '05-wolf.txt'}"
        )
        self.assertEqual(2, code)
        self.assertEqual("story_changed_since_package", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "05-wolf")
        self.assertEqual(0, code)
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"05-wolf={self.prompts / '05-wolf.txt'}"
        )
        self.assertEqual(0, code, payload.get("detail"))
        self.assertEqual(1, payload["provider_calls"], "a fresh decision covers the new content")

    def test_a_revision_while_waiting_for_B_rejects_a_new_unapproved_style(self) -> None:
        # The revision decision is the only authorization while B is pending, so the
        # global style basis it was taken on is part of what it approves.
        self.to_sampling()
        self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.stage("prepare-review", "--kind", "visual")
        self.stage("record-display", "--kind", "visual")
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "05-wolf")
        self.assertEqual(0, code)
        preamble = self.project / "prompts" / "style-preamble.txt"
        self.assertTrue(preamble.is_file(), "the initializer must ship the style basis")
        preamble.write_text("a completely different art direction\n", encoding="utf-8")
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"05-wolf={self.prompts / '05-wolf.txt'}"
        )
        self.assertEqual(2, code)
        self.assertEqual("story_changed_since_package", payload["reason"])
        self.assertIn("<style>", payload["detail"])
        self.assertEqual(0, payload["provider_calls"])
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "05-wolf")
        self.assertEqual(0, code)
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"05-wolf={self.prompts / '05-wolf.txt'}"
        )
        self.assertEqual(0, code, f"{payload.get('reason')} {payload.get('detail')}")
        self.assertEqual(1, payload["provider_calls"], "a decision taken on the new style authorizes it")

    def test_a_run_cut_short_after_a_file_landed_still_counts_it(self) -> None:
        # The file is on disk and its operation is completed, but the process died
        # before the batch bookkeeping. The retry reuses that file, so the revision
        # must recover the chapter instead of waiting forever to redo it.
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "02-forest,03-cottage")
        self.assertEqual(0, code)
        env = dict(os.environ)
        env["FAKE_RUNNER_MODE"] = "ok"
        env["FAKE_RUNNER_DELAY"] = "8"
        env["FAKE_RUNNER_DELAY_MATCH"] = "03-cottage"
        proc = subprocess.Popen(
            [
                sys.executable, str(STAGE), str(self.project), "run-remaining",
                "--runner", str(self.runner),
                "--target", f"02-forest={self.prompts / '02-forest.txt'}",
                "--target", f"03-cottage={self.prompts / '03-cottage.txt'}",
                "--call-timeout", "60",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        try:
            time.sleep(3.5)
        finally:
            proc.kill()
            proc.communicate()
        state = self.state()
        self.assertEqual("completed", [op for op in state["operations"] if op["target"] == "02-forest"][-1]["status"])
        self.assertEqual([], state["revision"]["done"], "the interrupted run never wrote its bookkeeping")
        in_doubt = [op["id"] for op in state["operations"] if op["target"] == "03-cottage" and op["status"] == "committed"]
        self.assertEqual(1, len(in_doubt))
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner),
            "--target", f"02-forest={self.prompts / '02-forest.txt'}",
            "--target", f"03-cottage={self.prompts / '03-cottage.txt'}",
            "--retry-unknown", in_doubt[0],
        )
        self.assertEqual(0, code, f"{payload.get('reason')} {payload.get('detail')}")
        self.assertEqual(1, payload["provider_calls"], "the chapter that already landed is reused")
        self.assertEqual("delivered", payload["phase"], "a chapter that landed before the kill is not still owed")

    def test_a_withdrawn_A_voids_the_samples_built_from_it(self) -> None:
        self.to_producing()
        code, payload = self.stage("record-decision", "--scope", "story", "--decision", "changes-requested")
        self.assertEqual(0, code)
        self.assertEqual("awaiting_story_review", payload["phase"])
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual(0, payload["provider_calls"])
        _, status = self.stage("status")
        self.assertFalse(status["visual_accepted"])

    def test_a_revoked_delegation_returns_to_the_real_gates(self) -> None:
        # A was given for real; only the wait for B was delegated. Withdrawing
        # that delegation must land on B, not drag the accepted draft back.
        self.stage("prepare-review", "--kind", "story", "--sample-ids", SAMPLES[0])
        self.stage("record-display", "--kind", "story")
        self.stage("record-decision", "--scope", "story", "--message-ref", "user-msg-1")
        self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.stage("prepare-review", "--kind", "visual")
        self.stage("record-display", "--kind", "visual")
        code, payload = self.stage("record-decision", "--scope", "delegation", "--stages", "visual")
        self.assertEqual(0, code)
        self.assertEqual("producing", payload["phase"])
        code, payload = self.stage(
            "record-decision", "--scope", "delegation", "--decision", "changes-requested", "--stages", "visual"
        )
        self.assertEqual(0, code)
        self.assertEqual("awaiting_visual_review", payload["phase"])
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual(0, payload["provider_calls"])
        self.assertEqual("collaborative", self.state()["interaction_mode"])

    def test_an_explicit_withdrawal_overrides_an_earlier_delegation(self) -> None:
        # The delegation waived the wait earlier; the user's later "change it" is
        # the newest word, so production must stop instead of finishing the batch.
        self.stage("prepare-review", "--kind", "story", "--sample-ids", ",".join(SAMPLES))
        self.stage("record-display", "--kind", "story")
        self.stage("record-decision", "--scope", "story")
        self.stage("run-samples", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.stage("prepare-review", "--kind", "visual")
        self.stage("record-display", "--kind", "visual")
        code, payload = self.stage("record-decision", "--scope", "delegation", "--stages", "visual")
        self.assertEqual(0, code)
        self.assertEqual("producing", payload["phase"])
        code, payload = self.stage("record-decision", "--scope", "visual", "--decision", "changes-requested")
        self.assertEqual(0, code, payload.get("detail"))
        self.assertEqual("awaiting_visual_review", payload["phase"])
        self.assertEqual("collaborative", self.state()["interaction_mode"])
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("phase_awaiting_visual_review", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])
        made = sorted(path.stem for path in (self.project / "assets" / "images" / "scenes").glob("*.png"))
        self.assertEqual(sorted(SAMPLES), made, "the withdrawn delegation may not produce the remaining scenes")

    def test_consecutive_authorized_sample_replacements_do_not_lock_the_project(self) -> None:
        # Replacing one accepted sample is legitimate; it must not make every
        # later change impossible because the whole old set no longer matches.
        self.to_producing()
        for chapter_id, prompt in (("01-opening", "01-opening"), ("05-wolf", "05-wolf")):
            code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", chapter_id)
            self.assertEqual(0, code, chapter_id)
            code, payload = self.stage(
                "run-remaining", "--runner", str(self.runner), "--target", f"{chapter_id}={self.prompts / (prompt + '.txt')}"
            )
            self.assertEqual(0, code, f"{chapter_id}: {payload.get('reason')} {payload.get('detail')}")
            self.assertEqual(1, payload["provider_calls"], chapter_id)
        code, payload = self.stage("record-decision", "--scope", "revision", "--chapters", "02-forest")
        self.assertEqual(0, code)
        code, payload = self.stage(
            "run-remaining", "--runner", str(self.runner), "--target", f"02-forest={self.prompts / '02-forest.txt'}"
        )
        self.assertEqual(0, code, payload.get("detail"))

    def test_a_second_authorized_replacement_of_one_sample_is_not_blocked(self) -> None:
        # The file on disk came from the first authorized run. A newer revision for
        # the same chapter that has not run yet must not make it read as stale.
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        for attempt in range(2):
            code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "05-wolf")
            self.assertEqual(0, code)
            code, payload = self.stage(
                "run-remaining", "--runner", str(self.runner), "--target", f"05-wolf={self.prompts / '05-wolf.txt'}"
            )
            self.assertEqual(0, code, f"attempt {attempt}: {payload.get('reason')} {payload.get('detail')}")
            self.assertEqual(1, payload["provider_calls"], f"attempt {attempt}")

    def test_a_manual_overwrite_of_a_revised_sample_is_still_refused(self) -> None:
        # Provenance stays pinned to the run: bytes nobody produced are not covered.
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.stage("record-decision", "--scope", "revision", "--chapters", "05-wolf")
        self.stage("run-remaining", "--runner", str(self.runner), "--target", f"05-wolf={self.prompts / '05-wolf.txt'}")
        self.write_png(self.still("05-wolf"), "#123456")
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        self.assertEqual(2, code)
        self.assertEqual("visual_review_stale", payload["reason"])
        self.assertEqual(0, payload["provider_calls"])

    def test_retrying_a_partial_revision_batch_reuses_what_already_succeeded(self) -> None:
        # Chapter two lands and chapter three fails in the same authorized batch;
        # retrying the identical command must not pay for chapter two a second time.
        self.to_producing()
        self.stage("run-remaining", "--runner", str(self.runner), "--prompts-dir", str(self.prompts))
        code, _ = self.stage("record-decision", "--scope", "revision", "--chapters", "02-forest,03-cottage")
        self.assertEqual(0, code)
        targets = ["--target", f"02-forest={self.prompts / '02-forest.txt'}", "--target", f"03-cottage={self.prompts / '03-cottage.txt'}"]
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), *targets, fail_match="03-cottage")
        self.assertEqual(1, code, payload.get("detail"))
        self.assertEqual({"failed", "completed"}, {item["status"] for item in payload["results"]})
        code, payload = self.stage("run-remaining", "--runner", str(self.runner), *targets)
        self.assertEqual(0, code, f"{payload.get('reason')} {payload.get('detail')}")
        self.assertEqual(1, payload["provider_calls"], "only the unfinished chapter is retried")
        by_target = {item["target"]: item["status"] for item in payload["results"]}
        self.assertEqual("skipped_existing", by_target["02-forest"], "the succeeded chapter is reused")
        self.assertEqual("completed", by_target["03-cottage"])
        self.assertEqual("delivered", payload["phase"])

    def write_png(self, path: Path, colour: str) -> None:
        from PIL import Image

        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (128, 72), colour).save(path)


if __name__ == "__main__":
    unittest.main()
