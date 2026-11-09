# CivicGuards — Scopus & Google Scholar Data Scraping Implementation

## IMPORTANT: Read PROMPTS/REBUILD-PROMPT.md first for full project context, database schema, and tech stack.

This prompt implements the data collection layer for **Module 2 (Academic Platform Integrity Analysis)**. The goal is to scrape researcher profiles, publications, citation data, and co-author networks from Google Scholar, Scopus, and supplementary APIs, then store everything in our PostgreSQL database so the integrity analysis pipeline can work with it.

---

## Overview: What Data We Need and Why

For each researcher we analyze, we need to collect:

| Data | Why We Need It | Primary Source | Fallback Source |
|------|---------------|----------------|-----------------|
| Researcher profile (name, institution, fields, h-index, total citations) | Baseline metrics to compare against adjusted scores | Google Scholar | Scopus / Semantic Scholar |
| Full publication list (title, journal, year, DOI, citation count per paper) | Analyze each paper for integrity flags | Google Scholar + Semantic Scholar | Scopus |
| Citation details per paper (WHO cited each paper) | Build citation graph, detect citation rings | Semantic Scholar API | OpenAlex API |
| Co-author list per paper | Detect self-citation networks and mutual boosting | Semantic Scholar API | Google Scholar scrape |
| Paper abstracts | Topic relevance analysis (does abstract match journal scope?) | Semantic Scholar API | CrossRef API |
| Journal/venue info per paper | Check if paper was published in a relevant journal | Semantic Scholar / CrossRef | Scraped from Google Scholar |
| Citing authors' profiles | Trace citation rings — who are the people citing them? | Semantic Scholar API | OpenAlex API |

---

## Database Schema Additions

Add these new models to support the raw scraped data. These sit BELOW the existing `ResearcherProfile` and `PublicationAnalysis` models from REBUILD-PROMPT.md — they store the raw scraped data before analysis runs on top.

### ScrapedPublication (raw publication data)
```python
class ScrapedPublication(Base):
    __tablename__ = "scraped_publications"

    id = Column(UUID, primary_key=True, default=generate_uuid)
    researcher_profile_id = Column(UUID, ForeignKey("researcher_profiles.id"), nullable=False)
    
    # Identifiers
    title = Column(String, nullable=False)
    doi = Column(String, nullable=True)
    semantic_scholar_id = Column(String, nullable=True)  # Semantic Scholar paperId
    google_scholar_cluster_id = Column(String, nullable=True)  # GS citation cluster ID
    scopus_eid = Column(String, nullable=True)
    
    # Metadata
    abstract = Column(Text, nullable=True)
    journal_name = Column(String, nullable=True)
    journal_issn = Column(String, nullable=True)
    venue = Column(String, nullable=True)  # conference name if not journal
    year = Column(Integer, nullable=True)
    publication_type = Column(String, nullable=True)  # journal-article, conference-paper, book-chapter, etc.
    
    # Metrics
    citation_count = Column(Integer, default=0)
    influential_citation_count = Column(Integer, default=0)  # from Semantic Scholar
    reference_count = Column(Integer, default=0)  # papers this paper cites
    
    # Authors
    authors_json = Column(JSON, nullable=True)  
    # Format: [{"name": "John Smith", "authorId": "S2_ID", "position": 0}, ...]
    
    # Source tracking
    data_source = Column(String, nullable=False)  # "google_scholar", "semantic_scholar", "scopus", "crossref"
    raw_data = Column(JSON, nullable=True)  # store the raw API/scrape response for debugging
    
    scraped_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
```

### CitationEdge (who cites whom — the citation graph)
```python
class CitationEdge(Base):
    __tablename__ = "citation_edges"

    id = Column(UUID, primary_key=True, default=generate_uuid)
    researcher_profile_id = Column(UUID, ForeignKey("researcher_profiles.id"), nullable=False)
    
    # The paper being cited (belongs to the researcher we're analyzing)
    cited_paper_id = Column(UUID, ForeignKey("scraped_publications.id"), nullable=False)
    cited_paper_title = Column(String, nullable=False)
    
    # The paper doing the citing
    citing_paper_title = Column(String, nullable=False)
    citing_paper_doi = Column(String, nullable=True)
    citing_paper_semantic_id = Column(String, nullable=True)
    citing_paper_year = Column(Integer, nullable=True)
    
    # The author(s) of the citing paper
    citing_authors_json = Column(JSON, nullable=True)
    # Format: [{"name": "Jane Doe", "authorId": "S2_ID"}, ...]
    
    # Flags (populated later by analysis, but good to have the columns)
    is_self_citation = Column(Boolean, default=False)  # citing author = analyzed researcher
    is_coauthor_citation = Column(Boolean, default=False)  # citing author is a known co-author
    is_ring_suspected = Column(Boolean, default=False)  # part of a detected ring
    
    created_at = Column(DateTime, default=func.now())
```

### CoAuthorRelation (co-author network)
```python
class CoAuthorRelation(Base):
    __tablename__ = "coauthor_relations"

    id = Column(UUID, primary_key=True, default=generate_uuid)
    researcher_profile_id = Column(UUID, ForeignKey("researcher_profiles.id"), nullable=False)
    
    coauthor_name = Column(String, nullable=False)
    coauthor_semantic_id = Column(String, nullable=True)
    coauthor_scopus_id = Column(String, nullable=True)
    coauthor_institution = Column(String, nullable=True)
    
    shared_publication_count = Column(Integer, default=0)  # how many papers together
    shared_publication_ids = Column(JSON, nullable=True)  # list of ScrapedPublication IDs
    
    # These get populated by analysis later
    mutual_citation_count = Column(Integer, default=0)  # how many times they cite each other
    suspicion_score = Column(Float, default=0.0)  # 0 = clean, 1 = highly suspicious
    
    created_at = Column(DateTime, default=func.now())
```

### Add fields to existing ResearcherProfile model
```python
# Add these columns to the ResearcherProfile model from REBUILD-PROMPT.md:
semantic_scholar_id = Column(String, nullable=True)
google_scholar_url = Column(String, nullable=True)
research_fields = Column(JSON, nullable=True)  # ["Computer Science", "Machine Learning", ...]
total_publications = Column(Integer, nullable=True)
i10_index = Column(Integer, nullable=True)  # Google Scholar i10-index
scrape_status = Column(String, default="pending")  # pending, scraping, completed, failed
scrape_error = Column(Text, nullable=True)
last_scraped_at = Column(DateTime, nullable=True)
```

Create an Alembic migration for all new tables and columns.

---

## Service Architecture

Create `backend/app/services/scrapers/` directory with this structure:

