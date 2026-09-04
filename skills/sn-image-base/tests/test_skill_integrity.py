from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / "skills"
EXPECTED_SKILLS = {
    "sn-image-base",
    "sn-image-doctor",
    "sn-image-imitate",
    "sn-image-resume",
    "sn-infographic",
}
DOCTOR_SCRIPT = SKILLS_ROOT / "sn-image-doctor/scripts/check_environment.py"
INFOGRAPHIC_POLICY_SCRIPT = (
    SKILLS_ROOT / "sn-infographic/scripts/infographic_policy.py"
)


def load_doctor_module():
    spec = importlib.util.spec_from_file_location("sn_image_doctor", DOCTOR_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load sn-image-doctor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_infographic_policy_module():
    spec = importlib.util.spec_from_file_location(
        "sn_infographic_policy", INFOGRAPHIC_POLICY_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load sn-infographic policy")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryScopeTests(unittest.TestCase):
    def test_exactly_five_skills_remain(self) -> None:
        actual = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
        self.assertEqual(actual, EXPECTED_SKILLS)
        self.assertFalse((REPO_ROOT / "examples").exists())

    def test_full_infographic_catalog_remains(self) -> None:
        root = SKILLS_ROOT / "sn-infographic" / "references"
        layouts = list((root / "layouts").glob("*.md"))
        styles = list((root / "styles").glob("*.md"))
        self.assertEqual(len(layouts), 87)
        self.assertEqual(len(styles), 66)
        self.assertTrue(all(path.stat().st_size > 50 for path in layouts + styles))

    def test_infographic_uses_relevance_and_iterative_refinement(self) -> None:
        selection = (
            SKILLS_ROOT / "sn-infographic/references/layout-style-selection.md"
        ).read_text(encoding="utf-8")
        skill = (SKILLS_ROOT / "sn-infographic/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Deterministic relevance ranking", selection)
        self.assertNotIn("shuf", selection)
        self.assertIn("sn-image-edit", skill)
        self.assertIn("Rank all completed candidates", skill)

    def test_infographic_confirms_visual_direction_before_generation(self) -> None:
        skill = (SKILLS_ROOT / "sn-infographic/SKILL.md").read_text(encoding="utf-8")
        selection = (
            SKILLS_ROOT / "sn-infographic/references/layout-style-selection.md"
        ).read_text(encoding="utf-8")
        analysis = (
            SKILLS_ROOT / "sn-infographic/references/analysis-framework.md"
        ).read_text(encoding="utf-8")

        self.assertLess(
            skill.index("selection_mode=confirm"), skill.index("Generate round 1")
        )
        for source in ("user_explicit", "user_confirmed", "auto"):
            self.assertIn(f"selection_source={source}", selection)
        self.assertIn("Do not assemble the final prompt", selection)
        self.assertIn("Clarity-first", selection)
        self.assertIn("Expressive", selection)
        self.assertIn('"status": "pending"', analysis)
        self.assertEqual(analysis.count('"tradeoff": "[Concrete tradeoff]"'), 3)

    def test_imitation_and_resume_keep_full_workflows(self) -> None:
        imitate = (SKILLS_ROOT / "sn-image-imitate/SKILL.md").read_text(
            encoding="utf-8"
        )
        resume = (SKILLS_ROOT / "sn-image-resume/SKILL.md").read_text(encoding="utf-8")
        resume_prompt = (SKILLS_ROOT / "sn-image-resume/prompts/resume.md").read_text(
            encoding="utf-8"
        )
        for prompt in ("image_annotate.md", "caption_rewrite.md", "layout_review.md"):
            self.assertTrue(
                (SKILLS_ROOT / "sn-image-imitate/prompts" / prompt).is_file()
            )
        self.assertIn("sn-image-edit", imitate)
        self.assertIn("layout_similarity_score", imitate)
        self.assertIn("Fact ledger", resume)
        self.assertIn("sn-image-edit", resume)
        self.assertIn("Factual Integrity Rule (Highest Priority)", resume_prompt)

    def test_prompt_contracts_enforce_facts_and_semantic_replacement(self) -> None:
        infographic = (SKILLS_ROOT / "sn-infographic/SKILL.md").read_text(
            encoding="utf-8"
        )
        critic = (
            SKILLS_ROOT / "sn-infographic/references/prompts-critic-system.md"
        ).read_text(encoding="utf-8")
        imitation = (SKILLS_ROOT / "sn-image-imitate/SKILL.md").read_text(
            encoding="utf-8"
        )
        rewrite = (
            SKILLS_ROOT / "sn-image-imitate/prompts/caption_rewrite.md"
        ).read_text(encoding="utf-8")
        annotate = (
            SKILLS_ROOT / "sn-image-imitate/prompts/image_annotate.md"
        ).read_text(encoding="utf-8")
        review = (SKILLS_ROOT / "sn-image-imitate/prompts/layout_review.md").read_text(
            encoding="utf-8"
        )
        resume = (SKILLS_ROOT / "sn-image-resume/prompts/resume.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("fact ledger", infographic.lower())
        for token in ("dimension_scores", "red_lines", '"score"', "score >= 0.90"):
            self.assertIn(token, critic)
        self.assertIn("semantic replacement ledger", imitation)
        self.assertIn("semantic compatibility check", rewrite)
        self.assertIn("reference_element_id", rewrite)
        self.assertIn("target_language", rewrite)
        self.assertIn("source_topic_elements", annotate)
        self.assertIn("explicit_user_request_quote", rewrite)
        self.assertIn("contradiction_acknowledgment_quote", rewrite)
        self.assertIn('"semantic_residue_check": "PASS"', rewrite)
        self.assertIn("Mexican chicken taco", rewrite)
        self.assertIn("target content request", review)
        self.assertIn("semantic_residue", review)
        self.assertIn("language_contamination", review)
        self.assertIn("ledger_errors", review)
        self.assertIn("check_environment.py", imitation)
        self.assertIn("imitation_policy.py", imitation)
        self.assertEqual(imitation.count("--no-prompt-extend"), 3)
        self.assertLess(
            imitation.index("0. Before reference analysis"),
            imitation.index("1. Validate the reference"),
        )
        self.assertIn("Portrait and QR gate", resume)
        self.assertIn("Omit QR codes entirely", resume)
        self.assertNotIn("rewritten, expanded", resume)
        self.assertIn("Only narrative prose and structural headings", resume)
        self.assertNotIn("All user information mapped", resume)
        self.assertIn("including round 1", infographic)

    def test_image_skill_commands_inherit_the_u15_primary_default(self) -> None:
        for name in (
            "sn-image-base",
            "sn-infographic",
            "sn-image-imitate",
            "sn-image-resume",
        ):
            text = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
            image_commands = [
                block
                for block in re.findall(r"```bash\n(.*?)```", text, re.DOTALL)
                if "sn-image-generate" in block or "sn-image-edit" in block
            ]
            self.assertTrue(image_commands, name)
            self.assertTrue(
                all("--model" not in command for command in image_commands), name
            )

    def test_legacy_host_paths_are_absent(self) -> None:
        legacy_host = "open" + "claw"
        offenders = []
        for path in REPO_ROOT.rglob("*"):
            if path.suffix not in {".md", ".py"}:
                continue
            if any(part in {".git", ".venv"} for part in path.parts):
                continue
            if legacy_host in path.read_text(encoding="utf-8").lower():
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [])

    def test_generation_backends_share_a_portable_output_directory(self) -> None:
        scripts = SKILLS_ROOT / "sn-image-base/scripts"
        sys.path.insert(0, str(scripts))
        try:
            from sn_image_base.generation import nano_banana, openai_image, sensenova

            output_dirs = {
                nano_banana.OUTPUT_DIR,
                openai_image.OUTPUT_DIR,
                sensenova.OUTPUT_DIR,
            }
        finally:
            sys.path.pop(0)
        self.assertEqual(output_dirs, {Path(tempfile.gettempdir()) / "sensenova-image"})

    def test_infographic_gallery_has_no_orphan_images(self) -> None:
        image_names = {
            path.name
            for path in (REPO_ROOT / "docs/images/infographics").glob("*.webp")
        }
        for name in ("sn-infographic-examples.md", "sn-infographic-examples_CN.md"):
            text = (REPO_ROOT / "docs" / name).read_text(encoding="utf-8")
            referenced = set(re.findall(r"images/infographics/([^\"')]+\.webp)", text))
            self.assertEqual(referenced, image_names, name)


class DocumentationTests(unittest.TestCase):
    LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
    CANONICAL_CLONE_COMMAND = "git clone https://github.com/Ryderey/SenseNova-Skills.git"

    def test_installation_uses_the_canonical_default_branch(self) -> None:
        for name in ("INSTALL.md", "INSTALL_CN.md"):
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            self.assertIn(self.CANONICAL_CLONE_COMMAND, text)
            self.assertNotIn("--branch image-viz", text)
            self.assertNotIn("OpenSenseNova/SenseNova-Skills", text)

    def test_env_example_lists_every_supported_shared_runtime_setting(self) -> None:
        example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        for key in ("SN_BASE_URL", "SN_CHAT_TYPE", "SN_TEXT_TYPE", "SN_VISION_TYPE"):
            self.assertRegex(example, rf"(?m)^{key}=.*$")

    def test_skill_runtime_commands_are_location_independent(self) -> None:
        forbidden = (
            "$SN_IMAGE_BASE",
            "python scripts/",
            "pip install -r requirements.txt",
            "pip install -r ../sn-image-base/requirements.txt",
        )
        for path in SKILLS_ROOT.glob("*/SKILL.md"):
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{path.relative_to(REPO_ROOT)}: {token}")

    def test_skills_define_platform_api_key_discovery(self) -> None:
        base = (SKILLS_ROOT / "sn-image-base/SKILL.md").read_text(encoding="utf-8")
        doctor = (SKILLS_ROOT / "sn-image-doctor/SKILL.md").read_text(encoding="utf-8")
        for token in (
            r"HKEY_CURRENT_USER\Environment",
            r"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            "~/.bashrc",
            "~/.zshrc",
            "project `.env`",
        ):
            self.assertIn(token, base)
        self.assertIn("Credential discovery", doctor)
        self.assertIn("never print the key", doctor)

    def test_official_docs_links_do_not_use_unreliable_model_hashes(self) -> None:
        for path in REPO_ROOT.rglob("*.md"):
            if any(part in {".git", ".venv"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "https://platform.sensenova.cn/docs#model-",
                text,
                str(path.relative_to(REPO_ROOT)),
            )

    def test_relative_markdown_links_resolve(self) -> None:
        missing: list[str] = []
        for markdown in REPO_ROOT.rglob("*.md"):
            if any(part in {".git", ".venv"} for part in markdown.parts):
                continue
            text = markdown.read_text(encoding="utf-8")
            for raw_target in self.LINK.findall(text):
                target = raw_target.strip().split(" ", 1)[0].strip("<>")
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                relative = unquote(target.split("#", 1)[0])
                if relative and not (markdown.parent / relative).resolve().exists():
                    missing.append(f"{markdown.relative_to(REPO_ROOT)} -> {target}")
        self.assertEqual(
            missing, [], "Broken local Markdown links:\n" + "\n".join(missing)
        )

class InfographicPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_infographic_policy_module()

    def test_density_boundaries_and_unicode_han_count(self) -> None:
        self.assertEqual(self.policy.TEXT_UNIT_LIMIT, 48)
        self.assertEqual(self.policy.HAN_CHARACTER_LIMIT, 300)
        self.assertEqual(
            self.policy.assess_text_density(["中"] * 48)["text_density_risk"],
            "normal",
        )
        self.assertEqual(
            self.policy.assess_text_density(["中"] * 49)["text_density_risk"],
            "high",
        )
        self.assertEqual(
            self.policy.assess_text_density(["中" * 300])["text_density_risk"],
            "normal",
        )
        self.assertEqual(
            self.policy.assess_text_density(["中" * 301])["text_density_risk"],
            "high",
        )
        self.assertEqual(
            self.policy.count_han_characters(["中\ufa0e\U00020000"]),
            3,
        )

    def test_correction_mode_covers_every_error_scope(self) -> None:
        choose = self.policy.choose_correction_mode
        self.assertEqual(choose(0, localized_visual_correction=True), "edit")
        self.assertEqual(choose(3), "edit")
        self.assertEqual(choose(4), "regenerate")
        self.assertEqual(choose(1, short_text_only=False), "regenerate")
        self.assertEqual(choose(1, large_cjk_rewrite=True), "regenerate")
        self.assertEqual(choose(1, repeated_entry_error=True), "regenerate")
        self.assertEqual(choose(1, layout_topology_change=True), "regenerate")

    def test_round_and_stagnation_boundaries(self) -> None:
        self.assertEqual(self.policy.clamp_rounds(None), 1)
        self.assertEqual(self.policy.clamp_rounds(0), 1)
        self.assertEqual(self.policy.clamp_rounds(15), 15)
        self.assertEqual(self.policy.clamp_rounds(16), 15)
        self.assertFalse(self.policy.should_stop_for_stagnation(2))
        self.assertTrue(self.policy.should_stop_for_stagnation(3))


class DoctorTests(unittest.TestCase):
    def test_selected_optional_adapter_must_have_a_complete_valid_runtime(self) -> None:
        doctor = load_doctor_module()
        configs = SimpleNamespace(
            SN_TEXT_MODEL="text-model",
            SN_TEXT_API_KEY="",
            SN_TEXT_BASE_URL="not-a-url",
            SN_TEXT_TYPE="unknown",
            SN_VISION_MODEL="",
            SN_VISION_API_KEY="",
            SN_VISION_BASE_URL="",
            SN_VISION_TYPE="",
        )
        output = io.StringIO()
        with (
            patch.object(
                doctor,
                "_load_runtime",
                return_value=(
                    configs,
                    lambda value: value.startswith(("http://", "https://")),
                    {"anthropic-messages", "openai-completions"},
                ),
            ),
            contextlib.redirect_stdout(output),
        ):
            result = doctor.check_optional_chat_runtime(verbose=False)
        self.assertFalse(result)
        self.assertIn("[FAIL] text adapter", output.getvalue())

    def test_invalid_base_url_is_reported_without_a_traceback(self) -> None:
        env = os.environ.copy()
        env.update(
            SENSENOVA_API_KEY="diagnostic-placeholder",
            SN_IMAGE_GEN_BASE_URL="not-a-url",
        )
        result = subprocess.run(
            [sys.executable, str(DOCTOR_SCRIPT), "--verbose"],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] Image runtime validation failed", output)
        self.assertIn("=== Summary ===", output)
        self.assertNotIn("Traceback", output)

    def test_typing_extensions_is_checked_as_a_runtime_dependency(self) -> None:
        doctor = load_doctor_module()

        def fake_find_spec(name: str):
            return None if name == "typing_extensions" else object()

        output = io.StringIO()
        with (
            patch.object(
                doctor.importlib.util, "find_spec", side_effect=fake_find_spec
            ),
            contextlib.redirect_stdout(output),
        ):
            result = doctor.check_dependencies(verbose=False)
        self.assertFalse(result)
        self.assertIn("typing-extensions", output.getvalue())

    def test_unrelated_skill_can_coexist_with_required_skills(self) -> None:
        doctor = load_doctor_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_root = Path(temp_dir)
            for name in EXPECTED_SKILLS | {"sn-unrelated-skill"}:
                skill_dir = skills_root / name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text("# test\n", encoding="utf-8")
            base = skills_root / "sn-image-base"
            (base / "requirements.txt").write_text("", encoding="utf-8")
            (base / "scripts/sn_image_base/generation").mkdir(parents=True)
            (base / "scripts/sn_agent_runner.py").write_text("", encoding="utf-8")
            (base / "scripts/sn_image_base/generation/sensenova.py").write_text(
                "", encoding="utf-8"
            )

            with (
                patch.object(doctor, "SKILLS_DIR", skills_root),
                patch.object(doctor, "BASE_SKILL_DIR", base),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = doctor.check_installation(verbose=False)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
