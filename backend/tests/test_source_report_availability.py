"""Unavailable assessments must survive report loading and rendering."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.report_engine.html_template import (
    render_source_check_report, render_executive_summary_report, render_comparison_report,
)
from app.services.report_engine import narrative_generator
from app.routers.reports import _load_check_data, _load_check_summaries_batched
from app.tasks.scheduled_reports import _summary_check_data


@pytest.mark.parametrize("renderer", [render_source_check_report, render_executive_summary_report])
def test_single_source_reports_preserve_missing_assessments(renderer):
    html = renderer({
        "overall_credibility_score": None, "ai_content_percentage": None,
        "misinfo_claims_found": None,
    }, "Required evidence is missing.")
    assert "Unavailable" in html
    assert "Not assessed" in html
    assert "look clean" not in html


def test_comparison_report_preserves_missing_score_and_real_zero():
    html = render_comparison_report([
        {"input_title": "Unavailable source", "overall_credibility_score": None},
        {"input_title": "Zero source", "overall_credibility_score": 0},
    ])
    assert "Unavailable" in html
    assert ">0</td>" in html


@pytest.mark.asyncio
async def test_unavailable_narrative_does_not_ask_model_for_conclusion(monkeypatch):
    generate = AsyncMock()
    monkeypatch.setattr(narrative_generator, "_generate", generate)
    text = await narrative_generator.generate_source_check_narrative({"overall_credibility_score": None})
    assert "unavailable" in text
    generate.assert_not_called()


@pytest.mark.asyncio
async def test_report_loaders_do_not_convert_missing_values_to_zero():
    check = SimpleNamespace(
        id="check-id", input_title="Source", input_type="text",
        overall_credibility_score=None, ai_content_percentage=None, misinfo_claims_found=None,
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: []),
    )))
    single = await _load_check_data(check, db)
    batch = await _load_check_summaries_batched([check], db)
    for item in [single, *batch]:
        assert item["overall_credibility_score"] is None
        assert item["ai_content_percentage"] is None
        assert item["misinfo_claims_found"] is None


@pytest.mark.asyncio
async def test_summary_averages_only_completed_available_assessments():
    def check(status, score):
        return SimpleNamespace(status=status, overall_credibility_score=score,
                               ai_content_percentage=None, misinfo_claims_found=None)
    result = await _summary_check_data([
        check("completed", 80), check("completed", 0),
        check("completed", None), check("failed", 100), check("processing", 100),
    ])
    assert result["overall_credibility_score"] == 40
    assert result["scored_checks"] == 2
    assert result["ai_content_percentage"] is None
    assert result["misinfo_claims_found"] is None


@pytest.mark.asyncio
async def test_empty_activity_has_no_assessment():
    result = await _summary_check_data([])
    assert result["overall_credibility_score"] is None
    assert result["ai_content_percentage"] is None
