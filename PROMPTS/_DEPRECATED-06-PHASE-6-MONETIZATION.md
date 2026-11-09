# Phase 6 — Monetization, Public API & Browser Extension

## Context
Read `00-PROJECT-BRIEF.md` for full context. Phases 1-5 are built. Now we monetize: Stripe integration for subscriptions, a public API for enterprise customers, and a browser extension for mass adoption.

## Objective
Implement the full freemium business model with Stripe, build a developer-facing API with documentation, and create a Chrome/Firefox browser extension that lets users right-click any content and scan with CivicGuards.

---

## Task 1: Stripe Subscription Integration

### Pricing Tiers:

**Free ($0/mo)**:
- 10 scans per day
- Basic scan results (summary + overall score)
- Education hub access (all courses)
- Community participation (report + vote)
- Single DISARM technique view per scan

**Pro ($12/mo or $99/yr)**:
- Unlimited scans
- Full engine-by-engine results
- Detailed DISARM classification
- Raw data access
- Analytics dashboard
- Export PDF reports and CSV
- Bulk scanning (up to 100/batch)
- Custom alerts (up to 10)
- Streak freeze (1/week)
- Priority processing queue
- No ads

**Enterprise (custom pricing, starting $499/mo)**:
- Everything in Pro
- API access with rate limits
- Unlimited bulk scanning
- Webhook integrations
- White-label scan reports
- Team management (up to 50 seats)
- Dedicated support
- Custom alert limits
- SLA guarantees
- Narrative tracking (unlimited)
- Source intelligence export

### Stripe Implementation:

**Setup:**
```
npm install stripe @stripe/stripe-js
```

**Backend (Python):**
```
pip install stripe
```

**Flow:**
1. Create Stripe Products + Prices for Pro monthly, Pro yearly, Enterprise
2. When user clicks "Upgrade to Pro":
   - Create Stripe Checkout Session
   - Redirect to Stripe-hosted checkout
   - On success: Stripe webhook → update user role to PRO
3. Stripe webhooks to handle:
   - `checkout.session.completed` → activate subscription
   - `customer.subscription.updated` → handle plan changes
   - `customer.subscription.deleted` → downgrade to FREE
   - `invoice.payment_failed` → notify user, grace period
4. Customer portal for managing subscription (upgrade, downgrade, cancel, update payment)
5. Store Stripe customer ID and subscription ID on user record

**New fields on User model:**
```prisma
model User {
  // ... existing fields
  stripeCustomerId    String?  @unique @map("stripe_customer_id")
  stripeSubscriptionId String? @map("stripe_subscription_id")
  subscriptionStatus  String?  @map("subscription_status")  // active, past_due, canceled
  subscriptionEndsAt  DateTime? @map("subscription_ends_at")
}
```

### Pricing Page (`/pricing` — public):
- Three tier cards side by side
- Feature comparison table below
- FAQ section (cancellation, refunds, etc.)
- Testimonials section (placeholder)
- "Start Free" and "Upgrade to Pro" CTAs

### In-App Upgrade Prompts:
- When free user hits scan limit: "You've used all 10 scans today. Upgrade to Pro for unlimited."
- When free user tries to access Pro feature: "This feature requires Pro. Upgrade now →"
- Non-intrusive, dismissable, with clear value proposition
- Settings page: "Manage Subscription" button → Stripe Customer Portal

---

## Task 2: Public API

### API Design:

**Base URL**: `https://api.civicguards.com/v1` (or `/api/public/v1` for local dev)

**Authentication**: API key in header `X-API-Key: cg_live_xxxx`

**API Key Management:**
- Enterprise users can generate API keys from Settings page
- Each key has: name, prefix (cg_live_ or cg_test_), created date, last used, permissions
- Revoke/regenerate keys
- Rate limiting per key (configurable per enterprise plan)

### Endpoints:

**Scan:**
```
POST /v1/scan
Body: { "content": "claim text or URL", "type": "text|url|image", "engines": ["all"] }
Response: { "scan_id": "...", "status": "processing" }

GET /v1/scan/{scan_id}
Response: {
  "scan_id": "...",
  "status": "completed",
  "threat_score": 73,
  "summary": "...",
  "results": [
    { "engine": "grok", "verdict": "misleading", "confidence": 0.85, "analysis": "..." },
    { "engine": "gemini", "verdict": "misleading", "confidence": 0.78, "analysis": "..." },
    ...
  ],
  "disarm_techniques": [
    { "id": "T0023", "name": "Distort facts", "confidence": 0.9 }
  ],
  "source_credibility": { "domain": "...", "score": 35, "bias": "right" }
}
```

**Bulk Scan:**
```
POST /v1/scan/bulk
Body: { "items": [{ "content": "...", "type": "text" }, ...] }
Response: { "job_id": "...", "total": 50, "status": "processing" }

GET /v1/scan/bulk/{job_id}
Response: { "job_id": "...", "completed": 35, "total": 50, "results": [...] }
```

**Claims Database:**
```
GET /v1/claims/search?q=query
Response: { "claims": [{ "text": "...", "verdict": "false", "total_scans": 47, "first_seen": "..." }] }
```

**Source Lookup:**
```
GET /v1/sources/{domain}
Response: { "domain": "...", "credibility_score": 82, "bias": "center-left", "factual_reporting": "high" }
```

**DISARM:**
```
GET /v1/disarm/techniques
GET /v1/disarm/techniques/{id}
```

### API Documentation Page (`/docs/api`):
- Interactive API documentation (similar to Stripe docs style)
- Each endpoint with:
  - Description
  - Request/response examples
  - Code snippets in Python, JavaScript, cURL
  - Try-it-out playground
