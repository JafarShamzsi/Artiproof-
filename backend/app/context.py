"""Process-wide ContextVars for cross-cutting state.

The request-id ContextVar already lives in ``app.main`` because the
request middleware sets it there. This module is for the rest:
identities that the pipeline layer can stash so deeply-nested helpers
(Gemini client, retry decorators, governance logger) read them without
plumbing parameters through every function signature.

Why ContextVar and not threading.local: every pipeline call goes through
asyncio. Tasks spawned from a request inherit the same context, and a
``run_in_executor`` thread the orchestrator might use still sees the
right value via PEP 567 propagation. threading.local would lose this
on the first ``await``.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional


# Set by the orchestrator at ``run_pipeline_streaming`` start; read by
# the centralized Gemini client when it writes a usage row.
current_user_id: ContextVar[Optional[str]] = ContextVar(
    "current_user_id", default=None
)

# Pipeline linkage so a gemini_metrics row can be joined back to the
# source_check / researcher_profile it served. Both default to None so
# ad-hoc Gemini calls (admin tooling, smoke tests) just don't link.
current_source_check_id: ContextVar[Optional[str]] = ContextVar(
    "current_source_check_id", default=None
)
current_researcher_profile_id: ContextVar[Optional[str]] = ContextVar(
    "current_researcher_profile_id", default=None
)
