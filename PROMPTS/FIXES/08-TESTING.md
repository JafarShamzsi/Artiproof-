# Phase 8: Testing
## Priority: HIGH for production — Add test coverage

The ArtiProof project has ZERO test files. This phase creates the test infrastructure and adds tests for the most critical functionality: scoring calculations, detection logic, API endpoints, and frontend components.

---

## Setup

### Backend Test Infrastructure

```bash
cd backend
pip install pytest pytest-asyncio httpx aiosqlite factory-boy --break-system-packages
```

Create `backend/tests/conftest.py`:
```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

Create `backend/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
```

---

## Tests To Write (9 groups)

### 1. Credibility Score Calculation Tests

File: `backend/tests/test_credibility_scoring.py`

```python
"""Test the credibility score calculation logic."""

class TestCredibilityScoring:
    
    def test_perfect_score_no_issues(self):
        """All claims true, no AI, all citations valid → 100."""
        
    def test_false_claims_reduce_score(self):
        """Each false claim deducts from score."""
        
    def test_retracted_citation_reduces_score(self):
        """Retracted citations deduct from score."""
        
    def test_high_ai_content_reduces_score(self):
        """AI probability > 50% reduces score."""
        
    def test_score_never_below_zero(self):
        """Score should be clamped to 0 minimum."""
        
    def test_score_never_above_100(self):
        """Score should be clamped to 100 maximum."""
        
    def test_breakdown_matches_final_score(self):
        """Sum of deductions from base should equal final."""
        
    def test_confidence_decreases_with_truncation(self):
        """Truncated text should lower confidence."""
```

### 2. Integrity Score Calculation Tests

File: `backend/tests/test_integrity_scoring.py`

```python
"""Test the researcher integrity score calculation."""

class TestIntegrityScoring:
    
    def test_clean_researcher_high_score(self):
        """No flags → score near 100."""
        
    def test_high_self_citation_reduces_score(self):
        """Self-citation rate > 25% reduces score."""
        
    def test_citation_ring_member_reduces_score(self):
        """Being in a citation ring reduces score."""
        
    def test_adjusted_h_index_lower_than_official(self):
        """With manipulation, adjusted h-index < official."""
        
    def test_breakdown_tracks_all_adjustments(self):
        """All deductions recorded in breakdown."""
```

### 3. Claim Extraction Tests

File: `backend/tests/test_claim_extractor.py`

```python
"""Test claim extraction JSON parsing and edge cases."""

class TestClaimExtraction:
    
    def test_extracts_claims_from_text(self):
        """Valid text returns list of claims."""
        
    def test_handles_empty_text(self):
        """Empty text returns empty list."""
        
    def test_truncates_long_text(self):
        """Text > 15000 chars is truncated."""
        
    def test_respects_claim_limit(self):
        """Never returns more than 15 claims."""
        
    def test_handles_invalid_json_response(self):
        """Malformed Gemini response returns empty list, not crash."""
        
    def test_handles_missing_api_key(self):
        """No API key returns empty list with warning."""
```

### 4. AI Detection Tests

File: `backend/tests/test_ai_detector.py`

```python
"""Test AI content detection logic."""

class TestAIDetection:
    
    def test_caps_at_20_paragraphs(self):
        """Only first 20 paragraphs analyzed."""
        
    def test_skipped_paragraphs_get_default(self):
        """Paragraphs beyond 20 get 0.5 probability."""
        
    def test_heuristic_fallback_works(self):
        """When Gemini fails, heuristic fallback is used."""
        
    def test_short_paragraphs_skipped(self):
        """Very short paragraphs (< 20 chars) skipped."""
        
    def test_overall_probability_calculated(self):
        """Overall AI probability is average of paragraph probabilities."""
```

### 5. Citation Ring Detection Tests

File: `backend/tests/test_ring_detector.py`

```python
"""Test citation ring detection heuristics."""

class TestRingDetection:
    
    def test_no_ring_in_normal_citations(self):
        """Normal citation patterns don't trigger ring flags."""
        
    def test_detects_mutual_citation_ring(self):
        """Two authors citing each other 5+ times flagged."""
        
    def test_threshold_boundary(self):
        """4 mutual citations = no flag, 5 = flag."""
        
    def test_self_citation_rate_calculation(self):
        """Self-citation rate correctly calculated."""
        
    def test_self_citation_warn_threshold(self):
        """Rate > 15% triggers warning."""
        
    def test_self_citation_flag_threshold(self):
        """Rate > 25% triggers flag."""
        
    def test_citation_velocity_anomaly(self):
        """Papers with > 50 cites/year flagged."""
        
    def test_current_year_is_dynamic(self):
        """Uses current year, not hardcoded 2024."""