```
backend/app/services/scrapers/
├── __init__.py
├── google_scholar.py      # Google Scholar profile & publication scraper
├── semantic_scholar.py    # Semantic Scholar API client (citations, abstracts, author data)
├── scopus_client.py       # Scopus API client (if API key available)
├── crossref_client.py     # CrossRef API for DOI lookups, metadata enrichment
├── openalex_client.py     # OpenAlex API as free fallback for citation data
├── scrape_orchestrator.py # Coordinates all scrapers, deduplicates, stores to DB
└── rate_limiter.py        # Rate limiting utility shared across all scrapers
```

---

## 1. Rate Limiter (`rate_limiter.py`)

Every external source has rate limits. Build a simple async rate limiter that all scrapers share:

```python
import asyncio
from collections import defaultdict
import time

class RateLimiter:
    """Simple token-bucket rate limiter per source."""
    
    def __init__(self):
        self.limits = {
            "google_scholar": {"requests_per_second": 0.2, "burst": 1},   # 1 request per 5 seconds (be gentle, it's scraping)
            "semantic_scholar": {"requests_per_second": 10, "burst": 10},  # 100 req/5min on free tier = ~0.33/s but burst ok
            "scopus": {"requests_per_second": 3, "burst": 5},
            "crossref": {"requests_per_second": 5, "burst": 10},          # polite pool with email header
            "openalex": {"requests_per_second": 10, "burst": 10},         # generous free tier
        }
        self._last_request = defaultdict(float)
        self._locks = defaultdict(asyncio.Lock)

    async def acquire(self, source: str):
        """Wait until we can make a request to this source."""
        async with self._locks[source]:
            limit = self.limits.get(source, {"requests_per_second": 1})
            min_interval = 1.0 / limit["requests_per_second"]
            elapsed = time.monotonic() - self._last_request[source]
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_request[source] = time.monotonic()

rate_limiter = RateLimiter()  # singleton
```

---

## 2. Google Scholar Scraper (`google_scholar.py`)

Google Scholar has NO official API. We have to scrape it. Use `httpx` + `BeautifulSoup`.

### What to scrape

**Researcher profile page** (`https://scholar.google.com/citations?user=SCHOLAR_ID`):
- Name
- Institution/affiliation
- Research interests/fields (the blue tag links)
- h-index (from the stats table on the right)
- i10-index (from the stats table)
- Total citations (from the stats table)
- Profile image URL

**Publication list** (same page, paginated — loads 20 at a time via `cstart` param):
- For each publication row:
  - Title
  - Authors string
  - Journal/venue string
  - Year
  - Citation count
  - Google Scholar citation cluster ID (from the "Cited by X" link — contains `cites=CLUSTER_ID`)

### Implementation

```python
import httpx
from bs4 import BeautifulSoup
from typing import Optional
import re
import asyncio
import random

class GoogleScholarScraper:
    BASE_URL = "https://scholar.google.com"
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        }
    
    async def search_researcher(self, name: str, institution: str = None) -> list[dict]:
        """
        Search Google Scholar for a researcher by name.
        Returns list of matching profiles: [{scholar_id, name, affiliation, interests, cited_by}]
        
        URL: https://scholar.google.com/citations?view_op=search_authors&mauthors=NAME+INSTITUTION
        
        Parse the results page — each result is a div.gsc_1usr containing:
        - Name: h3.gs_ai_name > a (href contains user=SCHOLAR_ID)
        - Affiliation: div.gs_ai_aff
        - Interests: a.gs_ai_one_int (multiple)
        - Cited by: div.gs_ai_cby (text "Cited by XXXX")
        """
        query = name
        if institution:
            query += f" {institution}"
        
        await rate_limiter.acquire("google_scholar")
        
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/citations",
                params={"view_op": "search_authors", "mauthors": query}
            )
            # Check for CAPTCHA — if we get a 429 or the page contains CAPTCHA markers
            if resp.status_code == 429 or "CAPTCHA" in resp.text or "/sorry/" in str(resp.url):
                raise ScraperBlockedError("Google Scholar rate limit / CAPTCHA triggered")
            
            resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        
        for profile_div in soup.select("div.gsc_1usr"):
            # Extract scholar ID from profile link
            name_link = profile_div.select_one("h3.gs_ai_name a")
            if not name_link:
                continue
            href = name_link.get("href", "")
            scholar_id_match = re.search(r"user=([^&]+)", href)
            scholar_id = scholar_id_match.group(1) if scholar_id_match else None
            
            results.append({
                "scholar_id": scholar_id,
                "name": name_link.get_text(strip=True),
                "affiliation": (profile_div.select_one("div.gs_ai_aff") or {}).get_text(strip=True) if profile_div.select_one("div.gs_ai_aff") else None,
                "interests": [a.get_text(strip=True) for a in profile_div.select("a.gs_ai_one_int")],
                "cited_by": self._parse_cited_by(profile_div),
            })
        
        return results

    async def scrape_profile(self, scholar_id: str) -> dict:
        """
        Scrape a researcher's full profile page.
        Returns: {name, affiliation, interests, h_index, i10_index, total_citations, image_url}
        
        Profile URL: https://scholar.google.com/citations?user=SCHOLAR_ID&hl=en
        
        Stats table (id="gsc_rsb_st"):
        - Row 1: Citations → All / Since YYYY
        - Row 2: h-index → All / Since YYYY
        - Row 3: i10-index → All / Since YYYY
        
        We want the "All" column values (second td in each row).
        """
        await rate_limiter.acquire("google_scholar")
        
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/citations",
                params={"user": scholar_id, "hl": "en"}
            )
            if resp.status_code == 429 or "CAPTCHA" in resp.text:
                raise ScraperBlockedError("Google Scholar CAPTCHA")
            resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        profile = {
            "scholar_id": scholar_id,
            "name": self._get_text(soup, "#gsc_prf_in"),
            "affiliation": self._get_text(soup, ".gsc_prf_il"),  # first instance
            "interests": [a.get_text(strip=True) for a in soup.select("#gsc_prf_int a")],
            "image_url": None,
        }
        
        # Parse stats table
        stats_table = soup.select("#gsc_rsb_st tbody tr")
        if len(stats_table) >= 3:
            profile["total_citations"] = self._parse_int(stats_table[0].select("td")[1].get_text())
            profile["h_index"] = self._parse_int(stats_table[1].select("td")[1].get_text())
            profile["i10_index"] = self._parse_int(stats_table[2].select("td")[1].get_text())
        
        return profile

    async def scrape_publications(self, scholar_id: str, max_papers: int = 200) -> list[dict]:
        """
        Scrape all publications from a researcher's Google Scholar profile.
        The page loads 20 papers at a time. We need to paginate using cstart parameter.
        
        URL: https://scholar.google.com/citations?user=SCHOLAR_ID&hl=en&cstart=0&pagesize=100
        
        Each publication row (tr.gsc_a_tr) contains:
        - Title: a.gsc_a_at (also contains link to paper detail page)
        - Authors + venue: div.gs_gray (two of them — first is authors, second is journal/venue + year)
        - Citations: a.gsc_a_ac (text is the count, href contains cites=CLUSTER_ID)
        - Year: span.gsc_a_h.gsc_a_hc.gs_ibl (the year column)
        
        Paginate: increment cstart by pagesize until we get fewer results than pagesize or hit max_papers.
        """
        all_pubs = []
        cstart = 0
        pagesize = 100  # Google Scholar supports pagesize up to 100
        
        while cstart < max_papers:
            await rate_limiter.acquire("google_scholar")
            # Add random delay between 2-5 seconds to avoid detection
            await asyncio.sleep(random.uniform(2, 5))
            
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=30) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/citations",
                    params={
                        "user": scholar_id,
                        "hl": "en",
                        "cstart": cstart,
                        "pagesize": pagesize,
                        "sortby": "pubdate"  # most recent first
                    }
                )
                if resp.status_code == 429 or "CAPTCHA" in resp.text:
                    raise ScraperBlockedError("Google Scholar CAPTCHA")
                resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("tr.gsc_a_tr")
            
            if not rows:
                break
            
            for row in rows:
                title_el = row.select_one("a.gsc_a_at")
                gray_divs = row.select("div.gs_gray")
                cite_el = row.select_one("a.gsc_a_ac")
                year_el = row.select_one("span.gsc_a_h")
                
                # Extract cluster ID from citation link
                cluster_id = None
                if cite_el and cite_el.get("href"):
                    cid_match = re.search(r"cites=(\d+)", cite_el.get("href", ""))
                    cluster_id = cid_match.group(1) if cid_match else None
                
                pub = {
                    "title": title_el.get_text(strip=True) if title_el else None,
                    "authors_string": gray_divs[0].get_text(strip=True) if len(gray_divs) > 0 else None,
                    "venue": gray_divs[1].get_text(strip=True) if len(gray_divs) > 1 else None,
                    "citation_count": self._parse_int(cite_el.get_text()) if cite_el else 0,
                    "year": self._parse_int(year_el.get_text()) if year_el else None,
                    "cluster_id": cluster_id,
                    "detail_url": title_el.get("href") if title_el else None,
                }
                all_pubs.append(pub)
            
            if len(rows) < pagesize:
                break
            cstart += pagesize
        
        return all_pubs

    # Helper methods
    def _get_text(self, soup, selector):
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else None
    
    def _parse_int(self, text):
        if not text:
            return None
        digits = re.sub(r"[^\d]", "", str(text))
        return int(digits) if digits else None
    
    def _parse_cited_by(self, div):
        el = div.select_one("div.gs_ai_cby")
        if not el:
            return 0
        return self._parse_int(el.get_text())


class ScraperBlockedError(Exception):
    """Raised when Google Scholar blocks us with CAPTCHA or rate limit."""
    pass
```

