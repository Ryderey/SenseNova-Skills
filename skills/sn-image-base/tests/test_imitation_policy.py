from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

POLICY_PATH = (
    Path(__file__).resolve().parents[2]
    / "sn-image-imitate/scripts/imitation_policy.py"
)


def load_policy():
    spec = importlib.util.spec_from_file_location("imitation_policy", POLICY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load imitation policy")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ImitationPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy()

    def setUp(self) -> None:
        self.blueprint = {
            "source_topic_elements": [
                {
                    "id": "topic_1",
                    "reference_element": "旧菜名",
                    "semantic_role": "主标题",
                },
                {
                    "id": "topic_2",
                    "reference_element": "旧食材图标",
                    "semantic_role": "步骤配图",
                },
            ]
        }
        self.rewrite = {
            "target_language": "zh-CN",
            "allowed_foreign_terms": [],
            "rewritten_caption": "主标题为宫保鸡丁，步骤配图改为鸡肉。",
            "semantic_replacement_ledger": [
                {
                    "reference_element_id": "topic_1",
                    "reference_element": "旧菜名",
                    "action": "replace",
                    "target_element": "宫保鸡丁",
                },
                {
                    "reference_element_id": "topic_2",
                    "reference_element": "旧食材图标",
                    "action": "replace",
                    "target_element": "鸡肉图标",
                },
            ],
            "semantic_residue_check": "PASS",
        }

    def test_valid_contract_passes(self) -> None:
        result = self.policy.validate_imitation_contract(
            self.blueprint, self.rewrite, "制作宫保鸡丁中文食谱"
        )
        self.assertTrue(result["valid"])

    def test_missing_ledger_entry_fails(self) -> None:
        self.rewrite["semantic_replacement_ledger"].pop()
        result = self.policy.validate_imitation_contract(
            self.blueprint, self.rewrite, "制作宫保鸡丁中文食谱"
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["missing_ids"], ["topic_2"])

    def test_duplicate_and_unknown_ledger_ids_fail(self) -> None:
        self.rewrite["semantic_replacement_ledger"].extend(
            [
                {
                    "reference_element_id": "topic_1",
                    "reference_element": "旧菜名",
                    "action": "replace",
                    "target_element": "宫保鸡丁",
                },
                {
                    "reference_element_id": "topic_3",
                    "reference_element": "不存在的来源元素",
                    "action": "remove",
                    "target_element": "删除且不改变布局",
                },
            ]
        )
        result = self.policy.validate_imitation_contract(
            self.blueprint, self.rewrite, "制作宫保鸡丁中文食谱"
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["duplicate_ids"], ["topic_1"])
        self.assertEqual(result["unknown_ids"], ["topic_3"])

    def test_unapproved_english_in_chinese_caption_fails(self) -> None:
        self.rewrite["rewritten_caption"] += " 配菜使用 pico de gallo。"
        result = self.policy.validate_imitation_contract(
            self.blueprint, self.rewrite, "制作宫保鸡丁中文食谱"
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["language_contamination"], ["pico de gallo"])

    def test_user_authorized_foreign_term_passes(self) -> None:
        target = "制作中文 AI 行业海报，保留英文 AI"
        self.rewrite["rewritten_caption"] = "制作中文 AI 行业海报。"
        self.rewrite["allowed_foreign_terms"] = [
            {"term": "AI", "user_request_quote": "保留英文 AI"}
        ]
        result = self.policy.validate_imitation_contract(
            self.blueprint, self.rewrite, target
        )
        self.assertTrue(result["valid"])

    def test_carry_over_requires_exact_user_evidence(self) -> None:
        entry = self.rewrite["semantic_replacement_ledger"][0]
        entry.update(
            action="carry_over",
            target_element="旧菜名",
            explicit_user_request_quote="请保留旧菜名",
            compatibility="compatible",
        )
        result = self.policy.validate_imitation_contract(
            self.blueprint, self.rewrite, "制作宫保鸡丁中文食谱"
        )
        self.assertFalse(result["valid"])
        self.assertIn("carry_over 'topic_1' lacks an exact user quote", result["errors"])


if __name__ == "__main__":
    unittest.main()
