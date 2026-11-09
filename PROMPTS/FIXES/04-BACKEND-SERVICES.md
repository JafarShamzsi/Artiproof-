# Phase 4: Backend Service Fixes
## Priority: HIGH — Core engine improvements

This phase fixes incomplete implementations, error handling, retry logic, and makes scoring transparent in the ArtiProof backend services.

---

## Context

ArtiProof has two main pipelines:
1. **Source Verification** (`backend/app/services/source_verification/`) — claim extraction, fact-checking, AI detection, citation analysis
2. **Academic Integrity** (`backend/app/services/academic_integrity/`) — researcher profiling, citation ring detection, integrity scoring

Both pipelines currently use Gemini LLM calls with static rule-based scoring. The scores look precise but aren't calibrated, and many features are incomplete (TODOs in code, hardcoded thresholds, missing fallbacks).

---

## Issues To Fix (30 total)

### GROUP A: Transparent Scoring (Issues 1-4)

**1. Store score breakdown in credibility scoring**
File: `backend/app/services/source_verification/orchestrator.py:294`

Currently the credibility score is a manual deduction formula with no record of what was deducted.

**Fix:** Refactor the scoring logic to build a breakdown object:
```python
def calculate_credibility_score(self, claims, ai_result, citations):
    breakdown = {"base": 100, "deductions": [], "warnings": []}
    score = 100.0
    
    # For each false claim
    for claim in claims:
        if claim["verdict"] == "false":
            deduction = 15  # or whatever the weight is
            score -= deduction
            breakdown["deductions"].append({
                "reason": "false_claim",
                "claim": claim["text"][:100],
                "impact": -deduction
            })
    
    # For each retracted citation
    for cit in citations:
        if cit.get("is_retracted"):
            deduction = 15
            score -= deduction
            breakdown["deductions"].append({
                "reason": "retracted_citation",
                "url": cit.get("url", ""),
                "impact": -deduction
            })
    
    # For AI content
    ai_percentage = ai_result.get("overall_ai_probability", 0) * 100
    if ai_percentage > 50:
        deduction = (ai_percentage - 50) * 0.2
        score -= deduction
        breakdown["deductions"].append({
            "reason": "ai_content_detected",
            "percentage": round(ai_percentage, 1),
            "impact": -round(deduction, 1)
        })
    
    final = max(0, min(100, round(score, 1)))
    breakdown["final"] = final
    breakdown["confidence"] = self._calculate_confidence(claims, citations)
    breakdown["formula_version"] = "1.0"
    
    return final, breakdown
```

Save the breakdown to the database alongside the score.

**2. Store integrity breakdown in researcher scoring**
File: `backend/app/services/academic_integrity/rating_adjuster.py:75`

Same pattern — refactor integrity score to produce a breakdown:
```python
def adjust_rating(self, profile, publications, ring_flags):
    breakdown = {"base": 100, "adjustments": [], "warnings": []}
    
    # Self-citation adjustment
    if self_citation_rate > 0.25:
        adjustment = -15
        breakdown["adjustments"].append({
            "reason": "high_self_citation_rate",
            "value": round(self_citation_rate, 3),
            "threshold": 0.25,
            "impact": adjustment
        })
    
    # Citation ring involvement
    if ring_flags.get("is_member"):
        adjustment = -20
        breakdown["adjustments"].append({
            "reason": "citation_ring_member",
            "ring_size": ring_flags.get("ring_size", 0),
            "impact": adjustment
        })
    
    # ... etc for all deduction categories
    
    return final_score, breakdown
```

**3. Add confidence calculation**

Create a method that estimates how confident we are in the score:
```python
def _calculate_confidence(self, claims, citations):
    """Estimate confidence based on coverage and data quality."""
    factors = []
    
    # How many claims were we able to verify?
    verified = sum(1 for c in claims if c["verdict"] != "unknown")
    if claims:
        factors.append(verified / len(claims))
    
    # How many citations were accessible?
    accessible = sum(1 for c in citations if c.get("is_accessible"))
    if citations:
        factors.append(accessible / len(citations))
    
    # Were we working with truncated text?
    if self._text_was_truncated:
        factors.append(0.7)  # Penalty for truncation
    
    return round(sum(factors) / max(len(factors), 1), 2)
```

**4. Store model metadata per analysis**

