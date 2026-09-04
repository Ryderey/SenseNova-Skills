#!/usr/bin/env python3
"""Validate an imitation rewrite before spending an image API call."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

VALID_ACTIONS = {"replace", "remove", "carry_over"}
CHINESE_LANGUAGE_TAGS = {"chinese", "中文", "简体中文", "繁体中文"}
LATIN_FRAGMENT = re.compile(
    r"[A-Za-z][A-Za-z0-9]*(?:[ \t'’\-]+[A-Za-z][A-Za-z0-9]*)*"
)


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contains_exact_quote(target_content: str, quote: Any) -> bool:
    return _is_nonempty_string(quote) and quote in target_content


def _is_chinese_target(language: Any) -> bool:
    if not _is_nonempty_string(language):
        return False
    normalized = language.strip().casefold()
    return normalized.startswith("zh") or normalized in CHINESE_LANGUAGE_TAGS


def _validate_allowed_terms(
    raw_terms: Any, target_content: str, errors: list[str]
) -> list[str]:
    if not isinstance(raw_terms, list):
        errors.append("allowed_foreign_terms must be a list")
        return []

    terms: list[str] = []
    for index, item in enumerate(raw_terms):
        if not isinstance(item, dict):
            errors.append(f"allowed_foreign_terms[{index}] must be an object")
            continue
        term = item.get("term")
        quote = item.get("user_request_quote")
        if not _is_nonempty_string(term):
            errors.append(f"allowed_foreign_terms[{index}].term is required")
            continue
        if not _contains_exact_quote(target_content, quote) or term not in quote:
            errors.append(
                f"allowed foreign term {term!r} lacks an exact supporting user quote"
            )
            continue
        terms.append(term)

    normalized = [term.casefold() for term in terms]
    if len(normalized) != len(set(normalized)):
        errors.append("allowed_foreign_terms contains duplicates")
    return terms


def _find_language_contamination(caption: Any, language: Any, terms: list[str]) -> list[str]:
    if not _is_nonempty_string(caption) or not _is_chinese_target(language):
        return []
    remaining = caption
    for term in sorted(terms, key=len, reverse=True):
        remaining = re.sub(re.escape(term), "", remaining, flags=re.IGNORECASE)
    return sorted({match.group(0).strip() for match in LATIN_FRAGMENT.finditer(remaining)})


def validate_imitation_contract(
    blueprint: dict[str, Any], rewrite: dict[str, Any], target_content: str
) -> dict[str, Any]:
    errors: list[str] = []
    source_items = blueprint.get("source_topic_elements")
    ledger = rewrite.get("semantic_replacement_ledger")
    if not isinstance(source_items, list):
        errors.append("blueprint.source_topic_elements must be a list")
        source_items = []
    if not isinstance(ledger, list):
        errors.append("rewrite.semantic_replacement_ledger must be a list")
        ledger = []

    source_ids: list[str] = []
    source_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(source_items):
        if not isinstance(item, dict):
            errors.append(f"source_topic_elements[{index}] must be an object")
            continue
        element_id = item.get("id")
        if not _is_nonempty_string(element_id):
            errors.append(f"source_topic_elements[{index}].id is required")
            continue
        source_ids.append(element_id)
        source_by_id.setdefault(element_id, item)
        for field in ("reference_element", "semantic_role"):
            if not _is_nonempty_string(item.get(field)):
                errors.append(f"source element {element_id!r} requires {field}")

    duplicate_source_ids = sorted(
        element_id for element_id, count in Counter(source_ids).items() if count > 1
    )
    if duplicate_source_ids:
        errors.append("duplicate source IDs: " + ", ".join(duplicate_source_ids))

    ledger_ids: list[str] = []
    for index, entry in enumerate(ledger):
        if not isinstance(entry, dict):
            errors.append(f"semantic_replacement_ledger[{index}] must be an object")
            continue
        element_id = entry.get("reference_element_id")
        if not _is_nonempty_string(element_id):
            errors.append(f"semantic_replacement_ledger[{index}].reference_element_id is required")
            continue
        ledger_ids.append(element_id)
        source = source_by_id.get(element_id)
        if source and entry.get("reference_element") != source.get("reference_element"):
            errors.append(f"ledger entry {element_id!r} does not match its source element")

        action = entry.get("action")
        if action not in VALID_ACTIONS:
            errors.append(f"ledger entry {element_id!r} has invalid action {action!r}")
        elif not _is_nonempty_string(entry.get("target_element")):
            errors.append(f"ledger entry {element_id!r} requires target_element")
        if action == "carry_over":
            quote = entry.get("explicit_user_request_quote")
            if not _contains_exact_quote(target_content, quote):
                errors.append(f"carry_over {element_id!r} lacks an exact user quote")
            compatibility = entry.get("compatibility")
            if compatibility not in {"compatible", "intentional_contradiction"}:
                errors.append(f"carry_over {element_id!r} has invalid compatibility")
            if compatibility == "intentional_contradiction" and not _contains_exact_quote(
                target_content, entry.get("contradiction_acknowledgment_quote")
            ):
                errors.append(
                    f"carry_over {element_id!r} lacks contradiction acknowledgment"
                )

    ledger_counts = Counter(ledger_ids)
    duplicate_ledger_ids = sorted(
        element_id for element_id, count in ledger_counts.items() if count > 1
    )
    missing_ids = sorted(set(source_ids) - set(ledger_ids))
    unknown_ids = sorted(set(ledger_ids) - set(source_ids))
    if duplicate_ledger_ids:
        errors.append("duplicate ledger IDs: " + ", ".join(duplicate_ledger_ids))
    if missing_ids:
        errors.append("missing ledger IDs: " + ", ".join(missing_ids))
    if unknown_ids:
        errors.append("unknown ledger IDs: " + ", ".join(unknown_ids))
    if rewrite.get("semantic_residue_check") != "PASS":
        errors.append("semantic_residue_check must be PASS")

    language = rewrite.get("target_language")
    if not _is_nonempty_string(language):
        errors.append("target_language is required")
    allowed_terms = _validate_allowed_terms(
        rewrite.get("allowed_foreign_terms"), target_content, errors
    )
    caption = rewrite.get("rewritten_caption")
    if not _is_nonempty_string(caption):
        errors.append("rewritten_caption is required")
    language_contamination = _find_language_contamination(
        caption, language, allowed_terms
    )
    if language_contamination:
        errors.append(
            "unapproved foreign-language fragments: "
            + ", ".join(language_contamination)
        )

    return {
        "valid": not errors,
        "source_element_count": len(source_ids),
        "ledger_entry_count": len(ledger_ids),
        "missing_ids": missing_ids,
        "duplicate_ids": duplicate_ledger_ids,
        "unknown_ids": unknown_ids,
        "language_contamination": language_contamination,
        "errors": errors,
    }


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint_json", type=Path)
    parser.add_argument("rewrite_json", type=Path)
    parser.add_argument("target_content", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = validate_imitation_contract(
            _load_object(args.blueprint_json),
            _load_object(args.rewrite_json),
            args.target_content.read_text(encoding="utf-8"),
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result = {"valid": False, "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
