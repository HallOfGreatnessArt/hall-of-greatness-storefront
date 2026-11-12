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


TARGET_CODE_MAP = {}


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
            command, capture_output=True, text=True, timeout=90, check=False,
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


def _split_long_text(text: str, max_words: int = 220) -> list[list[str]]:
    """Split very long descriptions at sentence boundaries, retaining paragraphs."""
    groups = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        parts = []
        current = []
        current_words = 0
        for sentence in sentences:
            sentence_words = len(sentence.split())
            if current and current_words + sentence_words > max_words:
                parts.append(" ".join(current))
                current, current_words = [], 0
            if sentence_words > max_words:
                words = sentence.split()
                for offset in range(0, len(words), max_words):
                    piece = " ".join(words[offset:offset + max_words])
                    if piece:
                        if current:
                            parts.append(" ".join(current))
                            current, current_words = [], 0
                        parts.append(piece)
                continue
            current.append(sentence)
            current_words += sentence_words
        if current:
            parts.append(" ".join(current))
        groups.append(parts)
    return groups or [[text]]


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
    markers = [(index, f"[{position + 1}]", text) for position, (index, text) in enumerate(chunk)]
    combined = "\n".join(f"{marker}\n{text}" for _, marker, text in markers)
    output = _madlad_translate(combined, target)
    if not output:
        return None
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
    pending_parts = []
    part_layout = {}

    for index, source in enumerate(source_texts):
        if argos_translator is not None:
            try:
                value = argos_translator.translate(source)
                if value and value.strip():
                    results[index] = value
                    continue
            except Exception as exc:
                print(f"Argos translation failed for {target}; trying MADLAD-400: {exc}")

        paragraphs = _split_long_text(source)
        part_layout[index] = paragraphs
        for paragraph_index, parts in enumerate(paragraphs):
            for part_index, part in enumerate(parts):
                segment_id = len(pending_parts)
                pending_parts.append((segment_id, part))
                part_layout[index][paragraph_index][part_index] = (segment_id, part)

    translated_parts = {}
    for chunk in _chunks(pending_parts):
        if len(chunk) == 1:
            segment_id, source = chunk[0]
            translated_parts[segment_id] = _madlad_translate(source, target)
            continue
        batch_result = _translate_batch(chunk, target)
        if batch_result is not None:
            translated_parts.update(batch_result)
            continue
        # A boundary-marker mismatch is not allowed to corrupt paragraph alignment.
        for segment_id, source in chunk:
            translated_parts[segment_id] = _madlad_translate(source, target)

    for index, paragraphs in part_layout.items():
        rebuilt = []
        for parts in paragraphs:
            values = [translated_parts.get(segment_id) for segment_id, _ in parts]
            if any(value is None for value in values):
                results[index] = None
                break
            rebuilt.append(" ".join(str(value).strip() for value in values))
        else:
            results[index] = "\n\n".join(rebuilt)

    if any(value is None for value in results):
        return None
    return [str(value) for value in results]


def translate_text(text: str, target: str, argos_translator=None) -> str | None:
    values = translate_texts([str(text)], target, argos_translator)
    return values[0] if values else None