In the orchestrator, after each analysis completes, save metadata:
```python
model_metadata = {
    "model_provider": "google",
    "model_name": settings.GEMINI_MODEL,
    "apis_used": list(self._apis_used),  # Track during pipeline
    "text_length": len(text),
    "text_truncated": len(text) > 15000,
    "claims_extracted": len(claims),
    "claims_limit": 15,
    "paragraphs_analyzed": len(analyzed_paragraphs),
    "paragraphs_total": len(all_paragraphs),
    "fallback_used": self._fallback_used,
    "processing_warnings": self._warnings,
    "timestamp": datetime.now(timezone.utc).isoformat()
}
check.model_metadata = model_metadata
```

---

### GROUP B: Error Handling & Retry Logic (Issues 5-12)

**5. Replace broad `except Exception:` with specific types**

Throughout the orchestrators, replace:
```python
# BAD:
except Exception as e:
    logger.exception("Error")
    
# GOOD:
except httpx.TimeoutException:
    logger.warning("API timeout, will retry")
    # retry logic
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        logger.warning("Rate limited, backing off")
        # backoff logic
    else:
        logger.error(f"API error: {e.response.status_code}")
except json.JSONDecodeError:
    logger.error("Invalid JSON response from API")
except Exception as e:
    logger.exception(f"Unexpected error: {type(e).__name__}")
```

Apply this pattern in these files:
- `source_verification/orchestrator.py` (lines 96, 112, 128, 149, 162, 175, 185, 241)
- `academic_integrity/orchestrator.py` (lines 96, 115, 141, 152, 162, 174)
- `source_verification/claim_extractor.py`
- `source_verification/fact_checker.py`
- `source_verification/ai_detector.py`
- `source_verification/citation_analyzer.py`

**6. Add retry logic with exponential backoff**

Create a utility decorator:
```python
# backend/app/utils/retry.py
import asyncio
import functools
import logging

logger = logging.getLogger(__name__)

def with_retry(max_retries=3, base_delay=1.0, max_delay=30.0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
                    last_error = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts")
                        raise
            raise last_error
        return wrapper
    return decorator
```

Apply to all external API calls (Gemini, Google Fact Check, CrossRef, Semantic Scholar).

**7. Add circuit breaker for Gemini API**

```python
# backend/app/utils/circuit_breaker.py
class CircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self):
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half-open"
                return True
            return False
        return True  # half-open
    
    def record_success(self):
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
```

**8. Fix silent PDF annotation failure**
File: `source_verification/orchestrator.py:241`

Currently if PDF annotation fails, the pipeline marks as "complete" with no indication.

**Fix:** Add a warning to the response:
```python
try:
    annotated_path = await self.annotate_pdf(...)
except Exception as e:
    logger.exception("PDF annotation failed")
    self._warnings.append("pdf_annotation_failed")
    # Still mark as complete but include warning
    yield {"type": "warning", "message": "PDF annotation could not be generated"}
```

**9. Validate PDF before processing**
File: `source_verification/pdf_processor.py`

```python
async def extract_text(self, pdf_path: str) -> str:
    # Validate PDF
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        raise ValueError("Invalid or corrupted PDF file")
    
    if doc.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported")
    
    if doc.page_count == 0:
        raise ValueError("PDF has no pages")
    
    if doc.page_count > 500:
        raise ValueError("PDF exceeds maximum page limit (500)")
    
    # ... existing extraction logic
```

**10. Add input validation for file uploads**
File: `backend/app/routers/source_check.py`

```python
# Validate file before processing
ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@router.post("/upload")
async def upload_source(file: UploadFile, ...):
    # Check extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Only PDF files are supported. Got: {ext}")
    
    # Check file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Maximum: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    # Validate it's actually a PDF (magic bytes)
    if content[:4] != b'%PDF':
        raise HTTPException(400, "File is not a valid PDF")
    
    await file.seek(0)  # Reset for processing
    ...
```

**11. Add ORCID format validation**
File: `backend/app/routers/researcher.py:72`

```python
import re

ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

if data.orcid and not ORCID_PATTERN.match(data.orcid):
    raise HTTPException(400, "Invalid ORCID format. Expected: 0000-0000-0000-000X")
```

**12. Fix race condition on analysis creation**
File: `backend/app/routers/source_check.py:190`

