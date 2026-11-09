"""Back-compat re-export of the renamed LLMMetric model.

Pre-Phase-9 code imported ``GeminiMetric`` from this module. The table
was renamed to ``llm_metrics`` in migration 0016 and the model lives in
``app.models.llm_metric``. This module re-exports the same class under
the legacy name so existing imports keep working without a code-change
ripple.

Prefer ``from app.models.llm_metric import LLMMetric`` in new code.
"""

from app.models.llm_metric import LLMMetric as GeminiMetric  # noqa: F401


__all__ = ["GeminiMetric"]
