#!/usr/bin/env python3
"""Read-only coverage check for English-to-target Argos Translate models.

This reports whether a model is listed; it does not install models, translate
content, or modify locale files. Model availability is not a quality rating.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CODE_MAP = {"zh-CN": "zh", "zh-TW": "zh"}


def build_coverage(languages: list[dict[str, Any]], packages: list[Any]) -> dict[str, Any]:
    available_pairs = {
        (getattr(package, "from_code", None), getattr(package, "to_code", None))
        for package in packages
    }
    rows = []
    for language in languages:
        code = language["code"]
        target = CODE_MAP.get(code, code)
        if code == "en":
            status = "source-language"
        elif ("en", target) in available_pairs:
            status = "model-listed"
        else:
            status = "no-model-listed"
        rows.append({
            "code": code,
            "name": language.get("name", code),
            "argos_target_code": target,
            "status": status,
        })
    targets: dict[str, list[str]] = {}
    for row in rows:
        if row["code"] != "en":
            targets.setdefault(row["argos_target_code"], []).append(row["code"])
    collisions = {target: codes for target, codes in targets.items() if len(codes) > 1}
    return {
        "report_version": 1,
        "read_only": True,
        "provider": "Argos Translate",
        "model_availability_is_not_quality_approval": True,
        "summary": {
            "registered_languages": len(rows),
            "source_languages": sum(row["status"] == "source-language" for row in rows),
            "model_listed": sum(row["status"] == "model-listed" for row in rows),
            "no_model_listed": sum(row["status"] == "no-model-listed" for row in rows),
            "unique_target_codes": len(targets),
            "target_code_collisions": len(collisions),
        },
        "target_code_collisions": collisions,
        "languages": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    try:
        from argostranslate import package
        registry = json.loads((args.root / "locales/languages.json").read_text(encoding="utf-8"))
        package.update_package_index()
        report = build_coverage(registry.get("languages", []), package.get_available_packages())
    except Exception as exc:
        print(f"Translation engine coverage check failed: {exc}", file=sys.stderr)
        return 2
    output = report["summary"] if args.summary else report
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
