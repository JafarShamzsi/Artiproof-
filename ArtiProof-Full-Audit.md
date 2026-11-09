# ArtiProof — Full Project Audit
### Every gap, flaw, incomplete feature, and issue found

---

## CRITICAL (Fix before demo/pitch)

### 🔴 Security — Exposed Credentials
1. **Google OAuth secret exposed** in `frontend/.env.local` — secret visible in plain text (redacted from this audit; see git history for the rotated value)
2. **Neon database password hardcoded** in 8 shell scripts (`import.sh`, `check.sh`, `cleanup.sh`, etc.) — credentials redacted (rotate the password in Neon)
3. **JWT secret is "change-me-in-production"** — hardcoded default in `backend/app/config.py:28`
4. **Scopus API key exposed** in `.env` file — key redacted (rotate at Elsevier)
5. **Google Client ID hardcoded** in `backend/app/config.py:21` (should be env var only)
6. **Demo password in source code** — `demo1234` bcrypt hash in `backend/app/routers/seed.py:34`

### 🔴 Security — Authorization Missing
7. **No ownership check on source checks** — anyone with a check ID can view it (`backend/app/routers/source_check.py:164`)
8. **No ownership check on researcher profiles** — same issue
9. **Users can escalate to admin** — PUT `/api/auth/me` allows setting own `role` field
10. **Seed endpoint is public** — `/api/seed/demo` has no auth, anyone can reset the database
11. **No rate limiting** anywhere — brute force attacks possible on login

### 🔴 Landing Page — Wrong Information
12. **Pricing shows $19/mo** — should be $20/mo (PricingSection.tsx)
13. **Stats are fake** — "70% encounter misinformation" and "30% self-citation manipulation" have no source (ProblemSection.tsx)
14. **Retractions count wrong** — shows "10K+" should be "14,000+" (verified Retraction Watch 2023)
15. **"Free for researchers" messaging** conflicts with paid model (FeaturesSection.tsx last card)
16. **Free tier marked "Most Popular"** — undermines monetization (PricingSection.tsx)

---

## HIGH PRIORITY (Fix before production)

### Backend — Incomplete Implementations
17. **Citation alternatives not implemented** — TODO at `citation_analyzer.py:169`: `"suggested_alternative": None`
18. **Publication self-citation always False** — `orchestrator.py:194`: `is_self_cited = False` never updated from citation graph
19. **Suspicious count always 0** — `orchestrator.py:196`: `suspicious_count = 0` never populated
20. **Claims truncated silently** — text cut at 15,000 chars, max 15 claims extracted (`claim_extractor.py:24`)
21. **AI detection only checks 20 paragraphs** — rest silently skipped (`ai_detector.py:67`)
22. **Fact-checking uses tiny snippets** — small article snippet passed to verification (`fact_checker.py:123`)
23. **Credibility score is manual formula** — hidden deductions, no breakdown stored (`orchestrator.py:294`)
24. **Integrity score is manual formula** — same issue (`rating_adjuster.py:75`)
25. **Citation ring detection too simple** — fixed threshold of 5+ citations, no field normalization (`ring_detector.py:16`)
26. **Skipped paragraphs get 0.5 AI probability** — arbitrary default, not a real analysis (`ai_detector.py:106-115`)
27. **Scholar lookup incomplete** — only tries ORCID then Semantic Scholar, ignores Scopus/Google Scholar IDs even when provided (`scholar_scraper.py:171-194`)
28. **Citation analysis is domain-only** — doesn't check if citation actually supports the claim
29. **No retraction cross-check** — doesn't check Retraction Watch, PubMed, OpenAlex together
30. **Publication analysis stops at 20 papers** — large research groups have 500+ (`citation_graph_builder.py:109`)

### Backend — Error Handling
31. **Broad `except Exception:` everywhere** — no distinction between network timeout, API quota, invalid input, DB error (20+ occurrences)
32. **No circuit breaker** — if Gemini API is down, every request hangs 30s then fails
33. **No retry logic** — single attempt for all external API calls, no exponential backoff
34. **PDF annotation fails silently** — pipeline marks "complete" even when PDF annotation crashes (`orchestrator.py:241`)
35. **Empty claims not flagged** — if Gemini key missing, returns empty `[]` with no user indication (`claim_extractor.py:51`)
36. **No PDF validation** — corrupted/encrypted PDFs can crash extraction (`pdf_processor.py`)
37. **Race condition on analysis** — concurrent requests can create duplicate analyses (`source_check.py:190`)