### CAPTCHA Handling Strategy

Google Scholar WILL block us if we scrape too aggressively. Strategy:

1. **Rate limit strictly** — no more than 1 request per 5 seconds to Google Scholar
2. **Random delays** — add 2-5 second random sleep between requests
3. **Rotate User-Agent strings** — maintain a list of 5-10 real browser UAs, pick randomly
4. **Graceful degradation** — if CAPTCHA hits, log the error, mark `scrape_status = "blocked"` on the researcher profile, and fall back to Semantic Scholar API for whatever data we're missing
5. **Don't retry immediately** — if blocked, wait at least 10 minutes before trying Google Scholar again
6. **For the hackathon demo** — if scraping is unreliable, have a "demo mode" flag that loads pre-scraped sample data from a JSON fixture file

---

## 3. Semantic Scholar API Client (`semantic_scholar.py`)

Semantic Scholar is our MOST IMPORTANT data source. It's a free API with good rate limits and gives us citation-level data that Google Scholar doesn't.

### API Endpoints We Need

**Author search:**
`GET https://api.semanticscholar.org/graph/v1/author/search?query=NAME`

**Author profile:**
`GET https://api.semanticscholar.org/graph/v1/author/{authorId}?fields=name,affiliations,homepage,paperCount,citationCount,hIndex`

**Author's papers:**
`GET https://api.semanticscholar.org/graph/v1/author/{authorId}/papers?fields=paperId,title,abstract,venue,year,citationCount,influentialCitationCount,referenceCount,authors,journal,publicationTypes,externalIds&limit=1000`

**Paper's citations (WHO cited this paper):**
`GET https://api.semanticscholar.org/graph/v1/paper/{paperId}/citations?fields=paperId,title,authors,year,venue&limit=1000`

**Paper's references (WHAT this paper cites):**
`GET https://api.semanticscholar.org/graph/v1/paper/{paperId}/references?fields=paperId,title,authors,year&limit=1000`

**Paper detail:**
`GET https://api.semanticscholar.org/graph/v1/paper/{paperId}?fields=paperId,title,abstract,venue,year,citationCount,authors,journal,publicationTypes,externalIds,references,citations`

### Implementation

