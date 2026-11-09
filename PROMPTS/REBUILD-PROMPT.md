# CivicGuards — Complete Rebuild Prompt for Claude Code

## IMPORTANT: Read this entire prompt before writing any code.

---

## What is CivicGuards?

CivicGuards is a **Research Integrity Platform** — a web application that helps academic researchers, universities, and research institutions verify the integrity of their sources and get honest assessments of academic researcher ratings.

**Team:** EAP Guardians (Azerbaijan) — Javad Huseynli (Team Lead), Kamilli Murad (Backend), Rasim Abdullayev (Product Manager), Jafar Shamsiyev (Full-Stack Developer)

**Context:** This is an EaP hackathon project (€10-12K budget, 6 months timeline). We need a working MVP, not a production-ready enterprise system. Keep things lean, functional, and demo-ready.

---

## The Two Core Modules

### Module 1: Source Verification & Fact-Checking

A researcher pastes an article URL, text, or uploads a document. The platform:

1. **Checks for misinformation/disinformation** — cross-references claims against fact-check databases (Google Fact Check API, ClaimBuster, etc.), verified sources, and AI analysis (Gemini API)
2. **Detects AI-generated content** — identifies which sections or entire articles are machine-written, with per-paragraph confidence scores (use Gemini or a dedicated AI detection approach)
3. **Shows the true version** — when misinformation is found, surfaces the correct, verified version from trusted sources
4. **Traces misinformation origins** — maps where false claims originated, how they spread, and which platforms amplified them
5. **Improves citation quality** — suggests more reliable alternative sources and flags citations that link to unreliable or retracted content (check against Retraction Watch database, CrossRef API)

### Module 2: Academic Platform Integrity Analysis

The platform analyzes academic rating platforms (Scopus, Web of Science, Google Scholar) to expose integrity issues:

1. **Citation ring detection** — identifies groups of researchers who systematically inflate each other's citation counts through mutual referencing. Analyze citation graphs for suspicious clustering patterns
2. **Topic relevance scoring** — flags papers published in journals/categories unrelated to their actual content. Compare paper abstract/keywords against journal scope using NLP similarity
3. **Honest researcher ratings** — provides adjusted credibility scores that account for citation manipulation, giving a more accurate picture of a researcher's real impact. Recalculate h-index after removing suspicious citations
4. **Fake metric exposure** — highlights when h-index, citation counts, or impact factors have been artificially inflated. Compare self-citation rates, citation velocity anomalies, etc.

---

## Tech Stack (KEEP the same stack, rebuild the logic)

### Frontend (already set up — reuse the framework)
- **Next.js 16** with TypeScript
- **Tailwind CSS** + **shadcn/ui** components
- **Framer Motion** for animations
- **TanStack React Query** for data fetching
- **next-auth** for authentication
- Keep the existing `package.json` dependencies — don't remove anything, just add if needed

### Backend (already set up — rebuild the app logic)
- **Python FastAPI** with async support
- **SQLAlchemy** (async) + **PostgreSQL** + **Alembic** for migrations
- **Celery + Redis** for background task processing
- **Gemini API** (google-generativeai) as the primary AI engine
- **WeasyPrint** for PDF report generation
- **SSE (sse-starlette)** for real-time scan progress updates
- **httpx** for external API calls
- **BeautifulSoup** for web scraping

### Infrastructure
- **Docker Compose** for local dev (PostgreSQL, Redis, backend, frontend, Celery worker)
- Keep the existing `docker-compose.yml` structure, update services as needed

---

## Database Schema (Replace the old security scanner schema)

Delete ALL existing models and create these new ones:

### User (keep/update existing)
```
- id: UUID (primary key)
- email: String (unique)
- hashed_password: String
- full_name: String
- institution: String (nullable) — university/org name
- role: Enum (researcher, faculty, admin)
- created_at: DateTime
- updated_at: DateTime
```

### SourceCheck (NEW — Module 1 core)
```
- id: UUID (primary key)
- user_id: UUID (FK → User)
- input_type: Enum (url, text, document)
- input_content: Text — the URL or pasted text
- input_title: String (nullable) — extracted article title
- status: Enum (pending, processing, completed, failed)
- overall_credibility_score: Float (0-100)
- ai_content_percentage: Float (0-100) — how much is AI-generated
- misinfo_claims_found: Integer — count of misinformation claims detected
- created_at: DateTime
- completed_at: DateTime (nullable)
```

