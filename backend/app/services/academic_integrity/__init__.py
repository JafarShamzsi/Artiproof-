"""Public exports + prompt-version pinning for the academic-integrity engine.

When you edit ``TOPIC_PROMPT`` (or any future prompt added to this
package):

1. Bump ``PROMPT_VERSION``.
2. Re-run the hash and update ``PROMPT_HASHES``.
3. The CI ``test_prompt_governance`` keeps the two in sync.

The version constant + expected hashes are checked at pipeline start
by the orchestrator; drift fires a Sentry warning and is recorded in
``researcher_profile.model_metadata.prompt_drift_detected``.
"""

from app.governance.prompt_versioning import compute_prompt_hashes
from app.services.academic_integrity.orchestrator import AcademicIntegrityOrchestrator

PROMPT_VERSION = "2026-05-29.v1"

PROMPT_HASHES: dict[str, str] = {
    "topic_analyzer": "cdeac46f818c1629d3c340309409daa026b26adf6b16a8e4967b4946869475df",
}


def _gather_prompts() -> dict[str, str]:
    from app.services.academic_integrity.topic_analyzer import TOPIC_PROMPT

    return {
        "topic_analyzer": TOPIC_PROMPT,
    }


def compute_live_prompt_hashes() -> dict[str, str]:
    """Hash every prompt string as currently loaded. Compared against
    ``PROMPT_HASHES`` at pipeline start to detect drift."""
    return compute_prompt_hashes(_gather_prompts())


__all__ = [
    "AcademicIntegrityOrchestrator",
    "PROMPT_VERSION",
    "PROMPT_HASHES",
    "compute_live_prompt_hashes",
]