```python
import httpx
from typing import Optional

class SemanticScholarClient:
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, api_key: str = None):
        """API key is optional — free tier works without it (100 req/5min)."""
        self.headers = {}
        if api_key:
            self.headers["x-api-key"] = api_key  # bumps to 1 req/sec
    
    async def search_author(self, name: str, limit: int = 5) -> list[dict]:
        """Search for an author by name. Returns top matches."""
        await rate_limiter.acquire("semantic_scholar")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/author/search",
                params={"query": name, "limit": limit, "fields": "name,affiliations,paperCount,citationCount,hIndex"},
                headers=self.headers
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
    
    async def get_author(self, author_id: str) -> dict:
        """Get full author profile."""
        await rate_limiter.acquire("semantic_scholar")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/author/{author_id}",
                params={"fields": "name,affiliations,homepage,paperCount,citationCount,hIndex,externalIds"},
                headers=self.headers
            )
            resp.raise_for_status()
            return resp.json()
    
    async def get_author_papers(self, author_id: str, limit: int = 500) -> list[dict]:
        """
        Get all papers by an author with full metadata.
        Paginate using offset parameter — API returns max 1000 per call.
        """
        all_papers = []
        offset = 0
        batch_size = 500  # max allowed per request
        
        while offset < limit:
            await rate_limiter.acquire("semantic_scholar")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/author/{author_id}/papers",
                    params={
                        "fields": "paperId,title,abstract,venue,year,citationCount,influentialCitationCount,referenceCount,authors,journal,publicationTypes,externalIds",
                        "limit": min(batch_size, limit - offset),
                        "offset": offset
                    },
                    headers=self.headers
                )
                resp.raise_for_status()
                data = resp.json().get("data", [])
                
                if not data:
                    break
                all_papers.extend(data)
                
                if len(data) < batch_size:
                    break
                offset += batch_size
        
        return all_papers
    
    async def get_paper_citations(self, paper_id: str, limit: int = 500) -> list[dict]:
        """
        Get all papers that CITE this paper.
        This is the critical data for citation ring detection.
        Each result includes the citing paper's title, authors, year.
        """
        all_citations = []
        offset = 0
        batch_size = 500
        
        while offset < limit:
            await rate_limiter.acquire("semantic_scholar")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/paper/{paper_id}/citations",
                    params={
                        "fields": "paperId,title,authors,year,venue",
                        "limit": min(batch_size, limit - offset),
                        "offset": offset
                    },
                    headers=self.headers
                )
                resp.raise_for_status()
                data = resp.json().get("data", [])
                
                if not data:
                    break
                all_citations.extend(data)
                
                if len(data) < batch_size:
                    break
                offset += batch_size
        
        return all_citations
    
    async def get_paper_references(self, paper_id: str, limit: int = 500) -> list[dict]:
        """Get all papers that this paper REFERENCES (cites)."""
        all_refs = []
        offset = 0
        batch_size = 500
        
        while offset < limit:
            await rate_limiter.acquire("semantic_scholar")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/paper/{paper_id}/references",
                    params={
                        "fields": "paperId,title,authors,year,venue",
                        "limit": min(batch_size, limit - offset),
                        "offset": offset
                    },
                    headers=self.headers
                )
                resp.raise_for_status()
                data = resp.json().get("data", [])
                
                if not data:
                    break
                all_refs.extend(data)
                
                if len(data) < batch_size:
                    break
                offset += batch_size
        
        return all_refs
    
    async def find_author_by_external_id(self, id_type: str, id_value: str) -> Optional[dict]:
        """
        Look up author by external ID.
        Supported: ORCID, DBLP, etc.
        For ORCID: GET /author/ORCID:0000-0001-2345-6789
        """
        prefix_map = {"orcid": "ORCID", "dblp": "DBLP"}
        prefix = prefix_map.get(id_type.lower())
        if not prefix:
            return None
        
        await rate_limiter.acquire("semantic_scholar")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/author/{prefix}:{id_value}",
                params={"fields": "name,affiliations,paperCount,citationCount,hIndex,externalIds"},
                headers=self.headers
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
```

---

## 4. Scopus Client (`scopus_client.py`)

Scopus requires an API key. It's free for academic use through Elsevier Developer Portal. We use it as an enrichment source — if we have a Scopus ID, we can get very clean data.

### API Key Setup

```env
# Add to .env
SCOPUS_API_KEY=your_key_here  # Optional — system works without it
```

### Implementation

```python
import httpx
from typing import Optional
from app.config import settings

class ScopusClient:
    BASE_URL = "https://api.elsevier.com"
    
    def __init__(self):
        self.api_key = settings.SCOPUS_API_KEY  # can be None
        self.headers = {
            "Accept": "application/json",
        }
        if self.api_key:
            self.headers["X-ELS-APIKey"] = self.api_key
    
    @property
    def is_available(self) -> bool:
        return self.api_key is not None
    
    async def search_author(self, name: str, affiliation: str = None) -> list[dict]:
        """Search Scopus for an author. Requires API key."""
        if not self.is_available:
            return []
        
        query = f"AUTHLASTNAME({name.split()[-1]})"
        if len(name.split()) > 1:
            query += f" AND AUTHFIRST({name.split()[0]})"
        if affiliation:
            query += f" AND AFFIL({affiliation})"
        
        await rate_limiter.acquire("scopus")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/content/search/author",
                params={"query": query, "count": 5},
                headers=self.headers
            )
            if resp.status_code == 401:
                return []  # invalid API key, silently fall back
            resp.raise_for_status()
            
            results = resp.json().get("search-results", {}).get("entry", [])
            return [
                {
                    "scopus_id": r.get("dc:identifier", "").replace("AUTHOR_ID:", ""),
                    "name": r.get("preferred-name", {}).get("surname", "") + ", " + r.get("preferred-name", {}).get("given-name", ""),
                    "affiliation": r.get("affiliation-current", {}).get("affiliation-name") if r.get("affiliation-current") else None,
                    "document_count": int(r.get("document-count", 0)),
                    "cited_by_count": int(r.get("cited-by-count", 0)),
                    "h_index": None,  # not in search results, need profile call
                }
                for r in results if r.get("dc:identifier")
            ]
    
    async def get_author_profile(self, scopus_id: str) -> Optional[dict]:
        """Get detailed author profile including h-index."""
        if not self.is_available:
            return None
        
        await rate_limiter.acquire("scopus")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/content/author/author_id/{scopus_id}",
                params={"field": "h-index,document-count,cited-by-count,dc:identifier,affiliation-current,subject-area"},
                headers=self.headers
            )
            if resp.status_code in (401, 404):
                return None
            resp.raise_for_status()
            
            data = resp.json().get("author-retrieval-response", [{}])[0]
            return {
                "scopus_id": scopus_id,
                "h_index": int(data.get("h-index", 0)),
                "document_count": int(data.get("coredata", {}).get("document-count", 0)),
                "cited_by_count": int(data.get("coredata", {}).get("cited-by-count", 0)),
                "subject_areas": [
                    area.get("$", "")
                    for area in data.get("subject-areas", {}).get("subject-area", [])
                ],
            }
    
    async def get_author_publications(self, scopus_id: str, max_results: int = 200) -> list[dict]:
        """Get publications by Scopus author ID."""
        if not self.is_available:
            return []
        
        await rate_limiter.acquire("scopus")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/content/search/scopus",
                params={
                    "query": f"AU-ID({scopus_id})",
                    "count": min(max_results, 200),
                    "field": "dc:title,dc:creator,prism:publicationName,prism:coverDate,prism:doi,citedby-count,eid",
                    "sort": "-citedby-count"
                },
                headers=self.headers
            )
            if resp.status_code in (401, 404):
                return []
            resp.raise_for_status()
            
            entries = resp.json().get("search-results", {}).get("entry", [])
            return [
                {
                    "title": e.get("dc:title"),
                    "journal": e.get("prism:publicationName"),
                    "doi": e.get("prism:doi"),
                    "year": int(e.get("prism:coverDate", "0")[:4]) if e.get("prism:coverDate") else None,
                    "citation_count": int(e.get("citedby-count", 0)),
                    "eid": e.get("eid"),
                }
                for e in entries if e.get("dc:title")
            ]
```

---