### ClaimAnalysis (NEW — individual claims within a source check)
```
- id: UUID (primary key)
- source_check_id: UUID (FK → SourceCheck)
- claim_text: Text — the specific claim being analyzed
- verdict: Enum (true, false, misleading, unverified, partially_true)
- confidence: Float (0-1)
- explanation: Text — why this verdict
- true_version: Text (nullable) — the correct information
- sources: JSON — list of fact-check sources that verify/debunk
- origin_trace: JSON (nullable) — origin platform, spread path
- position_in_text: JSON — start/end character positions in original
- created_at: DateTime
```

### AIDetectionResult (NEW — AI content detection per paragraph)
```
- id: UUID (primary key)
- source_check_id: UUID (FK → SourceCheck)
- paragraph_index: Integer
- paragraph_text: Text
- ai_probability: Float (0-1) — likelihood of being AI-generated
- detection_method: String — which model/method detected it
- created_at: DateTime
```

### CitationCheck (NEW — citation quality analysis)
```
- id: UUID (primary key)
- source_check_id: UUID (FK → SourceCheck)
- original_citation: Text — the citation as it appears
- citation_url: String (nullable)
- is_accessible: Boolean — can we reach this source
- is_retracted: Boolean — is this a retracted paper
- credibility_score: Float (0-100)
- issues: JSON — list of issues found
- suggested_alternative: Text (nullable) — better source suggestion
- created_at: DateTime
```

### ResearcherProfile (NEW — Module 2 core)
```
- id: UUID (primary key)
- user_id: UUID (FK → User, nullable) — who requested the analysis
- researcher_name: String
- scopus_id: String (nullable)
- google_scholar_id: String (nullable)
- orcid: String (nullable)
- institution: String (nullable)
- official_h_index: Integer (nullable)
- official_citation_count: Integer (nullable)
- adjusted_h_index: Integer (nullable) — our corrected h-index
- adjusted_citation_count: Integer (nullable)
- integrity_score: Float (0-100) — overall integrity rating
- self_citation_rate: Float (nullable) — percentage of self-citations
- citation_ring_flags: JSON (nullable) — detected ring patterns
- topic_relevance_score: Float (nullable) — how well papers match declared fields
- analysis_status: Enum (pending, processing, completed, failed)
- last_analyzed_at: DateTime (nullable)
- created_at: DateTime
```

### PublicationAnalysis (NEW — individual paper analysis for Module 2)
```
- id: UUID (primary key)
- researcher_profile_id: UUID (FK → ResearcherProfile)
- title: String
- journal: String (nullable)
- year: Integer (nullable)
- doi: String (nullable)
- citation_count: Integer
- suspicious_citations: Integer — citations flagged as potentially manipulated
- topic_match_score: Float (0-1) — relevance to journal/field
- is_self_cited_heavily: Boolean
- flags: JSON — list of integrity flags
- created_at: DateTime
```

### Report (keep concept, update for new modules)
```
- id: UUID (primary key)
- user_id: UUID (FK → User)
- source_check_id: UUID (FK → SourceCheck, nullable)
- researcher_profile_id: UUID (FK → ResearcherProfile, nullable)
- report_type: Enum (source_verification, researcher_integrity)
- title: String
- summary: Text — AI-generated narrative summary
- pdf_path: String (nullable) — path to generated PDF
- share_token: String (unique) — for public sharing
- created_at: DateTime
```

---

## Backend API Endpoints

### Auth Routes (`/api/auth/`)
- `POST /register` — create account (email, password, name, institution, role)
- `POST /login` — return JWT token
- `GET /me` — current user profile
- `PUT /me` — update profile

### Source Verification Routes (`/api/source-check/`)
- `POST /` — submit a new source check (URL, text, or document upload)
- `GET /` — list user's past source checks (paginated)
- `GET /{id}` — get full source check results with claims, AI detection, citations
- `GET /{id}/stream` — SSE endpoint for real-time progress during processing
- `DELETE /{id}` — delete a source check

