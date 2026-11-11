#!/usr/bin/env python3
"""CPU benchmark of free translation engines, including every storefront locale.

Writes reports only; it never modifies catalogue, locale, production, or deploy files.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

CASES = [
    {"id": "art-heritage", "text": "Discover meaningful digital artworks inspired by heritage, imagination, and human connection."},
    {"id": "printable-art", "text": "Bring timeless art into your home with a high-quality printable digital artwork."},
]
QUALITY_TARGETS = ["fr", "es", "he"]
ENGINES = [
    ("m2m100", "m2m100", "auto", QUALITY_TARGETS),
    ("madlad400", "madlad", "auto", None),
    ("opus_mt", "marian", None, QUALITY_TARGETS),
]


def run_one(binary, engine_id, backend, model, target, case, timeout):
    model_arg = model or f"opus-mt-en-{target}"
    command = [
        str(binary), "--backend", backend, "-m", model_arg,
        "--text", case["text"], "-sl", "en", "-tl", target,
        "--beam-size", "1",
    ]
    if engine_id == "opus_mt":
        command.append("--auto-download")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout,
            check=False, env={**os.environ, "OMP_NUM_THREADS": "4"},
        )
        return {
            "engine": engine_id, "backend": backend, "model": model_arg,
            "target": target, "case": case["id"],
            "return_code": completed.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip()[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "engine": engine_id, "backend": backend, "model": model,
            "target": target, "case": case["id"], "return_code": None,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "stdout": "", "stderr": f"TIMEOUT after {timeout}s: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    binary = args.binary.resolve()
    if not binary.is_file():
        raise SystemExit(f"Benchmark binary not found: {binary}")
    args.output.mkdir(parents=True, exist_ok=True)

    registry = json.loads((args.root / "locales/languages.json").read_text(encoding="utf-8"))
    all_targets = list(dict.fromkeys(
        item["code"] for item in registry["languages"] if item["code"] != "en"
    ))
    results = []
    for engine_id, backend, model, restricted_targets in ENGINES:
        targets = restricted_targets or all_targets
        for target in targets:
            # One short case is enough to detect target-code/model support.
            cases = CASES if target in QUALITY_TARGETS else CASES[:1]
            for case in cases:
                item = run_one(binary, engine_id, backend, model, target, case, args.timeout)
                results.append(item)
                print(json.dumps({
                    "engine": engine_id, "target": target, "case": case["id"],
                    "return_code": item["return_code"], "seconds": item["elapsed_seconds"],
                }), flush=True)

    # Test several low-token boundary styles for reliable MADLAD batching.
    batch_specs = [
        ("bracketed-numbers", ["[1]", "[2]"]),
        ("numbered-list", ["1)", "2)"]),
        ("hash-markers", ["###1###", "###2###"]),
    ]
    batch_results = []
    for case_id, markers in batch_specs:
        batch_text = (
            f"{markers[0]}\\nDiscover meaningful digital artworks inspired by heritage and imagination.\\n"
            f"{markers[1]}\\nBring timeless printable art into your home."
        )
        batch_result = run_one(
            binary, "madlad400", "madlad", "auto", "es",
            {"id": f"batch-{case_id}", "text": batch_text}, args.timeout,
        )
        batch_result["batch_markers_preserved"] = all(marker in batch_result["stdout"] for marker in markers)
        batch_results.append(batch_result)
        results.append(batch_result)


    failures = [
        f"{x['engine']}/{x['target']}/{x['case']}: exit {x['return_code']}"
        for x in results if x["return_code"] != 0
    ]
    by_engine = {}
    for engine_id, *_ in ENGINES:
        rows = [x for x in results if x["engine"] == engine_id]
        by_engine[engine_id] = {
            "attempted": len(rows),
            "successful": sum(x["return_code"] == 0 for x in rows),
            "failed": sum(x["return_code"] != 0 for x in rows),
            "supported_targets": sorted({x["target"] for x in rows if x["return_code"] == 0}),
            "unsupported_targets": sorted({x["target"] for x in rows if x["return_code"] != 0}),
        }
    report = {
        "benchmark_version": 2,
        "environment": "GitHub-hosted ubuntu-latest CPU runner",
        "production_files_modified": False,
        "translations_written_to_locale_files": False,
        "registered_targets": all_targets,
        "quality_targets": QUALITY_TARGETS,
        "engine_summaries": by_engine,
        "results": results,
        "failures": failures,
    }
    (args.output / "translation-model-benchmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        "# Free translation model benchmark", "",
        "CPU-only support and quality smoke tests; not a linguistic certification.", "",
        "| Engine | Registered targets attempted | Successful | Failed |",
        "|---|---:|---:|---:|",
    ]
    for engine, summary in by_engine.items():
        md.append(f"| {engine} | {summary['attempted']} | {summary['successful']} | {summary['failed']} |")
    md.extend(["", "## Per-language support", "", "| Engine | Supported target codes |", "|---|---|"])
    for engine, summary in by_engine.items():
        md.append(f"| {engine} | {', '.join(summary['supported_targets'])} |")
    md.extend(["", "## Sample translations", "", "| Engine | Target | Case | Exit | Seconds | Output |", "|---|---|---|---:|---:|---|"])
    for item in results:
        if item["target"] in QUALITY_TARGETS:
            output = (item["stdout"] or item["stderr"]).replace("|", "\\|").replace("\n", " ")[:180]
            md.append(f"| {item['engine']} | {item['target']} | {item['case']} | {item['return_code']} | {item['elapsed_seconds']} | {output} |")
    (args.output / "translation-model-benchmark.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"targets": len(all_targets), "engines": by_engine}, ensure_ascii=False))
    # Keep the report available even when some registry codes are not supported.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