## 5. CrossRef Client (`crossref_client.py`)

Free API, no key needed (but include a `mailto` param for the "polite pool" — faster rate limits).

```python
import httpx

class CrossRefClient:
    BASE_URL = "https://api.crossref.org"
    
    def __init__(self, email: str = "civicguards@example.com"):
        self.params = {"mailto": email}  # puts us in the polite pool (faster)
    
    async def lookup_doi(self, doi: str) -> dict | None:
        """Look up paper metadata by DOI. Use this to enrich papers with abstracts, references, etc."""
        await rate_limiter.acquire("crossref")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/works/{doi}",
                params=self.params
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            
            item = resp.json().get("message", {})
            return {
                "doi": doi,
                "title": item.get("title", [None])[0],
                "abstract": item.get("abstract"),  # sometimes available
                "journal": item.get("container-title", [None])[0],
                "issn": item.get("ISSN", [None])[0],
                "year": item.get("published", {}).get("date-parts", [[None]])[0][0],
                "type": item.get("type"),
                "is_retracted": "retracted" in str(item.get("update-to", [])).lower(),
                "reference_count": item.get("references-count", 0),
                "cited_by_count": item.get("is-referenced-by-count", 0),
                "authors": [
                    {"name": f"{a.get('given', '')} {a.get('family', '')}".strip(), "orcid": a.get("ORCID")}
                    for a in item.get("author", [])
                ],
            }
    
    async def check_retraction(self, doi: str) -> bool:
        """Check if a paper with this DOI has been retracted."""
        data = await self.lookup_doi(doi)
        if data is None:
            return False
        return data.get("is_retracted", False)
```

---

## 6. OpenAlex Client (`openalex_client.py`)

Free, open API — good fallback if Semantic Scholar is rate-limited. No API key needed.

```python
import httpx

class OpenAlexClient:
    BASE_URL = "https://api.openalex.org"
    
    def __init__(self, email: str = "civicguards@example.com"):
        self.params = {"mailto": email}  # polite pool
    
    async def search_author(self, name: str) -> list[dict]:
        """Search OpenAlex for an author."""
        await rate_limiter.acquire("openalex")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/authors",
                params={**self.params, "search": name, "per_page": 5}
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return [
                {
                    "openalex_id": r.get("id"),
                    "name": r.get("display_name"),
                    "institution": r.get("last_known_institutions", [{}])[0].get("display_name") if r.get("last_known_institutions") else None,
                    "works_count": r.get("works_count"),
                    "cited_by_count": r.get("cited_by_count"),
                    "h_index": r.get("summary_stats", {}).get("h_index"),
                    "orcid": r.get("orcid"),
                }
                for r in results
            ]
    
    async def get_author_works(self, openalex_author_id: str, limit: int = 200) -> list[dict]:
        """Get an author's publications from OpenAlex."""
        await rate_limiter.acquire("openalex")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/works",
                params={
                    **self.params,
                    "filter": f"authorships.author.id:{openalex_author_id}",
                    "per_page": min(limit, 200),
                    "sort": "cited_by_count:desc"
                }
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
    
    async def get_paper_citations(self, openalex_work_id: str, limit: int = 200) -> list[dict]:
        """Get papers that cite a specific work."""
        await rate_limiter.acquire("openalex")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/works",
                params={
                    **self.params,
                    "filter": f"cites:{openalex_work_id}",
                    "per_page": min(limit, 200),
                }
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
```

---

## 7. Scrape Orchestrator (`scrape_orchestrator.py`)

This is the brain that coordinates all scrapers, merges data, deduplicates, and stores everything in the database.

### Full Scraping Flow

When a user submits a researcher for analysis (via `POST /api/researcher/analyze`):

```
Step 1: RESOLVE THE RESEARCHER
├── User provides: name, OR Scopus ID, OR Google Scholar URL/ID, OR ORCID
├── Search across all available sources to find the researcher
├── Match results across sources (same person on GS + S2 + Scopus)
└── Create/update ResearcherProfile in DB

Step 2: SCRAPE PROFILE DATA
├── Google Scholar → profile stats (h-index, i10, total citations, interests)
├── Semantic Scholar → author profile (affiliations, paper count, h-index)
├── Scopus (if API key) → h-index, subject areas, document count
└── Merge: take the highest-quality data from each source
    Store in ResearcherProfile

Step 3: SCRAPE PUBLICATIONS
├── Semantic Scholar → get ALL papers with metadata (title, abstract, venue, year, citations, authors)
├── Google Scholar → scrape publication list (title, venue, year, citation count, cluster ID)
├── Scopus (if available) → get publications with DOIs and citation counts
├── Deduplicate across sources:
│   ├── Match by DOI (exact match)
│   ├── Match by title (fuzzy — lowercase, strip punctuation, check >85% similarity)
│   └── Prefer Semantic Scholar data (has abstracts + paper IDs for citation lookups)
└── Store in ScrapedPublication table
    SSE event: "scraped_publications" with count

Step 4: SCRAPE CITATION DATA (the expensive part — do this for top N cited papers)
├── For each of the researcher's top 50 most-cited papers:
│   ├── Semantic Scholar → GET /paper/{paperId}/citations
│   │   Returns: list of papers that cite this paper, with their authors
│   ├── For each citing paper, store a CitationEdge record:
│   │   - cited_paper = our researcher's paper
│   │   - citing_paper = the paper doing the citing
│   │   - citing_authors = who wrote the citing paper
│   └── Mark self-citations: if any citing author name matches the researcher's name
├── If Semantic Scholar is rate-limited, fall back to OpenAlex for citation data
└── Store in CitationEdge table
    SSE event: "scraped_citations" with count

Step 5: BUILD CO-AUTHOR NETWORK
├── From ScrapedPublication.authors_json, extract all unique co-authors
├── For each co-author:
│   ├── Count shared publications
│   ├── Record their Semantic Scholar ID (if available)
│   ├── Later (during analysis): count mutual citations
│   └── Store in CoAuthorRelation table
└── SSE event: "built_coauthor_network" with count

Step 6: ENRICH WITH CROSSREF
├── For papers that have DOIs but are missing abstracts:
│   ├── CrossRef → lookup DOI → get abstract, journal ISSN, retraction status
│   └── Update ScrapedPublication with enriched data
├── Check for retractions across all DOIs
└── SSE event: "enrichment_complete"

Step 7: MARK SCRAPING COMPLETE
├── Update ResearcherProfile.scrape_status = "completed"
├── Update ResearcherProfile.last_scraped_at = now()
├── Store total counts (total_publications, etc.)
└── SSE event: "scraping_complete" — ready for integrity analysis
```

### Implementation Skeleton