### Database — Schema Issues
38. **Zero Alembic migrations** — `alembic/versions/` is empty, schema changes untracked
39. **No unique constraints** beyond primary keys — duplicate checks possible
40. **Status fields are free strings** — should be ENUMs (`status`, `analysis_status`, `scrape_status`)
41. **JSON columns unvalidated** — `citation_ring_flags`, `flags`, `citing_authors_json` have no schema
42. **Missing indexes** on `source_checks.status`, `source_checks.created_at`, `researcher_profiles.analysis_status`
43. **No soft deletes** — hard deletes lose audit trail
44. **No transaction boundaries** — multi-step operations can partially save
45. **CASCADE DELETE risks** — deleting a source check removes all claims, citations, etc. permanently

### Frontend — Type Safety
46. **Excessive `any` types** — `useState<any[]>` in check page, researcher page, check detail page, researcher detail page
47. **No TypeScript interfaces** for API responses — runtime errors likely

### Frontend — Missing States
48. **No 404 page**
49. **No 500 error page**
50. **No network error recovery**
51. **File upload errors not shown in UI** — error state set but never rendered (`check/page.tsx:92`)
52. **No password reset flow**
53. **No email verification flow** — register immediately logs in

### Frontend — Memory Leaks
54. **EventSource streams never closed on unmount** — both check and researcher pages (`check/page.tsx`, `researcher/page.tsx`)

---

## MEDIUM PRIORITY (Should fix)

### Backend — Performance
55. **No caching** — same researcher queried multiple times = redundant API calls
56. **Sequential citation analysis** — should parallelize with `asyncio.gather()` (`citation_analyzer.py:173`)
57. **Sequential batch processing** — topic analyzer processes 15 papers at a time sequentially (`topic_analyzer.py:56`)
58. **No connection pooling config** — using SQLAlchemy defaults
59. **No query timeout** — long-running queries can hang
60. **No Gemini timeout config** — requests take 10-30s, some timeout at default 5s
61. **Uploaded PDFs never cleaned up** — disk fills over time, no storage quota per user

### Backend — API Design
62. **No bulk delete endpoint** — can't delete multiple checks at once
63. **No batch analysis** — can't submit multiple researchers at once
64. **No cancellation** — can't cancel a running analysis
65. **No search endpoint** — can't search past analyses by keyword
66. **Pagination inefficient** — count query separate from data query (`source_check.py:137`)
67. **N+1 query problem** — fetches researcher then separately fetches publications

### Backend — Missing Features
68. **No refresh tokens** — only long-lived (24hr) access tokens
69. **No token revocation** — logged-out users' tokens still valid
70. **No audit logging** — database changes not logged
71. **No feature flags** — can't enable/disable analysis types without code change
72. **No admin panel** — no way to adjust thresholds, view logs, manage users
73. **No GDPR delete** — no "right to be forgotten" implementation
74. **No model governance** — no tracking of model version, prompt version, API versions per analysis

### Frontend — UX Gaps
75. **No "Why this score?" breakdown** — scores show numbers but no deduction details
76. **No confidence interval** — scores look precise but aren't calibrated
77. **No coverage indicator** — user doesn't know "only 20 paragraphs analyzed" or "15 claims extracted"
78. **No AI detection disclaimer** — should warn it's probabilistic, not proof
79. **No evidence trail per claim** — no snippets showing support/contradiction
80. **Notification preferences non-functional** — checkboxes exist but have no onChange handlers, no backend persistence
81. **Settings "Saved!" shows only 2 seconds** — easy to miss
82. **Citation graph "5+ cites" label confusing** — no context for what it means
83. **Publications table capped at 50** — no pagination or virtualization
84. **Google sign-in no loading spinner** — button disables but no visual feedback

### Frontend — Accessibility
85. **Zero ARIA labels** in entire dashboard
86. **No skip-to-content link** on landing page
87. **No focus management** in modals — Sheet components don't trap focus
88. **No `aria-live` regions** for async progress updates
89. **Form labels not properly associated** in some auth forms
90. **No keyboard navigation indicators**

### Frontend — Dependencies
91. **Prisma client in frontend** — `@prisma/adapter-pg` shouldn't be in frontend package.json (security issue)
92. **bcryptjs in frontend** — password hashing should be backend-only
93. **dotenv in frontend** — unnecessary, Next.js handles .env natively
94. **shadcn as runtime dep** — it's a CLI tool, shouldn't be in dependencies
95. **Images unoptimized** — `next.config.ts` has `images: { unoptimized: true }`