Add a database-level check to prevent duplicate concurrent analyses:
```python
# Use SELECT FOR UPDATE or an advisory lock
async with db.begin():
    existing = await db.execute(
        select(SourceCheck)
        .where(SourceCheck.id == check_id)
        .with_for_update()
    )
    check = existing.scalar_one_or_none()
    if check.status == "processing":
        raise HTTPException(409, "Analysis already in progress")
    check.status = "processing"
    await db.flush()
```

---

### GROUP C: Incomplete Features (Issues 13-24)

**13. Fix publication self-citation tracking**
File: `academic_integrity/orchestrator.py:194`

`is_self_cited` is always `False`. Fix by checking against the citation graph:
```python
# After building citation graph, check each publication
for pub in publications:
    pub_citations = citation_graph.get(pub["paper_id"], [])
    self_cite_count = sum(
        1 for c in pub_citations 
        if c["citing_author_id"] == researcher.semantic_scholar_id
    )
    is_self_cited = self_cite_count / max(len(pub_citations), 1) > 0.25
    suspicious_count = sum(1 for c in pub_citations if c.get("suspicious"))
```

**14. Fix suspicious_count always 0**
File: `academic_integrity/orchestrator.py:196`

Same fix as above — populate from citation graph data.

**15. Add field-normalized citation ring thresholds**
File: `academic_integrity/ring_detector.py:16`

Replace hardcoded thresholds with field-aware defaults:
```python
FIELD_THRESHOLDS = {
    "computer_science": {"mutual_citation": 8, "self_cite_warn": 0.20, "self_cite_flag": 0.35},
    "medicine": {"mutual_citation": 5, "self_cite_warn": 0.12, "self_cite_flag": 0.20},
    "physics": {"mutual_citation": 6, "self_cite_warn": 0.15, "self_cite_flag": 0.25},
    "default": {"mutual_citation": 5, "self_cite_warn": 0.15, "self_cite_flag": 0.25},
}

def get_thresholds(self, field: str = "default"):
    return self.FIELD_THRESHOLDS.get(field, self.FIELD_THRESHOLDS["default"])
```

**16. Fix hardcoded current year**
File: `academic_integrity/ring_detector.py:112`

```python
# BAD:
current_year = 2024

# GOOD:
from datetime import datetime
current_year = datetime.now().year
```

**17. Implement citation suggested alternatives (TODO)**
File: `source_verification/citation_analyzer.py:169`

The `suggested_alternative` field is always `None` with a TODO comment. Implement it:
```python
async def suggest_alternative(self, original_url: str, claim_text: str) -> Optional[str]:
    """Use Gemini to suggest a better source for the claim."""
    prompt = f"""
    The following citation was found to be problematic: {original_url}
    It was cited to support this claim: {claim_text}
    
    Suggest a more authoritative, accessible, and current source that supports 
    or addresses this claim. Return ONLY a URL, or "none" if no better source exists.
    """
    # Call Gemini and return the suggestion
    ...
```

**18. Increase publication analysis limit**
File: `academic_integrity/citation_graph_builder.py:109`

Currently stops at 20 papers. Increase with pagination:
```python
MAX_PUBLICATIONS = 100  # Analyze more papers
BATCH_SIZE = 20

async def build_graph(self, papers):
    for i in range(0, min(len(papers), MAX_PUBLICATIONS), BATCH_SIZE):
        batch = papers[i:i + BATCH_SIZE]
        await self._process_batch(batch)
```

**19. Improve citation analysis beyond domain-only checks**

Currently `citation_analyzer.py` only checks domain reputation and accessibility. Add:
```python
async def analyze_citation(self, citation, claim_text):
    result = await self._basic_checks(citation)  # existing logic
    
    # NEW: Check if citation is primary, secondary, opinion, preprint
    result["source_type"] = await self._classify_source_type(citation["url"])
    
    # NEW: Check if citation actually supports the claim
    if citation.get("text_context"):
        result["supports_claim"] = await self._check_claim_support(
            citation["text_context"], claim_text
        )
    
    return result
```

**20. Add text truncation warnings**
File: `source_verification/claim_extractor.py:24`

