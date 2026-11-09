# Phase 3: Database & Schema Fixes
## Priority: HIGH — Foundation for everything else

This phase creates proper database migrations, adds missing indexes, converts string fields to ENUMs, adds constraints, and prepares the database for production.

---

## Context

ArtiProof uses PostgreSQL with SQLAlchemy (async) and Alembic for migrations. Currently Alembic is configured but has ZERO migrations — the `alembic/versions/` directory is empty. Schema is only defined in Python ORM models. Database changes are untraceable and unrollbackable.

Key files:
- `backend/app/models/` — SQLAlchemy models
- `backend/alembic/` — migration framework (unused)
- `backend/alembic.ini` — config with hardcoded connection string
- `data-dump.sql`, `data-ordered.sql` — raw SQL dumps used for seeding

---

## Issues To Fix (12 total)

### 1. Create Initial Alembic Migration

The `alembic/versions/` directory is empty. Create the first migration from existing models.

**Steps:**
```bash
cd backend
# Fix alembic.ini to use env var instead of hardcoded string
# Then generate initial migration
alembic revision --autogenerate -m "initial_schema"
```

**Fix `alembic.ini`:**
Replace the hardcoded connection:
```ini
# OLD:
sqlalchemy.url = postgresql://artiproof:artiproof@localhost:5432/artiproof
# NEW:
sqlalchemy.url = postgresql://%(DB_USER)s:%(DB_PASS)s@%(DB_HOST)s:%(DB_PORT)s/%(DB_NAME)s
```

Or better, handle it in `alembic/env.py`:
```python
from app.config import settings

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL_SYNC
    ...
```

---

### 2. Add Missing Database Indexes

These columns are frequently queried but have no indexes:

```python
# In backend/app/models/source_check.py
class SourceCheck(Base):
    __tablename__ = "source_checks"
    
    # Add these indexes:
    status = Column(String, index=True)  # Filtered in list queries
    created_at = Column(DateTime(timezone=True), index=True)  # Ordered/paginated
    
    # Add composite index for common query pattern:
    __table_args__ = (
        Index("ix_source_checks_user_status", "user_id", "status"),
        Index("ix_source_checks_user_created", "user_id", "created_at"),
    )
```

```python
# In backend/app/models/researcher.py
class ResearcherProfile(Base):
    __tablename__ = "researcher_profiles"
    
    analysis_status = Column(String, index=True)
    scrape_status = Column(String, index=True)
    
    __table_args__ = (
        Index("ix_researcher_user_status", "user_id", "analysis_status"),
    )
```

---

### 3. Convert String Status Fields to ENUMs

Currently `status`, `analysis_status`, `scrape_status` accept any string. Convert to PostgreSQL ENUMs.

```python
import enum
from sqlalchemy import Enum as SAEnum

class CheckStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    SCRAPING = "scraping"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"

# In SourceCheck model:
status = Column(SAEnum(CheckStatus), default=CheckStatus.PENDING, index=True)

# In ResearcherProfile model:
analysis_status = Column(SAEnum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
scrape_status = Column(SAEnum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
```

Note: If migrating existing data, create the enum type first, then ALTER the column. The Alembic migration should handle this.

---

### 4. Add Unique Constraints

Prevent duplicate analyses:

```python
# In SourceCheck:
__table_args__ = (
    # A user shouldn't analyze the exact same URL twice within a minute
    # (prevents double-submit race conditions)
    UniqueConstraint("user_id", "input_url", "created_at", name="uq_source_check_unique"),
    ...
)
```

```python
# In users:
email = Column(String, unique=True, nullable=False, index=True)
```

---

### 5. Add Check Constraints

Validate data at the database level:

```python
from sqlalchemy import CheckConstraint

# In SourceCheck:
__table_args__ = (
    CheckConstraint("credibility_score >= 0 AND credibility_score <= 100", name="ck_credibility_range"),
    ...
)

# In ResearcherProfile:
__table_args__ = (
    CheckConstraint("integrity_score >= 0 AND integrity_score <= 100", name="ck_integrity_range"),
    CheckConstraint("adjusted_h_index >= 0", name="ck_adjusted_h_positive"),
    ...
)
```

