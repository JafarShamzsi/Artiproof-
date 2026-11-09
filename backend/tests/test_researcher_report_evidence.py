"""Report outputs preserve unknown researcher evidence and known zeroes."""

from unittest.mock import AsyncMock

import pytest

from app.services.report_engine.html_template import render_researcher_report, render_institutional_audit_report
from app.services.report_engine import narrative_generator as ng


@pytest.mark.parametrize("score", [None, 0])
def test_researcher_report_distinguishes_unavailable_and_zero(score):
    profile = {"researcher_name": "Researcher", "integrity_score": score,
               "official_h_index": 0, "adjusted_h_index": None if score is None else 0,
               "self_citation_rate": None if score is None else 0}
    single = render_researcher_report(profile, "Available sample only.")
    audit = render_institutional_audit_report([profile])
    for html in (single, audit):
        assert "do not establish" in html or "does not establish" in html
        if score is None:
            assert "Unavailable" in html
            assert "Not assessed" in html
        else:
            assert "Unavailable" not in html
            assert "0.0%" in html
    assert ">0</div>" in single  # Official zero is not replaced by a dash.


@pytest.mark.asyncio
async def test_unavailable_researcher_narrative_does_not_request_model_conclusion(monkeypatch):
    generate = AsyncMock()
    monkeypatch.setattr(ng, "_generate", generate)
    narrative = await ng.generate_researcher_narrative({"integrity_score": None})
    assert "unavailable" in narrative
    assert "do not establish" in narrative
    generate.assert_not_called()


@pytest.mark.asyncio
async def test_researcher_narrative_prompt_preserves_known_zeroes(monkeypatch):
    generate = AsyncMock(return_value="A sample description.")
    monkeypatch.setattr(ng, "_generate", generate)
    await ng.generate_researcher_narrative({
        "integrity_score": 0, "official_h_index": 0, "adjusted_h_index": 0,
        "official_citation_count": 0, "adjusted_citation_count": 0, "self_citation_rate": 0,
    })
    prompt = generate.call_args.args[0]
    assert "OFFICIAL H-INDEX: 0" in prompt
    assert "ADJUSTED H-INDEX: 0" in prompt
    assert "INTEGRITY SCORE: 0/100" in prompt
    assert "not a validated probability" in prompt


def test_researcher_export_includes_coverage_and_safe_paper_links():
    html = render_researcher_report({
        "integrity_score": None,
        "integrity_breakdown": {"final": None, "explanation": "A required lookup failed."},
        "citation_ring_flags": {
            "citation_evidence_status": "partial",
            "coverage": {"papers_attempted": 2, "papers_succeeded": 1, "citations_per_paper_limit": 50},
            "citation_concentration": [{"name": "<script>author</script>", "citations_to_target": 3,
                "relationships": [{"citing_paper_id": 'c1" onclick="bad', "cited_paper_id": "p1"}],
            }],
        },
    }, "Available sample only.")
    assert "1 of 2 attempted publication lookups succeeded" in html
    assert "A required lookup failed." in html
    assert 'href="https://www.semanticscholar.org/paper/p1"' in html
    assert 'href="https://www.semanticscholar.org/paper/c1%22%20onclick%3D%22bad"' in html
    assert "<script>author</script>" not in html
