# Phase 6 — Sustainability, API & Scale

## Context
Read `00-PROJECT-BRIEF.md` for full context. Phases 1-5 are built. The core product (security scanning + misinfo detection) works for civil society organizations in Azerbaijan. Now we build sustainability — the plan for how CivicGuards survives after the €10K-12K grant runs out.

## The Sustainability Challenge
Irina (mentor) was clear: the hackathon evaluators will ask "how does this survive after the grant?" We need a credible answer that shows CivicGuards can be self-sustaining.

## Objective
Implement the sustainability model: free for civil society orgs (forever), paid tiers for businesses and international organizations, a public API for developers, and the operational foundations to scale beyond Azerbaijan.

---

## Task 1: Freemium Model

### Pricing Tiers:

**Free (Civil Society — Forever)**:
- Unlimited security scans for verified civil society orgs in Azerbaijan
- Full vulnerability reports with recommendations
- Weekly automated monitoring
- Misinfo shield (basic)
- Email alerts
- Up to 3 team members
- This tier is funded by the grant initially, then by revenue from paid tiers

**Pro ($19/mo — Businesses & International Orgs)**:
- Everything in Free
- Daily automated monitoring
- Priority scan queue
- Advanced misinfo detection
- Up to 10 team members
- Comparison reports and trend analysis
- White-label PDF reports (remove CivicGuards branding)
- Email + webhook alerts
- Scan history (unlimited)

**Enterprise (Custom pricing, from $199/mo)**:
- Everything in Pro
- API access
- Unlimited team members
- Bulk scanning
- Custom integrations
- Dedicated support
- SLA guarantees
- Custom reporting

### Verification System for Free Tier:
```python
# Civil society orgs must be verified to get free access:
# 1. Register with org details (name, type, website, description)
# 2. Admin reviews and verifies:
#    - Is this a real civil society org?
#    - Based in Azerbaijan (or EaP region)?
#    - Not a commercial entity?
# 3. Options for verification:
#    - Admin manual review (initial approach)
#    - Domain verification (prove ownership)
#    - Reference check (link to public registry or partner org vouching)
# 4. Unverified orgs get a 14-day free trial, then must verify or upgrade to Pro
```

### Payment Integration:
- Use Stripe for paid tiers
- Stripe Checkout for upgrade flow
- Webhook handlers for subscription lifecycle
- Customer portal for managing subscriptions
- Keep it simple — monthly billing only initially

---

## Task 2: Public API

### Why an API:
- Enterprise customers integrate CivicGuards into their own tools
- Developers can build on top of the platform
- Researchers can automate bulk analysis
- Revenue stream: API access is Enterprise-only

### API Design:

**Base URL**: `/api/public/v1`
**Auth**: API key in header `X-API-Key: cg_xxxx`

```
# Security Scan
POST /v1/scan
Body: { "url": "https://example.com", "checks": ["ssl", "headers", "cms", "all"] }
Response: { "scan_id": "...", "status": "scanning" }

GET /v1/scan/{scan_id}
Response: {
  "scan_id": "...",
  "status": "completed",
  "score": 72,
  "grade": "C",
  "findings": [
    { "check_type": "ssl", "severity": "pass", "title": "Valid SSL certificate", ... },
    { "check_type": "headers", "severity": "high", "title": "Missing CSP header", ... },
    ...
  ],
  "summary": "..."
}

# Misinfo Scan
POST /v1/misinfo-scan
Body: { "domain": "example.com" }
Response: { "scan_id": "...", "status": "scanning" }

GET /v1/misinfo-scan/{scan_id}
Response: { ... }

# Quick Check (lightweight, instant)
GET /v1/quick-check?url=https://example.com
Response: {
  "url": "https://example.com",
  "ssl_valid": true,
  "security_headers_grade": "D",
  "estimated_score": 55,
  "recommendation": "Full scan recommended"
}
```

### API Key Management:
- Enterprise users generate API keys from Settings
- Each key: name, prefix, created date, last used, rate limit
- Rate limiting: 100 requests/day default, configurable
- Usage dashboard showing API call history

### API Documentation:
- Simple documentation page at `/docs/api`
- Request/response examples
- Code snippets in Python, JavaScript, cURL
- Authentication guide
- Rate limiting explanation

---

## Task 3: Cost Optimization

### Server Costs After Grant:
```
Monthly cost estimates:
- VPS (DigitalOcean/Hetzner): €15-30/month
- PostgreSQL (managed or self-hosted): €0-15/month
- Redis: €0-5/month (or included with VPS)
- Gemini API: €5-10/month (at moderate usage)
- Domain + SSL: €2/month
- Email service (alerts): €0-5/month (SendGrid free tier)
-------------------------------------------------
Total: €22-65/month

Break-even: 2-4 Pro subscriptions cover monthly costs
```

### Cost Reduction Strategies:
- Cache scan results aggressively (same URL within 1 hour = cached)
- Use Gemini Flash (cheapest model) for report generation
- Rate limit free tier scanning (max 5 scans/day for unverified)
- Run security checks locally (no API costs) — only AI narrative generation costs money
- Use free hosting initially (Railway, Render free tier for demo)

---

## Task 4: Regional Expansion Foundations

### Beyond Azerbaijan:
The architecture should support expanding to other EaP countries (Georgia, Moldova, Ukraine, Armenia, Belarus):
- Country field on organization registration
- Localization support (report language, recommendations in local language)
- Region-specific vulnerability knowledge (common hosting providers, local CMS choices)
- Partner organization directory per country

### For the Hackathon Pitch:
Frame sustainability as:
1. **Year 1**: Grant-funded, free for all civil society in Azerbaijan
2. **Year 2**: Pro tier launches, revenue from businesses covers costs
3. **Year 3+**: Expand to other EaP countries, enterprise clients fund free tier for NGOs

---

## Task 5: Analytics & Impact Metrics

### Platform Analytics Dashboard (Admin):
Track metrics that demonstrate impact to grant reviewers and future funders:
- Total organizations served
- Total scans run
- Vulnerabilities found and resolved
- Average security score improvement over time
- Organizations by type and country
- Most common vulnerabilities (helps prioritize education)

### Impact Report Generation:
Auto-generate quarterly impact reports:
- "CivicGuards helped X organizations improve their security by Y% on average"
- "Z critical vulnerabilities were discovered and fixed"
- "Top 5 most common issues and our recommendations"
- Export as PDF for grant reporting

---

## Task 6: Browser Extension (Nice-to-Have)

If time permits, a simple Chrome extension:
- Click extension icon → shows security score for current website
- "Full scan" button → opens CivicGuards dashboard
- Simple traffic light: green/yellow/red based on known scan results
- NOT a priority for the hackathon — only build if all other phases are done

---

## Deliverables Checklist
- [ ] Stripe integration for Pro and Enterprise tiers
- [ ] Civil society verification workflow (admin approval)
- [ ] Free tier enforcement for verified orgs
- [ ] Public API with scan and quick-check endpoints
- [ ] API key management (generate, revoke, usage tracking)
- [ ] API documentation page
- [ ] Rate limiting for API
- [ ] Cost optimization (caching, free-tier limits)
- [ ] Platform analytics dashboard (admin)
- [ ] Impact metrics tracking (orgs served, vulns found/fixed)
- [ ] Impact report generation (PDF)
- [ ] Regional expansion foundations (country field, localization prep)
- [ ] Sustainability narrative for pitch (Year 1-3 plan)