---

### 6. Add Soft Deletes

Add `deleted_at` column to main tables so records can be restored:

```python
# Add to SourceCheck, ResearcherProfile:
deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)

# Update queries to exclude soft-deleted records:
# WHERE deleted_at IS NULL
```

Update the delete endpoints to set `deleted_at` instead of actually deleting:
```python
@router.delete("/{check_id}")
async def delete_source_check(...):
    check.deleted_at = datetime.now(timezone.utc)
    await db.commit()
```

---

### 7. Add Score Breakdown JSON Schema

Add a structured `score_breakdown` field to store transparent scoring:

```python
# In SourceCheck:
score_breakdown = Column(JSON, nullable=True)
# Expected structure:
# {
#   "base": 100,
#   "deductions": [
#     {"reason": "false_claim", "count": 2, "weight": 15, "impact": -24},
#     {"reason": "retracted_citation", "count": 1, "weight": 15, "impact": -15}
#   ],
#   "final": 55.6,
#   "confidence": 0.72,
#   "formula_version": "1.0"
# }

# In ResearcherProfile:
integrity_breakdown = Column(JSON, nullable=True)
# Expected structure:
# {
#   "base": 100,
#   "adjustments": [
#     {"reason": "self_citation_rate", "value": 0.35, "impact": -15},
#     {"reason": "citation_ring_member", "count": 2, "impact": -20}
#   ],
#   "final": 65,
#   "confidence": 0.68,
#   "formula_version": "1.0"
# }
```

---

### 8. Add Model Governance Fields

Track which model/prompt was used for each analysis:

```python
# In SourceCheck:
model_metadata = Column(JSON, nullable=True)
# Expected structure:
# {
#   "model_provider": "google",
#   "model_name": "gemini-2.0-flash",
#   "prompt_version": "1.0",
#   "apis_used": ["google_fact_check", "crossref", "semantic_scholar"],
#   "processing_warnings": ["text_truncated_at_15000_chars"],
#   "fallback_used": false,
#   "analysis_timestamp": "2026-05-01T12:00:00Z"
# }
```

---

### 9. Fix CASCADE DELETE Risks

Review all CASCADE relationships. For audit purposes, some should be RESTRICT or SET NULL:

```python
# Claims should be preserved even if source check is soft-deleted
# Change from CASCADE to SET NULL for non-critical relationships
# Keep CASCADE for truly dependent data (claim_verifications under claims)
```

---

### 10. Add NOT NULL Constraints Where Missing

Review all nullable columns. Key fields that should NOT be nullable:

```python
# In SourceCheck:
user_id = Column(UUID, ForeignKey("users.id"), nullable=False)  # Was nullable
status = Column(SAEnum(CheckStatus), nullable=False, default=CheckStatus.PENDING)
input_type = Column(String, nullable=False)

# In ResearcherProfile:
user_id = Column(UUID, ForeignKey("users.id"), nullable=False)
```

---

### 11. Add created_at/updated_at to All Tables

Ensure every table has timestamps:

```python
from sqlalchemy import func

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

# Apply to all models:
class SourceCheck(Base, TimestampMixin):
    ...
```

---

### 12. Generate Migration After All Changes

After all model changes:
```bash
cd backend
alembic revision --autogenerate -m "add_indexes_enums_constraints_soft_deletes"
alembic upgrade head
```

---

## Verification

1. `alembic/versions/` contains at least 1 migration file
2. `alembic upgrade head` runs without errors
3. `\d source_checks` in psql shows indexes on status, created_at
4. Enum types exist: `SELECT typname FROM pg_type WHERE typname LIKE '%status%'`
5. Check constraints exist: `SELECT * FROM information_schema.check_constraints WHERE constraint_schema = 'public'`
6. `deleted_at` column exists on SourceCheck and ResearcherProfile
7. `score_breakdown` and `model_metadata` columns exist on SourceCheck
