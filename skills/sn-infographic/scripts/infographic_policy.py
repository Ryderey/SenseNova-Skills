#!/usr/bin/env python3
"""Deterministic density, correction-mode, and round-budget policy."""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

TEXT_UNIT_LIMIT = 48
HAN_CHARACTER_LIMIT = 300
MAX_EDIT_TEXT_VIOLATIONS = 3
DEFAULT_ROUNDS = 1
MAX_ROUNDS = 15
STAGNATION_LIMIT = 3


def count_han_characters(texts: list[str]) -> int:
    return sum(
        unicodedata.name(character, "").startswith(
            ("CJK UNIFIED IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-")
        )
        for text in texts
        for character in text
    )


def assess_text_density(texts: list[str]) -> dict[str, int | str]:
    han_count = count_han_characters(texts)
    return {
        "required_text_unit_count": len(texts),
        "cjk_character_count": han_count,
        "text_density_risk": (
            "high"
            if han_count
            and (len(texts) > TEXT_UNIT_LIMIT or han_count > HAN_CHARACTER_LIMIT)
            else "normal"
        ),
    }


def choose_correction_mode(
    text_violation_count: int,
    *,
    localized_visual_correction: bool = False,
    short_text_only: bool = True,
    large_cjk_rewrite: bool = False,
    repeated_entry_error: bool = False,
    layout_topology_change: bool = False,
) -> str:
    if text_violation_count < 0:
        raise ValueError("text_violation_count must be non-negative")
    if (
        text_violation_count > MAX_EDIT_TEXT_VIOLATIONS
        or (text_violation_count and not short_text_only)
        or large_cjk_rewrite
        or repeated_entry_error
        or layout_topology_change
    ):
        return "regenerate"
    if localized_visual_correction or text_violation_count:
        return "edit"
    return "regenerate"


def clamp_rounds(requested: int | None) -> int:
    if requested is None:
        return DEFAULT_ROUNDS
    return min(MAX_ROUNDS, max(1, requested))


def should_stop_for_stagnation(non_improving_rounds: int) -> bool:
    if non_improving_rounds < 0:
        raise ValueError("non_improving_rounds must be non-negative")
    return non_improving_rounds >= STAGNATION_LIMIT


def load_inventory_texts(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    inventory = payload.get("required_text_inventory") if isinstance(payload, dict) else payload
    if not isinstance(inventory, list):
        raise TypeError("input must be an inventory list or contain required_text_inventory")
    texts: list[str] = []
    for item in inventory:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise TypeError("each inventory item must contain a string text field")
        texts.append(item["text"])
    return texts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    density = commands.add_parser("density", help="Measure an exact-text inventory")
    density.add_argument("inventory_json", type=Path)

    rounds = commands.add_parser("rounds", help="Clamp a requested round budget")
    rounds.add_argument("requested", nargs="?", type=int)

    correction = commands.add_parser("correction", help="Choose edit or regenerate")
    correction.add_argument("--text-violations", type=int, required=True)
    correction.add_argument("--localized-visual", action="store_true")
    correction.add_argument("--long-text", action="store_true")
    correction.add_argument("--large-cjk-rewrite", action="store_true")
    correction.add_argument("--repeated-entry-error", action="store_true")
    correction.add_argument("--layout-topology-change", action="store_true")

    stagnation = commands.add_parser("stagnation", help="Check the no-improvement limit")
    stagnation.add_argument("non_improving_rounds", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "density":
            result = assess_text_density(load_inventory_texts(args.inventory_json))
        elif args.command == "rounds":
            result = {"max_rounds": clamp_rounds(args.requested)}
        elif args.command == "correction":
            result = {
                "mode": choose_correction_mode(
                    args.text_violations,
                    localized_visual_correction=args.localized_visual,
                    short_text_only=not args.long_text,
                    large_cjk_rewrite=args.large_cjk_rewrite,
                    repeated_entry_error=args.repeated_entry_error,
                    layout_topology_change=args.layout_topology_change,
                )
            }
        else:
            result = {"stop": should_stop_for_stagnation(args.non_improving_rounds)}
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
