"""Free local translation fallback shared by catalogue and product-page builders.

Argos is preferred when a direct English-to-target package is installed.
MADLAD-400 (via the pinned CPU-only CrispASR CLI) is the broad-coverage fallback.
No paid API, key, account, or remote translation service is used.
"""
from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess


TARGET_CODE_MAP = {
    "zh-CN": "zh",
    "zh-TW": "zh",
}


def crispasr_binary() -> str | None:
    configured = os.environ.get("CRISPASR_BIN")
    if configured and os.path.isfile(configured):
        return configured
    return shutil.which("crispasr")


def has_fallback_engine() -> bool:
    return crispasr_binary() is not None


@functools.lru_cache(maxsize=8192)
def _madlad_translate(text: str, target: str) -> str | None:
    binary = crispasr_binary()
    if not binary:
        return None
    target = TARGET_CODE_MAP.get(target, target)
    command = [
        binary, "--backend", "madlad", "-m", "auto",
        "--text", text, "-sl", "en", "-tl", target,
        "--beam-size", "1", "--translate-max-tokens", "1024",
        "--threads", "4", "--no-gpu",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=240, check=False,
            env={**os.environ, "OMP_NUM_THREADS": "4"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"MADLAD fallback error for {target}: {exc}")
        return None
    translated = result.stdout.strip()
    if result.returncode != 0 or not translated:
        detail = result.stderr.strip().splitlines()
        print(
            f"MADLAD fallback unavailable for {target} "
            f"(exit {result.returncode}): {' | '.join(detail[-3:])}"
        )
        return None
    return translated


def _chunks(indexed_texts, max_words=300):
    chunk = []
    words = 0
    for index, text in indexed_texts:
        count = max(1, len(text.split()))
        if chunk and words + count > max_words:
            yield chunk
            chunk, words = [], 0
        chunk.append((index, text))
        words += count
    if chunk:
        yield chunk


def _translate_batch(chunk, target):
    markers = [(index, f"ZXQHOGSEGMENT{index:06d}QXZ", text) for index, text in chunk]
    combined = "\n".join(f"{marker}\n{text}" for _, marker, text in markers)
    output = _madlad_translate(combined, target)
    if not output:
        return None
    # Only accept batching if the model preserves every unique boundary marker.
    positions = [output.find(marker) for _, marker, _ in markers]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        return None
    translated = {}
    for item_index, (index, marker, _) in enumerate(markers):
        start = positions[item_index] + len(marker)
        end = positions[item_index + 1] if item_index + 1 < len(markers) else len(output)
        value = output[start:end].strip(" \t\r\n:—-")
        if not value:
            return None
        translated[index] = value
    return translated


def translate_texts(texts, target: str, argos_translator=None) -> list[str] | None:
    """Translate a list efficiently; preserve order and use MADLAD for Argos gaps."""
    source_texts = [str(value) for value in texts]
    results: list[str | None] = [None] * len(source_texts)
    pending = []
    for index, source in enumerate(source_texts):
        if argos_translator is not None:
            try:
                value = argos_translator.translate(source)
                if value and value.strip():
                    results[index] = value
                    continue
            except Exception as exc:
                print(f"Argos translation failed for {target}; trying MADLAD-400: {exc}")
        pending.append((index, source))

    for chunk in _chunks(pending):
        if len(chunk) == 1:
            index, source = chunk[0]
            results[index] = _madlad_translate(source, target)
            continue
        batch_result = _translate_batch(chunk, target)
        if batch_result is not None:
            for index, value in batch_result.items():
                results[index] = value
            continue
        # A boundary-marker mismatch is not allowed to corrupt alignment.
        for index, source in chunk:
            results[index] = _madlad_translate(source, target)

    if any(value is None for value in results):
        return None
    return [str(value) for value in results]


def translate_text(text: str, target: str, argos_translator=None) -> str | None:
    """Single-string convenience wrapper."""
    values = translate_texts([str(text)], target, argos_translator)
    return values[0] if values else None
