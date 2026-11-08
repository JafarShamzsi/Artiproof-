"""Public exports + prompt-version pinning for the source-verification engine.

When you edit any of the prompts in this package
(``EXTRACTION_PROMPT``, ``VERIFICATION_PROMPT``, ``DETECTION_PROMPT``,
``TRACE_PROMPT``):

1. Bump ``PROMPT_VERSION`` (date-suffixed; revision integer).
2. Re-run the hash and update ``PROMPT_HASHES`` to match. Quickest:

       python -c "from app.governance import compute_prompt_hash; \\
                  from app.services.source_verification.claim_extractor import EXTRACTION_PROMPT; \\
                  print(compute_prompt_hash(EXTRACTION_PROMPT))"

3. The CI test ``test_prompt_governance`` confirms steps 1 and 2 stay
   in sync. Without it a silent prompt edit changes the score
   distribution without any audit trail.
"""

from app.governance.prompt_versioning import compute_prompt_hashes
from app.services.source_verification.orchestrator import SourceVerificationOrchestrator

PROMPT_VERSION = "2026-05-29.v1"

# SHA-256 of each prompt string at the moment PROMPT_VERSION was last
# bumped. Computed via ``app.governance.compute_prompt_hash``; kept in
# sync by the ``test_prompt_governance`` CI test.
PROMPT_HASHES: dict[str, str] = {
    "claim_extractor": "0fd3d5463c8b2dd8bb4ad6373eddcf28f862ff656f0a118041ad87b0125649eb",
    "fact_checker": "2cff3b78495ceb73db45b226f3cb6428dd295fa814f122f087ddadd0e056ccd2",
    "ai_detector": "fd1017c5a9dd62b3e61c9340e0e4adc70cff5c70cbaa82a839cbea61eaa2f03d",
    "origin_tracer": "83ae0de2a423472a12b27ff78da1032acad4a26df9849907b7459af493e35f55",
}


def _gather_prompts() -> dict[str, str]:
    # Imports are local so a broken submodule doesn't crash import of
    # this package — orchestrator still loads, and the failure surfaces
    # when something actually tries to read that prompt.
    from app.services.source_verification.claim_extractor import EXTRACTION_PROMPT
    from app.services.source_verification.fact_checker import VERIFICATION_PROMPT
    from app.services.source_verification.ai_detector import DETECTION_PROMPT
    from app.services.source_verification.origin_tracer import TRACE_PROMPT

    return {
        "claim_extractor": EXTRACTION_PROMPT,
        "fact_checker": VERIFICATION_PROMPT,
        "ai_detector": DETECTION_PROMPT,
        "origin_tracer": TRACE_PROMPT,
    }


def compute_live_prompt_hashes() -> dict[str, str]:
    """Hash every prompt string as currently loaded. Compared against
    ``PROMPT_HASHES`` at pipeline start to detect drift."""
    return compute_prompt_hashes(_gather_prompts())


__all__ = [
    "SourceVerificationOrchestrator",
    "PROMPT_VERSION",
    "PROMPT_HASHES",
    "compute_live_prompt_hashes",
]
