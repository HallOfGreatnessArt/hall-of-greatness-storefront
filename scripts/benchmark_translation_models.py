#!/usr/bin/env python3
"""Run a small, repeatable CPU smoke benchmark for three free translation engines.

The benchmark writes raw outputs only to a report directory. It never edits locale
files, the catalogue, production configuration, or deployment artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

CASES = [
    {
        "id": "art-heritage",
        "text": "Discover meaningful digital artworks inspired by heritage, imagination, and human connection.",
    },
    {
        "id": "printable-art",
        "text": "Bring timeless art into your home with a high-quality printable digital artwork.",
    },
]
TARGETS = ["fr", "es", "he"]
ENGINES = [
    ("m2m100", "m2m100", "auto"),
    ("madlad400", "madlad", "auto"),
    ("opus_mt", "marian", None),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    binary = args.binary.resolve()
    if not binary.is_file():
        raise SystemExit(f"Benchmark binary not found: {binary}")
    args.output.mkdir(parents=True, exist_ok=True)

    results = []
    failures = []
    for engine_id, backend, model in ENGINES:
        for target in TARGETS:
            model_arg = model or f"opus-mt-en-{target}"
            for case in CASES:
                command = [
                    str(binary), "--backend", backend, "-m", model_arg,
                    "--text", case["text"], "-sl", "en", "-tl", target,
                    "--beam-size", "1",
                ]
                started = time.monotonic()
                try:
                    completed = subprocess.run(
                        command, capture_output=True, text=True,
                        timeout=args.timeout, check=False,
                        env={**os.environ, "OMP_NUM_THREADS": "4"},
                    )
                    elapsed = round(time.monotonic() - started, 2)
                    record = {
                        "engine": engine_id,
                        "backend": backend,
                        "model": model_arg,
                        "target": target,
                        "case": case["id"],
                        "return_code": completed.returncode,
                        "elapsed_seconds": elapsed,
                        "stdout": completed.stdout.strip(),
                        "stderr": completed.stderr.strip()[-4000:],
                    }
                    results.append(record)
                    if completed.returncode != 0:
                        failures.append(f"{engine_id}/{target}/{case['id']}: exit {completed.returncode}")
                except subprocess.TimeoutExpired as exc:
                    elapsed = round(time.monotonic() - started, 2)
                    results.append({
                        "engine": engine_id, "backend": backend,
                        "model": model_arg, "target": target,
                        "case": case["id"], "return_code": None,
                        "elapsed_seconds": elapsed, "stdout": "",
                        "stderr": f"TIMEOUT after {args.timeout}s: {exc}",
                    })
                    failures.append(f"{engine_id}/{target}/{case['id']}: timeout")

    report = {
        "benchmark_version": 1,
        "environment": "GitHub-hosted ubuntu-latest CPU runner",
        "production_files_modified": False,
        "translations_written_to_locale_files": False,
        "languages_tested": TARGETS,
        "cases": CASES,
        "results": results,
        "failures": failures,
        "summary": {
            "attempted": len(results),
            "successful": sum(x["return_code"] == 0 for x in results),
            "failed": len(failures),
        },
    }
    report_path = args.output / "translation-model-benchmark.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# Free translation model benchmark",
        "",
        "CPU-only smoke test; output is experimental and is not a linguistic certification.",
        "",
        "| Engine | Target | Case | Exit | Seconds | Output excerpt |",
        "|---|---|---|---:|---:|---|",
    ]
    for item in results:
        excerpt = (item["stdout"] or item["stderr"]).replace("|", "\\|").replace("\n", " ")[:180]
        md.append(f"| {item['engine']} | {item['target']} | {item['case']} | {item['return_code']} | {item['elapsed_seconds']} | {excerpt} |")
    md.extend(["", f"Successful runs: {report['summary']['successful']}/{report['summary']['attempted']}."])
    (args.output / "translation-model-benchmark.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
