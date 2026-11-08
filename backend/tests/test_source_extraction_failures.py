"""An input identifier must never substitute for unavailable source content."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.source_verification import orchestrator as svo


@pytest.mark.asyncio
@pytest.mark.parametrize("input_type, path, scraped", [
    ("url", None, {"error": "HTTP 503", "body": ""}),
    ("url", None, {"error": None, "body": ""}),
    ("document", None, None),
    ("document", "missing.pdf", None),
])
async def test_failed_extraction_does_not_analyze_identifier(monkeypatch, input_type, path, scraped):
    check = SimpleNamespace(
        id="check-id", user_id="user-id", input_type=input_type,
        input_content="https://example.com/" + "long-identifier" * 10,
        original_pdf_path=path, input_title=None, status="pending",
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: check)),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(svo, "scrape_url", AsyncMock(return_value=scraped))
    extract_claims = AsyncMock()
    monkeypatch.setattr(svo, "extract_claims", extract_claims)
    if path:
        from app.services.source_verification import pdf_processor
        monkeypatch.setattr(pdf_processor, "extract_text_with_positions", Mock(side_effect=OSError))

    events = [event async for event in svo.SourceVerificationOrchestrator(db).run_pipeline_streaming(check.id)]

    assert check.status == "failed"
    assert check.completed_at is not None
    assert check.overall_credibility_score is None
    assert check.ai_content_percentage is None
    assert check.misinfo_claims_found is None
    assert check.score_breakdown is None
    assert check.model_metadata["context"]["text_length"] == 0
    assert any(w["type"] == "insufficient_source_text" for w in check.model_metadata["processing_warnings"])
    assert events[-1]["status"] == "failed"
    extract_claims.assert_not_called()


@pytest.mark.asyncio
async def test_failed_claim_and_ai_service_preserve_other_claim_findings(monkeypatch):
    check = SimpleNamespace(id="check", user_id="owner", input_type="text",
        input_content="Readable text. " * 20, original_pdf_path=None, input_title=None, status="pending")
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: check)),
                         commit=AsyncMock(), add=Mock())
    monkeypatch.setattr(svo, "extract_claims", AsyncMock(return_value=[{"claim_text": "known"}, {"claim_text": "unknown"}]))
    async def verify(text, context):
        if text == "unknown":
            raise ConnectionError("Verification unavailable")
        return {"verdict": "true", "confidence": 0.8, "explanation": "Supported", "sources": []}
    monkeypatch.setattr(svo, "verify_claim", verify)
    monkeypatch.setattr(svo, "detect_ai_content", AsyncMock(side_effect=ConnectionError))
    monkeypatch.setattr(svo, "analyze_all_citations", AsyncMock(return_value=[]))
    events = [event async for event in svo.SourceVerificationOrchestrator(db).run_pipeline_streaming(check.id)]
    assert events[-1]["status"] == "completed"
    assert check.overall_credibility_score == 100
    assert check.ai_content_percentage is None
    assert check.score_breakdown["assessment_status"] == "partial"
    from app.models.source_check import ClaimAnalysis
    claims = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], ClaimAnalysis)]
    assert [(c.claim_text, c.verdict) for c in claims] == [("known", "true"), ("unknown", "unverified")]
    warnings = {w["type"] for w in check.model_metadata["processing_warnings"]}
    assert {"claim_verification_unavailable", "ai_detection_failed"} <= warnings



@pytest.mark.asyncio
@pytest.mark.parametrize("claims", [[], [{"claim_text": "A claim with no evidence"}]])
async def test_completed_job_without_evidence_persists_unavailable_result(monkeypatch, claims):
    check = SimpleNamespace(
        id="check-id", user_id="user-id", input_type="text",
        input_content="Readable manuscript text. " * 20,
        original_pdf_path=None, input_title=None, status="pending",
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: check)),
        commit=AsyncMock(), add=Mock(),
    )
    monkeypatch.setattr(svo, "extract_claims", AsyncMock(return_value=claims))
    monkeypatch.setattr(svo, "verify_claim", AsyncMock(return_value={
        "verdict": "unverified", "confidence": 0.2,
        "explanation": "Service unavailable", "sources": [],
    }))
    monkeypatch.setattr(svo, "detect_ai_content", AsyncMock(return_value=[]))
    monkeypatch.setattr(svo, "analyze_all_citations", AsyncMock(return_value=[]))
    events = [event async for event in svo.SourceVerificationOrchestrator(db).run_pipeline_streaming(check.id)]
    assert events[-1]["status"] == "completed"  # Execution is terminal; assessment is unavailable.
    assert check.overall_credibility_score is None
    assert check.ai_content_percentage is None
    assert check.misinfo_claims_found is None
    assert check.score_breakdown["final"] is None
    assert check.score_breakdown["confidence"] == 0
    assert check.score_breakdown["formula_version"] == "1.2"
    assert any(w["type"] == "insufficient_verification_evidence" for w in check.model_metadata["processing_warnings"])
    assert check.completed_at is not None
