"""Centralized Gemini client.

All engines (claim_extractor, fact_checker, ai_detector, topic_analyzer,
origin_tracer, narrative_generator) call ``call_gemini`` from here
instead of constructing their own client. This is the single chokepoint
where:

  - the genai.Client singleton is owned (one per process)
  - usage_metadata is captured into ``gemini_metrics``
  - latency is timed end-to-end
  - errors are recorded so cost dashboards can show wasted spend
  - OpenTelemetry spans are emitted (when OTel is initialized)

The track helper writes one row best-effort. If the DB write fails, the
caller's Gemini result still returns; observability degrades gracefully.
"""

from app.services.gemini.client import call_gemini, estimate_cost_usd, GEMINI_PRICING


__all__ = ["call_gemini", "estimate_cost_usd", "GEMINI_PRICING"]