```python
class ScrapeOrchestrator:
    def __init__(self, db_session, sse_callback=None):
        self.db = db_session
        self.sse = sse_callback  # function to send SSE events
        self.gs = GoogleScholarScraper()
        self.s2 = SemanticScholarClient(api_key=settings.SEMANTIC_SCHOLAR_API_KEY)
        self.scopus = ScopusClient()
        self.crossref = CrossRefClient()
        self.openalex = OpenAlexClient()
    
    async def scrape_researcher(self, profile_id: str, identifier: dict):
        """
        Main entry point. identifier is one of:
        {"name": "John Smith"} or
        {"scholar_id": "abc123"} or
        {"scopus_id": "123456"} or
        {"orcid": "0000-0001-..."} or
        {"scholar_url": "https://scholar.google.com/citations?user=abc123"}
        """
        try:
            # Update status
            await self._update_status(profile_id, "scraping")
            await self._send_event("scraping_started")
            
            # Step 1: Resolve researcher across platforms
            resolved = await self._resolve_researcher(identifier)
            await self._update_profile_ids(profile_id, resolved)
            await self._send_event("researcher_resolved", resolved)
            
            # Step 2: Scrape profile data
            profile_data = await self._scrape_profile(resolved)
            await self._update_profile_data(profile_id, profile_data)
            await self._send_event("profile_scraped", profile_data)
            
            # Step 3: Scrape publications
            publications = await self._scrape_publications(profile_id, resolved)
            await self._send_event("publications_scraped", {"count": len(publications)})
            
            # Step 4: Scrape citation data for top papers
            citation_count = await self._scrape_citations(profile_id, publications)
            await self._send_event("citations_scraped", {"count": citation_count})
            
            # Step 5: Build co-author network
            coauthor_count = await self._build_coauthor_network(profile_id, publications)
            await self._send_event("coauthor_network_built", {"count": coauthor_count})
            
            # Step 6: Enrich with CrossRef
            await self._enrich_with_crossref(profile_id)
            await self._send_event("enrichment_complete")
            
            # Step 7: Mark complete
            await self._update_status(profile_id, "completed")
            await self._send_event("scraping_complete")
            
        except ScraperBlockedError as e:
            await self._update_status(profile_id, "blocked", str(e))
            await self._send_event("scraping_blocked", {"error": str(e)})
        except Exception as e:
            await self._update_status(profile_id, "failed", str(e))
            await self._send_event("scraping_failed", {"error": str(e)})
            raise
    
    async def _resolve_researcher(self, identifier: dict) -> dict:
        """
        Find the researcher across all platforms and return unified IDs.
        Returns: {
            "name": "...",
            "scholar_id": "...",
            "semantic_scholar_id": "...",
            "scopus_id": "...",
            "orcid": "...",
        }
        """
        result = {}
        
        # If we have a Google Scholar URL, extract the ID
        if "scholar_url" in identifier:
            import re
            match = re.search(r"user=([^&]+)", identifier["scholar_url"])
            if match:
                identifier["scholar_id"] = match.group(1)
        
        # If we have a Scholar ID, scrape the name from GS profile
        if "scholar_id" in identifier:
            result["scholar_id"] = identifier["scholar_id"]
            try:
                gs_profile = await self.gs.scrape_profile(identifier["scholar_id"])
                result["name"] = gs_profile.get("name")
            except ScraperBlockedError:
                pass  # will try other sources
        
        # If we have an ORCID, look up via Semantic Scholar
        if "orcid" in identifier:
            result["orcid"] = identifier["orcid"]
            s2_author = await self.s2.find_author_by_external_id("orcid", identifier["orcid"])
            if s2_author:
                result["semantic_scholar_id"] = s2_author.get("authorId")
                result.setdefault("name", s2_author.get("name"))
        
        # If we have a Scopus ID
        if "scopus_id" in identifier:
            result["scopus_id"] = identifier["scopus_id"]
        
        # If we only have a name, search everywhere
        name = identifier.get("name") or result.get("name")
        if name and not result.get("semantic_scholar_id"):
            s2_results = await self.s2.search_author(name)
            if s2_results:
                # Take the top match (highest citation count)
                best = max(s2_results, key=lambda x: x.get("citationCount", 0))
                result["semantic_scholar_id"] = best.get("authorId")
                result.setdefault("name", best.get("name"))
        
        if name and not result.get("scholar_id"):
            try:
                gs_results = await self.gs.search_researcher(name)
                if gs_results:
                    result["scholar_id"] = gs_results[0].get("scholar_id")
                    result.setdefault("name", gs_results[0].get("name"))
            except ScraperBlockedError:
                pass  # GS blocked, continue with other sources
        
        if name and not result.get("scopus_id") and self.scopus.is_available:
            scopus_results = await self.scopus.search_author(name)
            if scopus_results:
                result["scopus_id"] = scopus_results[0].get("scopus_id")
        
        result.setdefault("name", name)
        return result
    
    async def _scrape_publications(self, profile_id: str, resolved: dict) -> list:
        """
        Scrape publications from all sources, deduplicate, store to DB.
        Priority: Semantic Scholar (has paper IDs for citation lookup) > Google Scholar > Scopus
        """
        all_pubs = []
        
        # 1. Semantic Scholar — primary source
        if resolved.get("semantic_scholar_id"):
            s2_papers = await self.s2.get_author_papers(resolved["semantic_scholar_id"])
            for p in s2_papers:
                all_pubs.append({
                    "title": p.get("title"),
                    "doi": (p.get("externalIds") or {}).get("DOI"),
                    "semantic_scholar_id": p.get("paperId"),
                    "abstract": p.get("abstract"),
                    "journal_name": (p.get("journal") or {}).get("name"),
                    "venue": p.get("venue"),
                    "year": p.get("year"),
                    "publication_type": (p.get("publicationTypes") or [None])[0],
                    "citation_count": p.get("citationCount", 0),
                    "influential_citation_count": p.get("influentialCitationCount", 0),
                    "reference_count": p.get("referenceCount", 0),
                    "authors_json": [
                        {"name": a.get("name"), "authorId": a.get("authorId")}
                        for a in (p.get("authors") or [])
                    ],
                    "data_source": "semantic_scholar",
                    "raw_data": p,
                })
        
        # 2. Google Scholar — secondary, fills gaps
        if resolved.get("scholar_id"):
            try:
                gs_papers = await self.gs.scrape_publications(resolved["scholar_id"])
                for gp in gs_papers:
                    # Check if already have this paper from S2 (match by title)
                    if not self._find_duplicate(all_pubs, gp.get("title")):
                        all_pubs.append({
                            "title": gp.get("title"),
                            "google_scholar_cluster_id": gp.get("cluster_id"),
                            "venue": gp.get("venue"),
                            "year": gp.get("year"),
                            "citation_count": gp.get("citation_count", 0),
                            "authors_json": self._parse_authors_string(gp.get("authors_string")),
                            "data_source": "google_scholar",
                            "raw_data": gp,
                        })
                    else:
                        # Merge: add GS cluster ID to existing entry
                        existing = self._find_duplicate(all_pubs, gp.get("title"))
                        if existing:
                            existing["google_scholar_cluster_id"] = gp.get("cluster_id")
                            # GS often has more up-to-date citation counts
                            if gp.get("citation_count", 0) > existing.get("citation_count", 0):
                                existing["citation_count"] = gp["citation_count"]
            except ScraperBlockedError:
                pass  # Continue without GS data
        
        # 3. Scopus — tertiary, adds DOIs and Scopus EIDs
        if resolved.get("scopus_id") and self.scopus.is_available:
            scopus_papers = await self.scopus.get_author_publications(resolved["scopus_id"])
            for sp in scopus_papers:
                existing = self._find_duplicate(all_pubs, sp.get("title"))
                if existing:
                    # Enrich existing record with Scopus data
                    if sp.get("doi") and not existing.get("doi"):
                        existing["doi"] = sp["doi"]
                    existing["scopus_eid"] = sp.get("eid")
                else:
                    all_pubs.append({
                        "title": sp.get("title"),
                        "doi": sp.get("doi"),
                        "scopus_eid": sp.get("eid"),
                        "journal_name": sp.get("journal"),
                        "year": sp.get("year"),
                        "citation_count": sp.get("citation_count", 0),
                        "data_source": "scopus",
                        "raw_data": sp,
                    })
        
        # Store all publications in DB
        for pub_data in all_pubs:
            pub = ScrapedPublication(
                researcher_profile_id=profile_id,
                **{k: v for k, v in pub_data.items() if k != "raw_data"},
                raw_data=pub_data.get("raw_data"),
            )
            self.db.add(pub)
        
        await self.db.commit()
        return all_pubs
    
    async def _scrape_citations(self, profile_id: str, publications: list) -> int:
        """
        For the top 50 most-cited papers, scrape who cited them.
        This data powers citation ring detection.
        
        IMPORTANT: This is the most API-intensive step. 
        50 papers × up to 500 citations each = potentially 25,000 citation edges.
        Rate limit carefully.
        """
        # Sort by citation count, take top 50
        sorted_pubs = sorted(publications, key=lambda p: p.get("citation_count", 0), reverse=True)
        top_papers = sorted_pubs[:50]
        
        total_edges = 0
        
        for i, paper in enumerate(top_papers):
            s2_id = paper.get("semantic_scholar_id")
            if not s2_id:
                continue  # Can only get citation details from Semantic Scholar
            
            await self._send_event("scraping_citations_progress", {
                "current": i + 1,
                "total": len(top_papers),
                "paper_title": paper.get("title", "")[:80]
            })
            
            try:
                citations = await self.s2.get_paper_citations(s2_id, limit=500)
            except Exception:
                continue  # skip this paper if API fails
            
            # Get the DB record for this paper
            db_paper = await self.db.execute(
                select(ScrapedPublication).where(
                    ScrapedPublication.semantic_scholar_id == s2_id,
                    ScrapedPublication.researcher_profile_id == profile_id
                )
            )
            db_paper = db_paper.scalar_one_or_none()
            if not db_paper:
                continue
            
            for cite in citations:
                citing_paper = cite.get("citingPaper", {})
                if not citing_paper or not citing_paper.get("title"):
                    continue
                
                citing_authors = [
                    {"name": a.get("name"), "authorId": a.get("authorId")}
                    for a in (citing_paper.get("authors") or [])
                ]
                
                # Detect self-citation
                researcher_name = paper.get("authors_json", [{}])[0].get("name", "").lower() if paper.get("authors_json") else ""
                is_self = any(
                    self._names_match(a.get("name", ""), researcher_name)
                    for a in citing_authors
                )
                
                edge = CitationEdge(
                    researcher_profile_id=profile_id,
                    cited_paper_id=db_paper.id,
                    cited_paper_title=paper.get("title", ""),
                    citing_paper_title=citing_paper.get("title", ""),
                    citing_paper_doi=None,
                    citing_paper_semantic_id=citing_paper.get("paperId"),
                    citing_paper_year=citing_paper.get("year"),
                    citing_authors_json=citing_authors,
                    is_self_citation=is_self,
                )
                self.db.add(edge)
                total_edges += 1
            
            # Commit in batches to avoid huge transactions
            if total_edges % 500 == 0:
                await self.db.commit()
        
        await self.db.commit()
        return total_edges
    
    async def _build_coauthor_network(self, profile_id: str, publications: list) -> int:
        """
        Extract all co-authors from publications and build the co-author relation table.
        """
        coauthor_map = {}  # name -> {semantic_id, shared_pubs, ...}
        
        # Get the researcher's own name for exclusion
        profile = await self.db.get(ResearcherProfile, profile_id)
        researcher_name = profile.researcher_name.lower() if profile else ""
        
        for pub in publications:
            authors = pub.get("authors_json", []) or []
            for author in authors:
                name = author.get("name", "").strip()
                if not name or self._names_match(name, researcher_name):
                    continue  # skip the researcher themselves
                
                key = name.lower()
                if key not in coauthor_map:
                    coauthor_map[key] = {
                        "name": name,
                        "semantic_id": author.get("authorId"),
                        "shared_pubs": [],
                    }
                coauthor_map[key]["shared_pubs"].append(pub.get("title"))
                # Update semantic ID if we get one
                if author.get("authorId") and not coauthor_map[key]["semantic_id"]:
                    coauthor_map[key]["semantic_id"] = author["authorId"]
        
        # Store in DB
        for key, data in coauthor_map.items():
            relation = CoAuthorRelation(
                researcher_profile_id=profile_id,
                coauthor_name=data["name"],
                coauthor_semantic_id=data.get("semantic_id"),
                shared_publication_count=len(data["shared_pubs"]),
                shared_publication_ids=data["shared_pubs"],  # titles for now, can be IDs later
            )
            self.db.add(relation)
        
        await self.db.commit()
        return len(coauthor_map)
    
    async def _enrich_with_crossref(self, profile_id: str):
        """Enrich publications that have DOIs with CrossRef data (abstracts, retraction status)."""
        result = await self.db.execute(
            select(ScrapedPublication).where(
                ScrapedPublication.researcher_profile_id == profile_id,
                ScrapedPublication.doi.isnot(None),
                ScrapedPublication.abstract.is_(None)  # only enrich if missing abstract
            ).limit(100)  # don't go overboard
        )
        papers = result.scalars().all()
        
        for paper in papers:
            try:
                cr_data = await self.crossref.lookup_doi(paper.doi)
                if cr_data:
                    if cr_data.get("abstract"):
                        paper.abstract = cr_data["abstract"]
                    if cr_data.get("journal") and not paper.journal_name:
                        paper.journal_name = cr_data["journal"]
                    if cr_data.get("issn"):
                        paper.journal_issn = cr_data["issn"]
                    if cr_data.get("is_retracted"):
                        # Flag retracted papers — this is important!
                        paper.raw_data = {**(paper.raw_data or {}), "is_retracted": True}
            except Exception:
                continue  # non-critical, skip
        
        await self.db.commit()
    
    # === Helper Methods ===
    
    def _find_duplicate(self, publications: list, title: str) -> dict | None:
        """Find a publication in the list with a matching title (fuzzy match)."""
        if not title:
            return None
        title_clean = self._normalize_title(title)
        for pub in publications:
            if self._normalize_title(pub.get("title", "")) == title_clean:
                return pub
        return None
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison: lowercase, remove punctuation, collapse whitespace."""
        import re
        title = title.lower().strip()
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title)
        return title
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two author names likely refer to the same person."""
        if not name1 or not name2:
            return False
        # Normalize
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        # Exact match
        if n1 == n2:
            return True
        # Last name match + first initial match
        parts1 = n1.split()
        parts2 = n2.split()
        if len(parts1) >= 2 and len(parts2) >= 2:
            if parts1[-1] == parts2[-1] and parts1[0][0] == parts2[0][0]:
                return True
        return False
    
    def _parse_authors_string(self, authors_str: str) -> list[dict]:
        """Parse a Google Scholar authors string like 'J Smith, A Jones, B Lee' into structured list."""
        if not authors_str:
            return []
        return [{"name": name.strip(), "authorId": None} for name in authors_str.split(",")]
    
    async def _update_status(self, profile_id, status, error=None):
        profile = await self.db.get(ResearcherProfile, profile_id)
        if profile:
            profile.scrape_status = status
            if error:
                profile.scrape_error = error
            if status == "completed":
                profile.last_scraped_at = func.now()
            await self.db.commit()
    
    async def _send_event(self, event_type, data=None):
        if self.sse:
            await self.sse({"event": event_type, "data": data or {}})
```

