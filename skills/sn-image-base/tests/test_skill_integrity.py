from __future__ import annotations

import re
import unittest
from pathlib import Path
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

    def test_infographic_uses_relevance_and_edit_refinement(self) -> None:
        selection = (
            SKILLS_ROOT / "sn-infographic/references/layout-style-selection.md"
        ).read_text(encoding="utf-8")
        skill = (SKILLS_ROOT / "sn-infographic/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Deterministic relevance ranking", selection)
        self.assertNotIn("shuf", selection)
        self.assertIn("1-8", skill)
        self.assertIn("sn-image-edit", skill)
        self.assertIn("Rank all completed candidates", skill)

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


class DocumentationTests(unittest.TestCase):
    LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
    IMAGE_BRANCH_CLONE_COMMAND = (
        "git clone --branch refactor/image-viz --single-branch "
        "https://github.com/Ryderey/SenseNova-Skills.git"
    )

    def test_installation_selects_the_image_branch(self) -> None:
        for name in ("INSTALL.md", "INSTALL_CN.md"):
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            self.assertIn(self.IMAGE_BRANCH_CLONE_COMMAND, text)
            self.assertNotIn("OpenSenseNova/SenseNova-Skills", text)

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


if __name__ == "__main__":
    unittest.main()
