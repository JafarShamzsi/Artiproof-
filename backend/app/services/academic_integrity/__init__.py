"""Public exports + prompt-version pinning for the academic-integrity engine.

This engine is fully deterministic — it has no LLM prompts, so the registry
below is intentionally empty. The scaffolding stays so adding a prompt later is
a small change:

1. Add the prompt to ``_gather_prompts`` and ``PROMPT_HASHES``.
2. Bump ``PROMPT_VERSION``.
3. The CI ``test_prompt_governance`` keeps the two in sync.

The version constant + expected hashes are stamped into
``researcher_profile.model_metadata`` at pipeline start for the audit trail.
"""

from app.governance.prompt_versioning import compute_prompt_hashes
from app.services.academic_integrity.orchestrator import AcademicIntegrityOrchestrator

PROMPT_VERSION = "2026-06-01.v1"

# No LLM prompts in this engine — topic relevance is deterministic (OpenAlex).
PROMPT_HASHES: dict[str, str] = {}


def _gather_prompts() -> dict[str, str]:
    return {}


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