### Researcher Analysis Routes (`/api/researcher/`)
- `POST /analyze` — submit a researcher for analysis (by name, Scopus ID, Google Scholar ID, or ORCID)
- `GET /` — list user's past researcher analyses (paginated)
- `GET /{id}` — get full researcher profile with publications and integrity analysis
- `GET /{id}/stream` — SSE endpoint for real-time progress
- `GET /{id}/publications` — paginated list of analyzed publications
- `GET /{id}/citation-graph` — citation network data for visualization

### Reports Routes (`/api/reports/`)
- `POST /generate` — generate PDF report for a source check or researcher analysis
- `GET /` — list user's reports
- `GET /{id}` — get report details
- `GET /shared/{share_token}` — public report access (no auth required)
- `GET /{id}/download` — download PDF

### Dashboard Routes (`/api/dashboard/`)
- `GET /stats` — user's overall stats (total checks, avg credibility, etc.)
- `GET /recent-activity` — recent source checks and researcher analyses
- `GET /trends` — credibility trends over time

---

## Backend Services Architecture

### Module 1: Source Verification Pipeline

Create `backend/app/services/source_verification/` with:

1. **`scraper.py`** — Extract article text from URLs using httpx + BeautifulSoup. Handle paywalls gracefully (return what's available). Extract title, body text, author, publication date, and embedded citations/links.

2. **`claim_extractor.py`** — Use Gemini API to break an article into individual factual claims. Each claim should be a specific, verifiable statement. Prompt Gemini to return structured JSON with claim text and position in original.

3. **`fact_checker.py`** — For each extracted claim:
   - Query Google Fact Check Tools API (`https://toolbox.google.com/factcheck/api`)
   - Use Gemini API for AI-powered fact analysis with web grounding
   - Cross-reference with known fact-check databases
   - Return verdict (true/false/misleading/unverified/partially_true), confidence score, explanation, and the true version if misinformation is found

4. **`ai_detector.py`** — Split text into paragraphs, analyze each for AI-generated probability. Use Gemini to analyze writing patterns, or integrate with a detection API. Return per-paragraph scores.

5. **`citation_analyzer.py`** — Extract all citations/references from the text:
   - Check if URLs are accessible (httpx HEAD requests)
   - Check against Retraction Watch database or CrossRef API for retracted papers
   - Score citation credibility
   - Suggest alternatives using Gemini

6. **`origin_tracer.py`** — For claims identified as misinformation:
   - Use Gemini with web grounding to trace the earliest known instance
   - Map the spread across platforms
   - Return origin platform, timeline, and amplification path

7. **`orchestrator.py`** — Coordinates the full pipeline:
   - Accepts input (URL/text/document)
   - Runs scraper if URL
   - Runs all analysis engines in parallel using `asyncio.gather()`
   - Updates SourceCheck status via SSE events as each step completes
   - Saves all results to database
   - Returns completed SourceCheck with all related data

### Module 2: Academic Integrity Pipeline

Create `backend/app/services/academic_integrity/` with:

1. **`scholar_scraper.py`** — Fetch researcher data from:
   - Google Scholar (scrape profile page — publications list, citation counts, h-index)
   - Scopus API (if API key available, otherwise scrape)
   - Semantic Scholar API (free, good coverage — `api.semanticscholar.org`)
   - Extract: name, affiliation, publication list with citation counts, co-authors

2. **`citation_graph_builder.py`** — Build a citation graph for the researcher:
   - Who cites them, who they cite
   - Identify clusters of mutual citation (potential rings)
   - Use network analysis (can use networkx library — add to requirements.txt)
   - Flag citation pairs with suspiciously high mutual citation counts

3. **`ring_detector.py`** — Analyze citation graph for manipulation:
   - Detect citation rings (groups of 3+ researchers with circular citation patterns)
   - Calculate self-citation rate
   - Identify "citation farms" — papers with abnormally high citation velocity
   - Flag papers cited mostly by the same small group

4. **`topic_analyzer.py`** — Check topic relevance:
   - Use Gemini to analyze each paper's abstract vs. the journal's scope
   - Flag papers published in journals clearly unrelated to their content
   - Score topic-to-journal match (0-1)

5. **`rating_adjuster.py`** — Calculate adjusted metrics:
   - Remove suspicious citations (from detected rings, self-citations above threshold)
   - Recalculate h-index with cleaned data
   - Produce an integrity score (0-100) based on all factors
   - Generate narrative explanation of adjustments

6. **`orchestrator.py`** — Coordinates the Module 2 pipeline:
   - Accepts researcher identifier (name, Scopus ID, Scholar ID, ORCID)
   - Fetches profile data
   - Runs all analysis in sequence (graph needs to be built before ring detection)
   - Updates ResearcherProfile via SSE as each step completes
   - Saves all results

### Celery Tasks

Create `backend/app/tasks/` with:

1. **`source_check_tasks.py`** — Celery task that runs the Module 1 orchestrator
2. **`researcher_tasks.py`** — Celery task that runs the Module 2 orchestrator
3. **`report_tasks.py`** — Celery task that generates PDF reports

### Report Engine

Update `backend/app/services/report_engine/` with:

1. **`narrative_generator.py`** — Use Gemini to write a human-readable summary of findings (both for source checks and researcher analyses)
2. **`pdf_generator.py`** — Generate professional PDF reports using WeasyPrint with HTML templates
3. **`html_template.py`** — HTML/CSS templates for both report types

---

## Frontend Pages (Delete old pages, create new ones)

### Brand / Design
- **Primary color:** Emerald (#10B981)
- **Dark background:** #0F172A
- **Card backgrounds:** #1E293B
- **Gray text:** #64748B
- **Keep the dark theme** from the existing landing page
- Use shadcn/ui components consistently
- Framer Motion for page transitions and micro-animations

### Landing Page (`/`) — Keep existing structure but update content
- Hero section: "Research Integrity Platform" — tagline about protecting academic research
- Two feature sections: Source Verification + Academic Integrity Analysis
- How it works (3 steps)
- Who it's for (researchers, faculty, PhD students, institutions)
- CTA to register
- Footer with team info and links

### Auth Pages
- `/login` — email + password login (keep existing, just clean up)
- `/register` — registration with institution and role fields

### Dashboard (`/dashboard`)
- Overview cards: Total source checks, Average credibility score, Total researcher analyses, Recent alerts
- Recent activity feed (last 5 source checks and researcher analyses)
- Quick action buttons: "Check a Source" and "Analyze a Researcher"
- Trends chart (credibility scores over time using recharts or similar)

### Source Check Pages
- `/check` — The main source check input page:
  - Tab interface: "Paste URL" | "Paste Text" | "Upload Document"
  - Large input area
  - "Analyze" button
  - Below: list of past checks with status, date, credibility score
  
- `/check/[id]` — Full results page:
  - Overall credibility score (big circular gauge)
  - AI content percentage bar
  - Claims analysis section — expandable list of each claim with verdict badges (true=green, false=red, misleading=yellow, etc.), explanation, and true version
  - AI Detection section — original text with paragraphs highlighted by AI probability (gradient from green=human to red=AI)
  - Citations section — list of citations with health status icons
  - Origin trace section — visual timeline/map of misinformation spread (if applicable)
  - "Generate Report" button
  - "Share Results" button (generates shareable link)

### Researcher Analysis Pages
- `/researcher` — The researcher analysis input page:
  - Search by name, Scopus ID, Google Scholar URL, or ORCID
  - "Analyze" button
  - Below: list of past analyses
  
- `/researcher/[id]` — Full results page:
  - Researcher profile card (name, institution, fields)
  - Side-by-side comparison: Official metrics vs. Adjusted metrics (h-index, citation count)
  - Integrity score gauge (0-100)
  - Citation ring visualization — network graph (use d3.js or react-force-graph) showing citation connections, with suspicious clusters highlighted in red
  - Publications table — sortable, with columns: title, journal, year, citations, suspicious citations, topic match score, flags
  - Self-citation analysis chart
  - "Generate Report" button

### Reports Page
- `/reports` — List of all generated reports with download links

### Settings Page
- `/settings` — Profile settings, notification preferences

### Shared Report Page (public, no auth)
- `/report/[shareToken]` — Read-only view of a shared report

---

## Frontend Layout

### Dashboard Sidebar Navigation
```
📊 Dashboard
🔍 Check Source        (Module 1)
👤 Analyze Researcher  (Module 2)
📄 Reports
⚙️ Settings
```

---

## Implementation Order

Build in this exact sequence:

### Phase 1: Foundation (Do this first)
1. Clean out ALL old models, routers, schemas, services (security scanner, misinfo, community, education — ALL of it)
2. Create new database models as specified above
3. Create Alembic migration
4. Set up new routers with basic CRUD (empty service calls are fine)
5. Update frontend: remove old pages, create new route structure with placeholder pages
6. Update landing page content for Research Integrity Platform
7. Update sidebar navigation
8. Make sure docker-compose still works, app starts without errors

### Phase 2: Module 1 — Source Verification
1. Build the scraper service
2. Build claim extractor (Gemini API)
3. Build fact checker (Google Fact Check API + Gemini)
4. Build AI content detector
5. Build citation analyzer
6. Build origin tracer
7. Build the orchestrator that ties them all together
8. Wire up Celery task
9. Wire up SSE streaming endpoint
10. Build the frontend check page (input form + results display)

### Phase 3: Module 2 — Academic Integrity
1. Build scholar scraper (Google Scholar + Semantic Scholar API)
2. Build citation graph builder (add networkx to requirements)
3. Build ring detector
4. Build topic analyzer
5. Build rating adjuster
6. Build the orchestrator
7. Wire up Celery task + SSE
8. Build the frontend researcher analysis page (input + results + citation graph visualization)

### Phase 4: Reports & Dashboard
1. Build report narrative generator (Gemini)
2. Build PDF generator (WeasyPrint HTML templates)
3. Build the reports API endpoints
4. Build the dashboard API with stats aggregation
5. Build frontend dashboard page with charts
6. Build frontend reports page
7. Build shared report public page

### Phase 5: Polish
1. Landing page final design with animations
2. Error handling and loading states everywhere
3. Mobile responsive check
4. Demo data seeder for hackathon presentation

---

## External APIs to Integrate

1. **Gemini API** (google-generativeai) — primary AI for claim extraction, fact analysis, AI detection, topic analysis, narrative generation. Use `gemini-2.0-flash` for speed, `gemini-2.5-pro` for complex analysis.
2. **Google Fact Check Tools API** — `https://factchecktools.googleapis.com/v1alpha1/claims:search` — free, returns fact-checks from verified publishers
3. **Semantic Scholar API** — `https://api.semanticscholar.org/graph/v1/` — free tier, no API key needed for basic access. Get author profiles, papers, citations
4. **CrossRef API** — `https://api.crossref.org/` — free, check DOIs, get paper metadata, check for retractions
5. **ORCID API** — `https://pub.orcid.org/v3.0/` — free public API for researcher lookup

---

## Environment Variables Needed

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/civicguards

# Redis
REDIS_URL=redis://localhost:6379/0

# AI
GEMINI_API_KEY=your_key_here

# Google Fact Check
GOOGLE_FACTCHECK_API_KEY=your_key_here

# Auth
JWT_SECRET=your_secret
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# App
APP_URL=http://localhost:3000
API_URL=http://localhost:8000
```

---

## Key Reminders

- **This is a COMPLETE REBUILD.** Delete all old service logic (security scanner, DISARM, community, education, courses, threat intel). Keep the framework/infrastructure (FastAPI app, Next.js app, Docker setup, auth system) but replace all domain-specific code.
- **Keep it lean.** This is a hackathon MVP. Don't over-engineer. If a service can't reach an external API, return mock/simulated data gracefully rather than crashing.
- **Gemini is the backbone.** Use it for claim extraction, fact analysis, AI detection, topic analysis, and report narratives. It's the most flexible tool we have.
- **SSE for real-time updates.** Both Module 1 and Module 2 pipelines should stream progress events so the frontend can show step-by-step progress.
- **The citation graph visualization is the demo wow-factor for Module 2.** Make it look good — use a force-directed graph with suspicious connections highlighted in red.
- **Don't touch:** team photos, the .docx brief files, the pitch deck .pptx, or the PROMPTS folder.