- Authentication guide
- Rate limiting explanation
- Error codes reference
- Webhooks documentation

Build using a clean shadcn-based layout with code blocks and syntax highlighting. Consider using MDX for the docs content.

### Rate Limiting:
- Free: No API access
- Pro: No API access (web only)
- Enterprise: Configurable (default: 1000 requests/day, 10 requests/second)
- Return `429 Too Many Requests` with `Retry-After` header
- Track usage in Redis

### API Key Backend:
```
POST /api/v1/api-keys              — Generate new API key
GET  /api/v1/api-keys              — List user's API keys
DELETE /api/v1/api-keys/{id}       — Revoke API key
GET  /api/v1/api-keys/{id}/usage   — Usage statistics
```

New table:
```prisma
model ApiKey {
  id          String   @id @default(cuid())
  userId      String   @map("user_id")
  name        String
  keyHash     String   @unique @map("key_hash")  // Store hashed, never plain
  keyPrefix   String   @map("key_prefix")  // cg_live_xxxx (first 12 chars for display)
  permissions Json     @default("{}")
  rateLimit   Int      @default(1000) @map("rate_limit")  // requests per day
  lastUsedAt  DateTime? @map("last_used_at")
  expiresAt   DateTime? @map("expires_at")
  createdAt   DateTime @default(now()) @map("created_at")

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@map("api_keys")
}
```

---

## Task 3: Browser Extension

### Chrome Extension (Manifest V3):

**Popup UI:**
- Small popup when clicking the extension icon
- Shows: login status, today's scan count, quick scan input
- "Scan this page" button — scans the current page URL
- Recent scan results (last 3)
- Link to open full dashboard

**Context Menu Integration:**
- Right-click any selected text → "Scan with CivicGuards"
- Right-click any link → "Check this link with CivicGuards"
- Right-click any image → "Analyze this image with CivicGuards"

**Inline Results:**
- After scanning, show a small toast/badge on the page with the threat score
- Click the toast to see full results in a side panel or new tab
- Optional: highlight flagged content on the page with a colored border

**Page Scanning:**
- "Scan Page" button in popup → extract all claims from the current page
- Show a summary: "Found 3 potentially misleading claims on this page"
- List each claim with its mini threat score

**Technical Structure:**
```
extension/
├── manifest.json
├── popup/
│   ├── popup.html
│   ├── popup.js
│   └── popup.css
├── background/
│   └── service-worker.js    # Handle context menus, API calls
├── content/
│   └── content-script.js    # Page scanning, inline results
├── sidepanel/
│   ├── sidepanel.html       # Full results view
│   └── sidepanel.js
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── utils/
    └── api.js               # CivicGuards API client
```

**Authentication:**
- Use CivicGuards API key (users generate from Settings page)
- Store API key in chrome.storage.sync
- Login flow in popup → open CivicGuards in new tab → generate API key → paste back into extension

### Firefox Add-on:
- Same codebase with minor manifest differences
- WebExtensions API compatible

---

## Task 4: Team Management (Enterprise)

### Team Features:
- Enterprise admin can invite team members
- Team dashboard shows aggregated scan activity
- Shared scan history within the team
- Team-level analytics
- Role-based access: Admin, Analyst, Viewer
- Seat management (add/remove team members)

### Implementation:
New tables:
```prisma
model Team {
  id          String   @id @default(cuid())
  name        String
  ownerId     String   @map("owner_id")
  maxSeats    Int      @default(50) @map("max_seats")
  createdAt   DateTime @default(now()) @map("created_at")

  members     TeamMember[]

  @@map("teams")
}

model TeamMember {
  id       String @id @default(cuid())
  teamId   String @map("team_id")
  userId   String @map("user_id")
  role     String @default("analyst")  // admin, analyst, viewer

  team Team @relation(fields: [teamId], references: [id], onDelete: Cascade)

  @@unique([teamId, userId])
  @@map("team_members")
}
```

### Team Pages:
- `/dashboard/team` — Team overview, member list, invite form
- `/dashboard/team/analytics` — Aggregated team analytics

---

## Task 5: Webhook System (Enterprise)

Enterprise customers can receive real-time events via webhooks:

### Events:
- `scan.completed` — When a scan finishes
- `alert.triggered` — When a custom alert is triggered
- `narrative.new` — When a new narrative is detected
- `narrative.updated` — When a narrative gets new scans

### Configuration:
- Webhook URL + secret key for signature verification
- Event type selection (subscribe to specific events)
- Retry logic (3 retries with exponential backoff)
- Delivery log with success/failure status

### Backend:
```
POST /api/v1/webhooks              — Create webhook endpoint
GET  /api/v1/webhooks              — List webhooks
PATCH /api/v1/webhooks/{id}        — Update webhook
DELETE /api/v1/webhooks/{id}       — Delete webhook
GET  /api/v1/webhooks/{id}/deliveries — Delivery log
POST /api/v1/webhooks/{id}/test    — Send test event
```

---

## Deliverables Checklist
- [ ] Stripe integration (checkout, webhooks, customer portal)
- [ ] Pricing page (public)
- [ ] In-app upgrade flows and paywalls
- [ ] Subscription management in settings
- [ ] Public API with all endpoints
- [ ] API key management (generate, revoke, usage tracking)
- [ ] API documentation page
- [ ] Rate limiting for API
- [ ] Chrome extension (popup, context menu, page scanning)
- [ ] Firefox extension
- [ ] Team management (Enterprise)
- [ ] Webhook system (Enterprise)
- [ ] All new database tables and migrations
