# Phase 5 — Misinformation Detection Module (Misinfo Shield)

## Context
Read `00-PROJECT-BRIEF.md` for full context. Phases 1-4 (foundation, security scanner, reports, monitoring) are built. The core security product is complete. Now we add the **differentiating feature** that no other security scanner has: detecting disinformation campaigns targeting the organization.

## Why This Matters
Civil society organizations in Azerbaijan aren't just attacked technically — they're also targeted by coordinated disinformation. Fake social media accounts impersonate them, lookalike domains are registered to phish their supporters, and their content is manipulated and taken out of context. CivicGuards is uniquely positioned to detect both technical AND information threats.

## Objective
Build a misinformation detection module that checks if an organization is being targeted by disinformation campaigns — domain spoofing, social media impersonation, content manipulation, and coordinated inauthentic behavior.

---

## Task 1: Misinfo Scan Interface

**Location**: `/dashboard/misinfo`

### Interface:
- "Misinfo Shield" section header with explanation: "Check if your organization is being targeted by disinformation campaigns"
- Input: Organization domain (pre-filled from org profile)
- "Run Misinfo Scan" button
- Scan checks listed: Domain Spoofing, Social Media Impersonation, Content Manipulation, DISARM Classification

### What We Check:
When a misinfo scan runs for an organization's domain:

1. **Domain Spoofing Detection**: Look for lookalike domains registered to impersonate the organization
2. **Social Media Impersonation**: Search for fake accounts using the org's name/brand
3. **Content Manipulation**: Check if the org's content is being taken out of context or manipulated
4. **DISARM Classification**: Classify any detected threats using the DISARM framework

---

## Task 2: Detection Engines

### Domain Spoofing Detector (`services/misinfo/domain_spoof.py`):
```python
# 1. Generate typosquat variations of the org's domain:
#    - Character substitution: o→0, l→1, i→l
#    - Missing characters: civicguards → cicguards
#    - Added characters: civicguards → civicguardss
#    - TLD variations: .com → .net, .org, .info, .az → .com
#    - Homograph attacks: using Unicode lookalikes
# 2. Check if any of these variations are registered (DNS lookup)
# 3. If registered, check:
#    - Is the site active?
#    - Does it mimic the original site's content?
#    - When was it registered? (recent registration = more suspicious)
#    - Who registered it? (WHOIS if available)
# 4. Score each lookalike domain by risk:
#    - Active + mimics content → CRITICAL
#    - Active but unrelated → LOW
#    - Registered but not active → MEDIUM
#    - Not registered (available) → INFO (mention as "you may want to register this defensively")
```

### Social Media Impersonation Checker (`services/misinfo/social_impersonation.py`):
```python
# Use web search (or social media APIs if available) to find:
# 1. Search for org name on major platforms
# 2. Use Gemini/Grok to analyze results:
#    - "Given this organization [name, domain, description], analyze these
#      search results and identify potential impersonation accounts.
#      Look for: similar names, copied bios, stolen logos, recent creation dates."
# 3. Flag suspicious accounts with evidence
# 4. Severity:
#    - Confirmed impersonation → HIGH
#    - Suspicious similarity → MEDIUM
#    - Minor name overlap → LOW
# Note: This is AI-assisted analysis, not definitive — always flag as "potential"
```

### Content Manipulation Detector (`services/misinfo/content_manipulation.py`):
```python
# 1. Fetch the org's actual website content (homepage, about page, key pages)
# 2. Search the web for copies/modifications of their content
# 3. Use Gemini to analyze:
#    - Are there sites republishing this org's content with alterations?
#    - Are quotes from this org being taken out of context?
#    - Are fake press releases or statements attributed to this org?
# 4. This is a more speculative check — results should be flagged as "potential"
# 5. Severity based on reach and deception level
```

### DISARM Classifier (`services/misinfo/disarm_classifier.py`):
```python
# For any detected misinfo threats, classify using DISARM framework:
# 1. Take the detected threat (domain spoof, impersonation, etc.)
# 2. Use Gemini/Grok to classify:
#    "Given this detected threat against a civil society organization:
#     [threat description]
#     Classify it using the DISARM framework. Which techniques are being used?
#     Provide technique IDs, names, and explanations."
# 3. Store DISARM technique mappings
# 4. Show on the report: "This attack uses DISARM technique T0007: Create Inauthentic Social Media Pages"
```

