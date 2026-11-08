"""Prompt-version hashing + drift detection.

Each engine pins a ``PROMPT_VERSION`` and a ``PROMPT_HASHES`` dict
(the snapshot of every prompt's SHA-256 at the moment the version was
bumped). When the pipeline runs, the live prompt strings are hashed
again and compared to the snapshot:

  - All hashes match → no drift, governance trail is consistent.
  - Any hash differs → drift detected: a Sentry warning fires and the
    per-analysis ``model_metadata.prompt_drift_detected`` is set True.

The CI gate is a unit test (``test_prompt_governance.py``) that
asserts ``compute_prompt_hashes(...) == PROMPT_HASHES`` for both
engines. That catches "developer edited a prompt without bumping the
version" at PR time so the drift can never reach production.

Why hashes and not the raw string
---------------------------------
Storing the raw prompt in ``model_metadata`` on every analysis would
balloon the JSON column for no real benefit — disputes are resolved
by looking up which ``PROMPT_VERSION`` was active and checking the
git history for that version. The hash is enough to tell whether two
analyses ran the same prompt.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Iterable, Mapping

logger = logging.getLogger(__name__)


def compute_prompt_hash(prompt: str) -> str:
    """SHA-256 hex digest of a prompt string.

    Strings are normalised by stripping trailing whitespace on each
    line so that editor auto-formatters that touch trailing spaces
    don't trigger spurious drift. Leading whitespace is preserved
    because it can affect the model's parsing of structured prompts.
    """
    canonical = "\n".join(line.rstrip() for line in prompt.splitlines())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_prompt_hashes(prompts: Mapping[str, str]) -> dict[str, str]:
    """Map prompt-name → hash for a bundle of prompts."""
    return {name: compute_prompt_hash(value) for name, value in prompts.items()}


def check_prompt_drift(
    *,
    engine: str,
    expected: Mapping[str, str],
    live: Mapping[str, str],
) -> bool:
    """True iff any hash in ``live`` differs from ``expected`` (or the
    key sets differ). Logs a warning at WARNING level so Sentry picks
    it up via the existing logging integration.

    Callers (orchestrators) typically call this once per pipeline run
    and record the boolean into ``model_metadata.prompt_drift_detected``.
    """
    drifted: list[str] = []
    for name in sorted(set(expected) | set(live)):
        if expected.get(name) != live.get(name):
            drifted.append(name)
    if drifted:
        logger.warning(
            "prompt drift detected",
            extra={
                "engine": engine,
                "drifted_prompts": drifted,
                "expected_hashes": dict(expected),
                "actual_hashes": dict(live),
            },
        )
    return bool(drifted)


def assert_no_drift(*pairs: tuple[str, Mapping[str, str], Mapping[str, str]]) -> None:
    """Test helper: raise AssertionError if any (engine, expected, live)
    triple shows drift. Used by the CI gate."""
    mismatches: list[str] = []
    for engine, expected, live in pairs:
        for name in sorted(set(expected) | set(live)):
            if expected.get(name) != live.get(name):
                mismatches.append(
                    f"{engine}.{name}: expected={expected.get(name)} "
                    f"actual={live.get(name)}"
                )
    if mismatches:
        joined = "\n  ".join(mismatches)
        raise AssertionError(
            "Prompt hash drift — a prompt was edited without bumping "
            "PROMPT_VERSION + PROMPT_HASHES. Update the engine's "
            "__init__.py with the new hashes and bump PROMPT_VERSION.\n"
            f"  {joined}"
        )


def all_engine_prompt_bundles() -> Iterable[tuple[str, str, dict[str, str]]]:
    """Yield (engine_name, prompt_version, live_hashes) for every engine.

    Used by orchestrators and tests so the list of engines lives in
    one place. Adding a new engine = adding an import + tuple here.
    """
    # Imported lazily so a broken engine module can't crash the whole
    # governance import — the import error surfaces when something
    # actually tries to use that engine.
    from app.services.source_verification import (
        PROMPT_HASHES as SV_HASHES,
        PROMPT_VERSION as SV_VERSION,
        compute_live_prompt_hashes as sv_live,
    )
    from app.services.academic_integrity import (
        PROMPT_HASHES as AI_HASHES,
        PROMPT_VERSION as AI_VERSION,
        compute_live_prompt_hashes as ai_live,
    )

    yield "source_verification", SV_VERSION, sv_live()
    yield "academic_integrity", AI_VERSION, ai_live()
    # The expected hashes are also exposed so test_prompt_governance.py
    # can run the assertion without re-importing each engine.
    _ = SV_HASHES, AI_HASHES  # explicit reference for readers
