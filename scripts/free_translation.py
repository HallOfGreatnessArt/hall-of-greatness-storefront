"""Free local translation fallback shared by catalogue and product-page builders.

Argos is preferred when a direct English-to-target package is installed.
MADLAD-400 (via the pinned CPU-only CrispASR CLI) is the broad-coverage fallback.
No paid API, key, account, or remote translation service is used.
"""
from __future__ import annotations

import functools
import os
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
        binary,
        "--backend", "madlad",
        "-m", "auto",
        "--text", text,
        "-sl", "en",
        "-tl", target,
        "--beam-size", "1",
        "--translate-max-tokens", "512",
        "--threads", "4",
        "--no-gpu",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
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


def translate_text(text: str, target: str, argos_translator=None) -> str | None:
    """Use Argos first, then MADLAD-400 if Argos is absent or fails."""
    source = str(text)
    if argos_translator is not None:
        try:
            translated = argos_translator.translate(source)
            if translated and translated.strip():
                return translated
        except Exception as exc:
            print(f"Argos translation failed for {target}; trying MADLAD-400: {exc}")
    return _madlad_translate(source, target)
