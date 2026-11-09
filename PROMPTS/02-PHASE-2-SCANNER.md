# Phase 2 — Security Scanner Core (Website Vulnerability Assessment)

## Context
Read `00-PROJECT-BRIEF.md` for full context. Phase 1 (foundation, auth, landing page, dashboard shell) is updated for the pivot. Now we build the **core product**: the website security vulnerability scanner. This is the MLP — the ONE feature that needs to work perfectly for the hackathon demo.

**THIS IS THE MOST IMPORTANT PHASE.** The hackathon demo (1–1.5 min recorded) will showcase this feature. A civil society org pastes their website URL → CivicGuards runs automated security checks → delivers a clear, actionable report.

## Objective
Build a complete security scanning pipeline: user submits a URL → multiple security checks run in parallel → results are aggregated into an overall security score → a detailed report is displayed with plain-language recommendations.

---

## Task 1: Scan Submission Interface

**Location**: `/dashboard/scan` page

### Input:
- Large, prominent URL input field
- Placeholder: "Enter your organization's website URL (e.g., https://yourorg.az)"
- URL validation (must be a valid URL, ideally with protocol)
- "Scan Now" button (large, gradient, prominent)
- Below input: "What we check:" with icons — SSL/TLS, Security Headers, CMS Version, Open Ports, DNS Configuration, Common Vulnerabilities

### Submission Flow:
1. User enters URL and clicks "Scan Now"
2. Show animated scanning progress — "Running security checks..." with each check type lighting up as it completes
3. Check categories appear one by one with status indicators (spinner → green check/red X)
4. When all checks complete, show "Scan Complete" with overall score preview
5. Auto-navigate to results page: `/dashboard/scan/[scanId]`

### Quick Examples:
- For first-time users or demo: "Try scanning our test site" button that scans a pre-configured demo URL
- Show estimated scan time: "Typical scan takes 30–60 seconds"

---

## Task 2: Python Backend — Security Scan Orchestrator

### API Endpoints (FastAPI):

```
POST /api/v1/security-scans              — Create a new security scan
GET  /api/v1/security-scans/{scan_id}    — Get scan status and results
GET  /api/v1/security-scans              — List org's scan history (paginated)
```

### Scan Orchestrator (`services/scanner/orchestrator.py`):

When a scan is created:

1. **Validate & preprocess URL**:
   - Normalize URL (add https:// if missing, strip trailing slashes)
   - Resolve DNS to verify the domain exists
   - Check that the URL is reachable (HEAD request)
   - Extract domain, subdomain info

2. **Run all security checks in parallel** using asyncio.gather():
   - SSL/TLS Check
   - Security Headers Check
   - CMS Detection & Version Check
   - Port Scan (common web ports)
   - DNS Configuration Check
   - Common Vulnerability Check (XSS, SQLi indicators)
   - Server Information Leak Check
   - Cookie Security Check

3. **Aggregate results**:
   - Calculate overall security score (0–100, higher = safer)
   - Score formula: start at 100, deduct points per finding based on severity
     - Critical: -20 points each
     - High: -10 points each
     - Medium: -5 points each
     - Low: -2 points each
     - Info: 0 points (informational only)
   - Minimum score: 0
   - Generate summary text describing overall security posture
   - Categorize overall: A (90-100), B (70-89), C (50-69), D (30-49), F (0-29)

4. **Store results** in database

### Security Check Implementations:

**SSL/TLS Check** (`services/scanner/ssl_checker.py`):
```python
# 1. Connect to the domain on port 443
# 2. Retrieve the SSL certificate
# 3. Check:
#    - Certificate validity (not expired, not self-signed)
#    - Certificate expiration date (warn if < 30 days)
#    - Certificate chain completeness
#    - TLS version (flag TLS 1.0/1.1 as insecure, require 1.2+)
#    - Cipher suite strength
#    - HSTS header presence
#    - Certificate issuer (Let's Encrypt, DigiCert, etc.)
# 4. Return severity + findings
#    - No SSL at all → CRITICAL
#    - Expired cert → CRITICAL
#    - Weak TLS version → HIGH
#    - Expiring soon → MEDIUM
#    - Missing HSTS → MEDIUM
#    - All good → PASS
```

**Security Headers Check** (`services/scanner/headers_checker.py`):
```python
# 1. Make a GET request to the URL
# 2. Check for presence and correct configuration of:
#    - Strict-Transport-Security (HSTS)
#    - Content-Security-Policy (CSP)
#    - X-Content-Type-Options (should be "nosniff")
#    - X-Frame-Options (should be "DENY" or "SAMEORIGIN")
#    - X-XSS-Protection
#    - Referrer-Policy
#    - Permissions-Policy
#    - Cache-Control (for sensitive pages)
# 3. Grade each header: present+correct, present+misconfigured, missing
# 4. Missing critical headers (CSP, HSTS) → HIGH
# 5. Missing other headers → MEDIUM
# 6. Return list of findings with recommendations for each missing/misconfigured header
```

**CMS Detection** (`services/scanner/cms_detector.py`):
```python
# 1. Fetch the homepage HTML
# 2. Detect CMS from common signatures:
#    - WordPress: /wp-content/, /wp-includes/, meta generator tag
#    - Joomla: /administrator/, /components/, meta generator
#    - Drupal: /sites/default/, Drupal.settings in JS
#    - Others: Squarespace, Wix, Ghost, etc.
# 3. If CMS detected:
#    - Extract version from meta tag, readme.html, changelog
#    - Check if version is current (compare against known latest versions)
#    - Check for known vulnerabilities in that version (use a small local DB of major CVEs)
#    - Check if admin panel is publicly accessible (/wp-admin, /administrator, etc.)
#    - Check if login page has brute-force protection
# 4. Outdated CMS → HIGH
# 5. Exposed admin panel → MEDIUM
# 6. Unknown CMS with no issues → INFO
```

**Port Scan** (`services/scanner/port_scanner.py`):
```python
# 1. Scan common web-related ports:
#    - 80 (HTTP), 443 (HTTPS), 8080, 8443 (alt HTTP/S)
#    - 21 (FTP), 22 (SSH), 3306 (MySQL), 5432 (PostgreSQL)
#    - 3389 (RDP), 27017 (MongoDB)
# 2. Use socket connect with short timeout (2s)
# 3. For each open port:
#    - Identify the service if possible (banner grab)
#    - Flag database ports open to internet → CRITICAL
#    - Flag FTP open → HIGH
#    - Flag RDP open → CRITICAL
#    - Flag non-standard web ports → LOW/INFO
# 4. Note: Keep this lightweight — not a full nmap scan
```

**DNS Configuration Check** (`services/scanner/dns_checker.py`):
```python
# 1. Query DNS records for the domain:
#    - A/AAAA records
#    - MX records
#    - TXT records (look for SPF, DKIM, DMARC)
#    - NS records
#    - CAA records
# 2. Check:
#    - SPF record exists and is valid → prevents email spoofing
#    - DMARC record exists → prevents email impersonation
#    - DNSSEC enabled (bonus)
#    - CAA record exists (controls who can issue SSL certs)
# 3. Missing SPF → HIGH (email spoofing risk)
# 4. Missing DMARC → HIGH (impersonation risk)
# 5. Missing CAA → LOW
# 6. Important for civil society orgs: email spoofing is a common attack vector
```

**Common Vulnerability Indicators** (`services/scanner/vuln_checker.py`):
```python
# 1. Check for common misconfigurations:
#    - Directory listing enabled (try common dirs: /images/, /uploads/, /backup/)
#    - Server version disclosed in headers (Server: Apache/2.4.41)
#    - X-Powered-By header revealing technology
#    - Error pages revealing stack traces (try /nonexistent-page-404)
#    - .git directory exposed (/.git/HEAD)
#    - .env file exposed (/.env)
#    - Backup files exposed (/backup.zip, /db.sql, etc.)
#    - robots.txt revealing sensitive paths
#    - sitemap.xml present
# 2. Each finding gets appropriate severity
# 3. Exposed .git or .env → CRITICAL
# 4. Server version disclosed → MEDIUM
# 5. Directory listing → MEDIUM
```

**Cookie Security Check** (`services/scanner/cookie_checker.py`):
```python
# 1. Make request and collect Set-Cookie headers
# 2. For each cookie, check:
#    - Secure flag (must be set for HTTPS sites)
#    - HttpOnly flag (should be set for session cookies)
#    - SameSite attribute (should be Strict or Lax)
#    - Expires/Max-Age (session cookies vs persistent)
# 3. Missing Secure on HTTPS → MEDIUM
# 4. Missing HttpOnly on session cookie → HIGH
# 5. Missing SameSite → LOW
```

---

## Task 3: Scan Results Page

**Location**: `/dashboard/scan/[scanId]`

### Layout:

**Top Section — Security Score:**
- Large circular gauge showing 0–100 score
- Color coded: A (90-100, green), B (70-89, light green), C (50-69, yellow), D (30-49, orange), F (0-29, red)
- Letter grade next to the score
- Text: "Your website security score is [SCORE]. Grade: [LETTER]"
- Scanned URL displayed below
- Scan date and duration

**Finding Summary Bar:**
- Horizontal bar showing finding counts by severity:
  - 🔴 Critical: X | 🟠 High: X | 🟡 Medium: X | 🔵 Low: X | ⚪ Info: X | ✅ Pass: X
- Each severity is clickable to filter the findings list

**Findings List:**
- Each finding is an expandable card:
  - **Header**: Severity badge (colored) + Title + Check type tag
  - **Expanded content**:
    - Description (plain language — what's wrong and why it matters)
    - Impact (what could happen if exploited)
    - Recommendation (step-by-step fix instructions, written for non-technical users)
    - Technical details (collapsible, for technical users)
- Findings are grouped by check type OR sorted by severity (user can toggle)
- Default: sorted by severity (critical first)

**Actions:**
- "Download Report" button → PDF export with all findings (see Phase 3)
- "Re-Scan" button → run the scan again
- "Share Report" → generate a shareable link
- "Set Up Monitoring" → create a monitor for this URL (Phase 4)

---

## Task 4: Scan History

**Location**: `/dashboard/reports`

- Table of past scans:
  - URL scanned
  - Security score (color-coded badge)
  - Grade (A–F)
  - Finding counts (critical/high/medium/low)
  - Date scanned
  - Status
  - Click to view full results
- Sort by date, score, severity count
- Simple search by URL

---

## Task 5: Celery Task Queue

Set up Celery with Redis for async scan processing:

```python
# Flow:
# 1. POST /security-scans → create scan record, status=pending
# 2. Return scan_id immediately to frontend
# 3. Queue Celery task to run orchestrator
# 4. Frontend polls GET /security-scans/{scan_id} every 3 seconds
# 5. Each check updates the scan record as it completes
# 6. When all checks done → status=completed, calculate overall score
# 7. Frontend shows results

# Alternative: SSE endpoint for real-time progress
# GET /security-scans/{scan_id}/stream → Server-Sent Events
# Each check completion pushes an event to the client
# Frontend updates check cards in real-time
```

---

## Task 6: Demo Data & Test Targets

For the hackathon demo:
- Create a deliberately vulnerable test site (or use known test targets like scanme.nmap.org concept)
- Pre-compute results for 2–3 example scans showing different score ranges:
  - A well-configured site (score 90+)
  - A moderately configured site (score 50-70)
  - A poorly configured site (score < 30)
- These can be used for the demo recording and for the landing page preview

---

## Technical Notes

### Dependencies:
```
# Python backend
pip install httpx beautifulsoup4 python-nmap dnspython ssl-checker
# Or use lighter alternatives:
pip install httpx dnspython cryptography  # For SSL checks without external tools
```

### Important Considerations:
- **Rate limiting**: Don't overwhelm target servers — add delays between checks
- **Timeout handling**: Each check should have a 10s timeout, fail gracefully
- **Error isolation**: If one check fails, others still complete
- **Legal/ethical**: Only scan URLs that the user owns (they confirm during org registration)
- **Caching**: Don't re-scan the same URL within 1 hour (return cached results)

### Environment Variables:
```
# No external AI API keys needed for Phase 2!
# Security scanning uses open-source tools and direct HTTP requests
# This keeps costs at €0 for the scanning engine itself

# Optional for enhanced scanning:
SHODAN_API_KEY=         # For port/service detection (free tier: 100 queries/month)
SECURITYHEADERS_API=    # For header analysis (free)
```

---

## Deliverables Checklist
- [ ] Scan submission page with URL input and validation
- [ ] Python FastAPI backend with all 7+ security check implementations
- [ ] Scan orchestrator running checks in parallel with asyncio
- [ ] Celery + Redis async task processing (or SSE for real-time updates)
- [ ] Scan results page with security score gauge and findings list
- [ ] Each finding has plain-language description + recommendation
- [ ] Findings sorted by severity with expandable cards
- [ ] Scan history page with table view
- [ ] Overall score calculation (0–100) with letter grades
- [ ] Real-time progress feedback during scanning
- [ ] Proper error handling (timeouts, unreachable sites, individual check failures)
- [ ] Demo data for 2–3 example scans
- [ ] Caching to prevent re-scanning same URL within 1 hour