---

## 8. Celery Task

Create `backend/app/tasks/scraper_tasks.py`:

```python
from celery import shared_task
from app.services.scrapers.scrape_orchestrator import ScrapeOrchestrator

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def scrape_researcher_task(self, profile_id: str, identifier: dict):
    """Background task to scrape researcher data from all sources."""
    import asyncio
    from app.database import async_session_factory
    
    async def run():
        async with async_session_factory() as session:
            orchestrator = ScrapeOrchestrator(session)
            await orchestrator.scrape_researcher(profile_id, identifier)
    
    asyncio.run(run())
```

---

## 9. API Endpoint Updates

Update `backend/app/routers/researcher.py` to wire up the scraper:

```python
@router.post("/analyze")
async def analyze_researcher(
    request: ResearcherAnalyzeRequest,  # contains: name, scholar_id, scholar_url, scopus_id, orcid
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Create ResearcherProfile record
    profile = ResearcherProfile(
        user_id=current_user.id,
        researcher_name=request.name or "Unknown",
        google_scholar_id=request.scholar_id,
        google_scholar_url=request.scholar_url,
        scopus_id=request.scopus_id,
        orcid=request.orcid,
        analysis_status="pending",
        scrape_status="pending",
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    
    # Build identifier dict
    identifier = {}
    if request.name: identifier["name"] = request.name
    if request.scholar_id: identifier["scholar_id"] = request.scholar_id
    if request.scholar_url: identifier["scholar_url"] = request.scholar_url
    if request.scopus_id: identifier["scopus_id"] = request.scopus_id
    if request.orcid: identifier["orcid"] = request.orcid
    
    # Kick off scraping as Celery task
    scrape_researcher_task.delay(str(profile.id), identifier)
    
    return {"id": profile.id, "status": "pending"}
```