When text is truncated, record it:
```python
if len(text) > 15000:
    text = text[:15000]
    self._warnings.append({
        "type": "text_truncated",
        "original_length": original_length,
        "analyzed_length": 15000,
        "message": f"Only first 15,000 of {original_length} characters analyzed"
    })
```

**21. Add paragraph cap warnings**
File: `source_verification/ai_detector.py:67`

Same pattern — when capping at 20 paragraphs:
```python
if len(paragraphs) > 20:
    self._warnings.append({
        "type": "paragraphs_capped",
        "total": len(paragraphs),
        "analyzed": 20,
        "message": f"Only first 20 of {len(paragraphs)} paragraphs analyzed for AI content"
    })
```

**22. Fix scholar lookup to try all IDs**
File: `academic_integrity/scholar_scraper.py:171-194`

Currently ignores Scopus and Google Scholar IDs even when provided:
```python
async def resolve_researcher(self, name, orcid=None, scopus_id=None, google_scholar_id=None):
    # Try ORCID first
    if orcid:
        result = await self._resolve_by_orcid(orcid)
        if result: return result
    
    # Try Scopus
    if scopus_id and settings.SCOPUS_API_KEY:
        result = await self._resolve_by_scopus(scopus_id)
        if result: return result
    
    # Try Google Scholar
    if google_scholar_id:
        result = await self._resolve_by_google_scholar(google_scholar_id)
        if result: return result
    
    # Fall back to name search
    if name:
        result = await self._resolve_by_name(name)
        if result: return result
    
    return None
```

**23. Parallelize citation analysis**
File: `source_verification/citation_analyzer.py:173-179`

```python
# BAD (sequential):
results = []
for citation in citations:
    result = await self.analyze_citation(citation)
    results.append(result)

# GOOD (parallel):
import asyncio
results = await asyncio.gather(
    *[self.analyze_citation(cit) for cit in citations],
    return_exceptions=True
)
# Filter out exceptions
results = [r for r in results if not isinstance(r, Exception)]
```

**24. Parallelize topic analysis batches**
File: `academic_integrity/topic_analyzer.py:56-96`

Same pattern — use `asyncio.gather()` within batches.

---

### GROUP D: API Improvements (Issues 25-30)

**25. Add bulk delete endpoint**
```python
@router.delete("/bulk")
async def bulk_delete(
    check_ids: list[str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Soft delete all checks owned by user
    ...
```

**26. Add search endpoint**
```python
@router.get("/search")
async def search_checks(
    q: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Search by URL, title, claim text
    ...
```

**27. Fix pagination efficiency**
File: `source_check.py:137-148`

Replace separate count query with window function or LIMIT+1 approach:
```python
# Fetch page_size + 1 to determine if there's a next page
items = await db.execute(
    select(SourceCheck)
    .where(...)
    .order_by(SourceCheck.created_at.desc())
    .offset(offset)
    .limit(page_size + 1)
)
results = items.scalars().all()
has_next = len(results) > page_size
results = results[:page_size]
```

**28. Fix N+1 query for researcher publications**
File: `researcher.py`

```python
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(ResearcherProfile)
    .options(selectinload(ResearcherProfile.publications))
    .where(ResearcherProfile.id == profile_id)
)
```

**29. Add request/response logging middleware**
```python
# backend/app/middleware/logging.py
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} duration={duration:.3f}s"
    )
    return response
```

**30. Add health check that verifies dependencies**
```python
@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    checks = {"status": "ok", "services": {}}
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["services"]["database"] = "ok"
    except Exception:
        checks["services"]["database"] = "error"
        checks["status"] = "degraded"
    
    # Check Redis
    try:
        redis = get_redis()
        await redis.ping()
        checks["services"]["redis"] = "ok"
    except Exception:
        checks["services"]["redis"] = "error"
        checks["status"] = "degraded"
    
    # Check Gemini API key
    checks["services"]["gemini"] = "configured" if settings.GEMINI_API_KEY else "missing"
    
    return checks
```

---

## Verification

1. Source check results include `score_breakdown` JSON
2. Researcher profiles include `integrity_breakdown` JSON
3. All analyses include `model_metadata`
4. `publication_analyses` have correct `is_self_cited_heavily` values (not all False)
5. External API calls retry on failure (check logs for retry messages)
6. Invalid PDFs return proper error messages
7. ORCID validation rejects bad formats
8. Citation analysis runs in parallel (check timing improvement)