### Infrastructure
96. **CORS too permissive** — `allow_methods=["*"]`, `allow_headers=["*"]` with `allow_credentials=True`
97. **Redis unauthenticated** — open on port 6379 with no password
98. **PostgreSQL port exposed** — `5432:5432` mapped to host
99. **No resource limits** in docker-compose — containers can consume all host resources
100. **Container name mismatch** — `run.sh` references `civicguards-*` but docker-compose uses `artiproof-*`
101. **No security headers** — no CSP, X-Frame-Options, X-Content-Type-Options in Next.js config
102. **Dependency versions loose** — `>=` without upper bounds, no lock file
103. **Alembic.ini has hardcoded connection string** — `postgresql://artiproof:artiproof@localhost:5432/artiproof`

---

## LOW PRIORITY (Nice to have)

### Landing Page Polish
104. **15+ dead footer links** — About, Blog, Careers, Press Kit, Contact, Privacy, Terms, Cookie Policy, Security all point to `#`
105. **No social proof section** — no logos, user counts, or testimonials
106. **Unused components** — `EngineGrid.tsx` and `EducationSection.tsx` exist but aren't imported
107. **No team section** on landing page
108. **CTA says "Built by EaP Guardians"** — should mention ArtiProof team

### Code Quality
109. **Zero test files** — no unit tests, integration tests, or E2E tests in entire project
110. **No test database setup** — no fixtures or mock data generators
111. **Magic numbers everywhere** — 15, 20, 50, 200, 5 scattered without constants
112. **Inconsistent error handling** — some try-catch, some `.catch()`, some silent
113. **Mixed naming** — snake_case from API, camelCase in frontend, both used interchangeably
114. **Three different color helper functions** — `scoreColor`, `aiProbColor`, `scoreTextColor` do similar things
115. **No API documentation** — no OpenAPI schema descriptions
116. **No deployment guide** — how to deploy to production undocumented
117. **Docstrings incomplete** — functions lack parameter/return documentation

### Missing Backend Features
118. **No email notifications** — mentioned in UI but not implemented
119. **No weekly digest** — notification checkbox exists, no backend
120. **No export/download endpoint** — reports generated but no CSV/PDF download API
121. **No data retention policy** — analyses stored forever
122. **No backup automation** — no backup/restore tooling

---

## SUMMARY

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Security | 11 | 0 | 0 | 0 | **11** |
| Landing Page | 5 | 0 | 0 | 5 | **10** |
| Backend Services | 0 | 14 | 13 | 0 | **27** |
| Backend Errors | 0 | 7 | 0 | 0 | **7** |
| Database | 0 | 8 | 0 | 0 | **8** |
| API Design | 0 | 0 | 6 | 0 | **6** |
| Frontend Code | 0 | 8 | 10 | 0 | **18** |
| Frontend UX | 0 | 0 | 10 | 0 | **10** |
| Accessibility | 0 | 0 | 6 | 0 | **6** |
| Dependencies | 0 | 0 | 5 | 0 | **5** |
| Infrastructure | 0 | 0 | 8 | 0 | **8** |
| Code Quality | 0 | 0 | 0 | 9 | **9** |
| Missing Features | 0 | 0 | 6 | 5 | **11** |
| **TOTAL** | **16** | **37** | **64** | **19** | **136** |

---

## RECOMMENDED ATTACK ORDER

**For hackathon demo (do first):**
1. Fix pricing ($19 → $20, Institution → Custom)
2. Fix stats with real numbers (14,000+ retractions, sourced data)
3. Fix "free for researchers" messaging
4. Remove exposed credentials from scripts and .env files
5. Fix container name mismatch in run.sh

**For production MVP:**
6. Add authorization checks (ownership verification)
7. Secure seed endpoint
8. Create initial Alembic migration
9. Close EventSource streams on unmount
10. Replace `any` types with proper interfaces
11. Add error boundaries and 404/500 pages
12. Fix CORS configuration
13. Add rate limiting on auth endpoints

**For defensible product:**
14. Score breakdown stored in DB (transparent scoring)
15. Retrieval-grounded fact checking (evidence-backed verification)
16. Field-normalized citation ring detection
17. Fix publication-level self-citation tracking
18. Add test suite (scoring, detection, API endpoints)
19. Model governance (track model version, prompt version per analysis)
20. Proper retry/backoff for all external API calls