---

## 10. Dependencies to Add

Add to `requirements.txt`:
```
networkx>=3.0          # for citation graph analysis (used later in integrity analysis)
```

Add to `.env`:
```env
SEMANTIC_SCHOLAR_API_KEY=    # optional, leave empty for free tier
SCOPUS_API_KEY=              # optional, leave empty if no access
```

---

## 11. Demo/Fallback Data

Create `backend/app/services/scrapers/demo_data.py`:

For the hackathon demo, create a JSON fixture with pre-scraped data for 2-3 real researchers who are known to have clean profiles, and 1-2 fictional profiles with planted citation ring patterns. This way even if external APIs are down or rate-limited during the demo, the system can load and analyze sample data.

```python
DEMO_RESEARCHERS = {
    "demo_clean": {
        "name": "Example Researcher",
        "h_index": 25,
        "publications": [...],  # 20 sample papers
        "citations": [...],     # sample citation edges
        "coauthors": [...],     # sample co-author list
    },
    "demo_suspicious": {
        "name": "Suspicious Author",
        "h_index": 45,  # inflated
        "publications": [...],  # papers with planted anomalies
        "citations": [...],     # citation ring pattern included
        "coauthors": [...],     # small group citing each other heavily
    }
}
```

Include a `--demo` flag on the analyze endpoint:
```python
if request.demo_mode:
    # Load from fixture instead of scraping
    await load_demo_data(profile.id, request.demo_profile)
```

---

## Important Notes

- **Semantic Scholar is the primary source** for citation-level data. Google Scholar gives us profile stats and publication lists, but only Semantic Scholar has the paper-level citation API we need for ring detection.
- **Google Scholar scraping is fragile.** It WILL break with CAPTCHAs. Always have Semantic Scholar + OpenAlex as fallbacks. Never crash the whole pipeline because GS is blocked.
- **Rate limiting is critical.** If we get banned from any API, it affects the whole hackathon. Be conservative. The rate limiter singleton must be used by every single HTTP call.
- **Deduplication matters.** The same paper appears on Google Scholar, Semantic Scholar, and Scopus with slightly different titles and metadata. Always deduplicate by DOI first, then by normalized title.
- **Don't scrape what we don't need.** For citation ring detection, we only need citation data for the top 50 papers (by citation count). Don't try to scrape citations for every single paper — it's too slow and API-intensive.
- **Store raw API responses.** The `raw_data` JSON column exists for debugging. When something looks wrong, we can check what the API actually returned.
- **The scraping step is SEPARATE from the analysis step.** This prompt only covers data collection. The integrity analysis (ring detection, rating adjustment, topic scoring) happens AFTER scraping is complete, using the data stored in the database. That's covered by the main REBUILD-PROMPT.md in the academic integrity pipeline services.