```

### 6. Citation Analyzer Tests

File: `backend/tests/test_citation_analyzer.py`

```python
"""Test citation analysis: accessibility, retraction, domain scoring."""

class TestCitationAnalyzer:
    
    def test_accessible_citation_scores_high(self):
        """Accessible citation from reputable domain scores well."""
        
    def test_inaccessible_citation_flagged(self):
        """404/broken links flagged as inaccessible."""
        
    def test_retracted_paper_detected(self):
        """Papers in retraction databases flagged."""
        
    def test_low_credibility_domain_flagged(self):
        """Known low-credibility domains score low."""
        
    def test_domain_extraction_handles_www(self):
        """www. prefix correctly stripped."""
        
    def test_domain_extraction_handles_subdomains(self):
        """Subdomains correctly handled."""
```

### 7. API Endpoint Tests

File: `backend/tests/test_api_endpoints.py`

```python
"""Test API endpoint responses, auth, and validation."""

class TestAuthEndpoints:
    
    async def test_register_creates_user(self, client):
        """POST /api/auth/register with valid data creates user."""
        
    async def test_register_rejects_duplicate_email(self, client):
        """Duplicate email returns 400."""
        
    async def test_login_returns_token(self, client):
        """POST /api/auth/login returns JWT token."""
        
    async def test_login_rejects_wrong_password(self, client):
        """Wrong password returns 401."""
        
    async def test_me_requires_auth(self, client):
        """GET /api/auth/me without token returns 401."""
        
    async def test_me_returns_profile(self, client):
        """GET /api/auth/me with valid token returns user."""
        
    async def test_update_profile_cannot_change_role(self, client):
        """PUT /api/auth/me with role field does NOT change role."""

class TestSourceCheckEndpoints:
    
    async def test_create_check_requires_auth(self, client):
        """POST /api/source-check without auth returns 401."""
        
    async def test_get_check_verifies_ownership(self, client):
        """GET /api/source-check/{id} for another user returns 403."""
        
    async def test_upload_rejects_non_pdf(self, client):
        """Uploading .txt file returns 400."""
        
    async def test_upload_rejects_oversized_file(self, client):
        """50MB+ file returns 400."""

class TestHealthEndpoint:
    
    async def test_health_returns_ok(self, client):
        """GET /health returns 200 with status ok."""
```

### 8. API Response Shape Tests

File: `backend/tests/test_api_shapes.py`

```python
"""Verify API response shapes match frontend expectations."""

class TestResponseShapes:
    
    async def test_source_check_response_shape(self, client):
        """Source check response has all expected fields."""
        response = await client.get("/api/source-check/test-id", headers=auth_headers)
        data = response.json()
        
        assert "id" in data
        assert "status" in data
        assert "credibility_score" in data or data["status"] != "completed"
        assert "claims" in data or data["status"] != "completed"
        
    async def test_researcher_response_shape(self, client):
        """Researcher profile response has all expected fields."""
        
    async def test_pagination_response_shape(self, client):
        """List endpoints return items, total, page, page_size."""
```

### 9. Frontend Component Tests (Optional)

If time permits, add basic React component tests:

```bash
cd frontend
npm install -D @testing-library/react @testing-library/jest-dom vitest jsdom
```

File: `frontend/src/__tests__/scoreExplanation.test.ts`
```typescript
import { explainScore } from "@/lib/scoreExplanation";

describe("explainScore", () => {
  it("returns positive message for high scores", () => {
    const result = explainScore(85);
    expect(result).toContain("high");
  });
  
  it("returns warning for medium scores", () => {
    const result = explainScore(55);
    // verify warning language
  });
  
  it("returns critical message for low scores", () => {
    const result = explainScore(20);
    // verify critical language
  });
});
```

---

## Running Tests

```bash
# Backend
cd backend
python -m pytest tests/ -v --tb=short

# Frontend (if configured)
cd frontend
npx vitest run
```

---

## Verification

1. `pytest tests/` runs without errors
2. All scoring calculation tests pass
3. All claim extraction edge cases pass
4. Ring detection threshold tests pass
5. API endpoint tests verify auth and ownership
6. Response shape tests verify frontend compatibility