---

## Task 3: Misinfo Results Page

**Location**: `/dashboard/misinfo/[scanId]`

### Layout:

**Threat Score:**
- 0-100 score (0 = no threats detected, 100 = severe targeting)
- Color-coded gauge: green (0-30), yellow (31-60), orange (61-80), red (81-100)
- Label: "Misinformation Threat Level: [LOW/MODERATE/HIGH/CRITICAL]"

**Findings by Category:**
- **Domain Spoofing** section:
  - Table of detected lookalike domains
  - Risk level badge per domain
  - "Whois" and "Visit" action buttons
  - Recommendation: "Consider registering these domains defensively"

- **Social Media Impersonation** section:
  - List of suspicious accounts found
  - Confidence level for each
  - Platform icon
  - "Report this account" guidance link

- **Content Manipulation** section:
  - List of detected manipulations
  - Side-by-side: original vs altered content
  - Source where manipulation was found

- **DISARM Classification** section:
  - Detected techniques listed as cards
  - Each with: technique ID, name, description, how it applies
  - "This is a known disinformation tactic used to [explanation]"

### Actions:
- Download misinfo report (PDF)
- "Set up monitoring" for ongoing misinfo detection
- "Report to platform" links for social media impersonation

---

## Task 4: Combined Security + Misinfo Report

The real value proposition is the COMBINED view:

**Location**: `/dashboard/overview` or integrated into main dashboard

- Security Score (from Phase 2): X/100
- Misinfo Threat Score (from this phase): X/100
- Combined "CivicGuards Shield Score": weighted combination
- "Your organization faces [N] technical vulnerabilities and [M] information threats"
- Single PDF report combining both

This is the differentiator — no other tool gives you BOTH in one place.

---

## Task 5: DISARM Framework Explorer (Simplified)

**Location**: `/dashboard/disarm`

A simplified version of the DISARM framework explorer (not the full ATT&CK-style matrix from the old spec):
- List of all DISARM techniques detected across the org's scans
- Each technique card shows:
  - Technique ID and name
  - Description (plain language)
  - How many times detected
  - Latest detection date
  - "What this means for your organization" explanation
- Searchable and filterable
- Educational purpose: help orgs understand the disinformation playbook

---

## Technical Notes

### API Endpoints:
```
POST /api/v1/misinfo-scans              — Run misinfo scan
GET  /api/v1/misinfo-scans/{scan_id}    — Get results
GET  /api/v1/misinfo-scans              — Scan history

GET  /api/v1/disarm/techniques          — List all DISARM techniques
GET  /api/v1/disarm/techniques/{id}     — Technique detail
GET  /api/v1/disarm/detected            — Techniques detected for this org
```

### Environment Variables:
```
GEMINI_API_KEY=...    # For AI-powered analysis
GROK_API_KEY=...      # Fallback AI analysis
# Domain availability checking is free (DNS lookups)
# Social media searching uses web search APIs
```

### Cost Considerations:
- Domain spoofing detection: Free (DNS lookups)
- AI analysis (Gemini Flash): ~$0.02-0.05 per misinfo scan
- Social media search: depends on approach (web scraping vs API)
- At 50 misinfo scans/month: ~$1-2.50/month

---

## Deliverables Checklist
- [ ] Misinfo scan submission interface
- [ ] Domain spoofing detector (typosquat generation + DNS lookup)
- [ ] Social media impersonation checker (AI-assisted)
- [ ] Content manipulation detector (AI-assisted)
- [ ] DISARM classification for detected threats
- [ ] Misinfo results page with categorized findings
- [ ] Threat score calculation for misinfo
- [ ] Combined security + misinfo dashboard view
- [ ] Simplified DISARM technique explorer
- [ ] DISARM seed data (import tactics and techniques)
- [ ] PDF export for misinfo report
- [ ] All new API endpoints
