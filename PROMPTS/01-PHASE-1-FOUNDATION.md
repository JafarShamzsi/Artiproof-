# Phase 1 — Foundation + Landing Page (UPDATE)

## Context
Read `00-PROJECT-BRIEF.md` first for full project context. CivicGuards has pivoted from a misinformation-only platform to a **Cyber Security Shield for Civil Society** — website security scanning + misinformation detection for civil society organizations in Azerbaijan.

## Status
Phase 1 is **mostly built** from the previous version. This document describes what needs to be UPDATED to reflect the pivot, not rebuilt from scratch.

> **IMPORTANT**: The landing page spec in `01B-LANDING-PAGE-PREMIUM.md` needs significant content updates but the technical architecture (3D scene, animations, components) can stay the same. Update the copy and sections as described below.

---

## Task 1: Update Landing Page Copy & Sections

The landing page structure and animations are already built. Update the CONTENT to reflect the pivot:

### Hero Section Updates:
- **Eyebrow text**: "CYBER SECURITY FOR CIVIL SOCIETY" (was: "MISINFORMATION THREAT INTELLIGENCE")
- **Headline**: "Your Organization's<br/>Digital **Shield**" (was: "The Truth Has a Guardian")
- **Subheadline**: "Free security scanning and vulnerability assessment for civil society organizations. Know your risks. Fix your weaknesses. Stay protected."
- **CTAs**: "Scan Your Website" (primary) + "Learn How It Works" (secondary)
- **Social proof**: "Built for NGOs, media, and activists in Azerbaijan"

### Problem Section Updates:
Replace misinformation stats with cybersecurity stats relevant to civil society:
- "78% of NGOs have experienced a cyber attack"
- "60% of civil society websites have critical vulnerabilities"
- "$4.5M average cost of a data breach"
- "< 5min to scan your entire website"

### How It Works — 3 Steps Update:
- Step 1: "Enter Your URL" — Paste your organization's website address
- Step 2: "Automated Security Scan" — We check SSL, headers, CMS vulnerabilities, exposed endpoints, misconfigurations, and more
- Step 3: "Get Your Report" — Plain-language report with severity ratings and step-by-step fix instructions

### Scanner Preview Update:
Replace the misinformation engine grid with security scan categories:
```
┌─────────────────┬──────────────────┬──────────────────┐
│  🟢 SSL/TLS     │  🔴 Security     │  🟡 CMS          │
│  VALID (A+)     │  Headers (F)     │  OUTDATED (6.2)  │
├─────────────────┼──────────────────┼──────────────────┤
│  🔴 Open Ports  │  🟢 DNS Config   │  🟡 Misinfo      │
│  3 EXPOSED      │  SECURE          │  2 CAMPAIGNS     │
└─────────────────┴──────────────────┴──────────────────┘
```

### Features Grid Update:
- **Security Scanner**: "Paste your URL. Get a full security audit in minutes."
- **Vulnerability Reports**: "Plain-language reports with fix instructions anyone can follow."
- **Misinfo Shield**: "Detect disinformation campaigns targeting your organization."
- **Monitoring**: "Continuous monitoring alerts you when new vulnerabilities appear."
- **DISARM Mapping**: "Understand HOW you're being targeted with DISARM framework."
- **Free for NGOs**: "100% free for civil society organizations in Azerbaijan."

### Audience Section Update:
Replace with civil society personas:
- **NGOs** → "Protect your donor data and member information"
- **Independent Media** → "Secure your publishing platform and detect impersonation"
- **Activists** → "Keep your communications safe and detect surveillance"
- **Community Groups** → "Simple security for non-technical teams"

### Pricing Section Update:
- **Free (Civil Society)**: All features free for registered civil society orgs in Azerbaijan
- **Pro (Businesses)**: Extended features for small businesses (future)
- **Enterprise**: Custom solutions (future)
- For the hackathon demo, emphasize the FREE tier prominently

### Remove/Deprioritize:
- Education Hub section (remove for now — not part of MLP)
- Waitlist → change to "Register Your Organization" with org name + website URL + email

---

## Task 2: Update Database Schema

The existing Prisma schema needs updates. KEEP existing tables that still apply (users, accounts, sessions). ADD new tables, MODIFY changed ones.

### New/Modified Models:

```prisma
// ADD to User model:
model User {
  // ... keep existing fields
  organizationId  String?  @map("organization_id")
  organization    Organization? @relation(fields: [organizationId], references: [id])
  // REMOVE: streakCount, xpPoints (education gamification not in MLP)
}

// NEW: Organization model
model Organization {
  id              String   @id @default(cuid())
  name            String
  type            String   // ngo, media, activist, community, business, other
  websiteUrl      String?  @map("website_url")
  country         String   @default("Azerbaijan")
  description     String?
  verified        Boolean  @default(false)
  createdAt       DateTime @default(now()) @map("created_at")

  users           User[]
  securityScans   SecurityScan[]
  monitors        Monitor[]

  @@map("organizations")
}

// NEW: SecurityScan (replaces old Scan model for security checks)
model SecurityScan {
  id             String     @id @default(cuid())
  organizationId String?    @map("organization_id")
  userId         String?    @map("user_id")
  targetUrl      String     @map("target_url")
  status         String     @default("pending") // pending, scanning, completed, failed
  overallScore   Int?       @map("overall_score") // 0-100, higher = safer
  summary        String?
  createdAt      DateTime   @default(now()) @map("created_at")
  completedAt    DateTime?  @map("completed_at")

  organization   Organization? @relation(fields: [organizationId], references: [id])
  results        ScanCheckResult[]

  @@index([organizationId, createdAt])
  @@map("security_scans")
}

// NEW: Individual check results within a security scan
model ScanCheckResult {
  id             String   @id @default(cuid())
  scanId         String   @map("scan_id")
  checkType      String   @map("check_type") // ssl, headers, cms, ports, xss, sqli, misconfig, dns, misinfo
  severity       String   // critical, high, medium, low, info, pass
  title          String
  description    String
  recommendation String?
  rawData        Json?    @map("raw_data")
  createdAt      DateTime @default(now()) @map("created_at")

  scan SecurityScan @relation(fields: [scanId], references: [id], onDelete: Cascade)

  @@index([scanId])
  @@map("scan_check_results")
}

// NEW: Monitor for ongoing checks
model Monitor {
  id             String   @id @default(cuid())
  organizationId String   @map("organization_id")
  targetUrl      String   @map("target_url")
  checkInterval  String   @default("weekly") // daily, weekly, monthly
  isActive       Boolean  @default(true) @map("is_active")
  lastCheckedAt  DateTime? @map("last_checked_at")
  createdAt      DateTime @default(now()) @map("created_at")

  organization   Organization @relation(fields: [organizationId], references: [id])
  alerts         Alert[]

  @@map("monitors")
}

// NEW: Alerts from monitors
model Alert {
  id          String   @id @default(cuid())
  monitorId   String   @map("monitor_id")
  alertType   String   @map("alert_type") // new_vulnerability, ssl_expiring, score_dropped
  severity    String   // critical, high, medium, low
  title       String
  message     String
  isRead      Boolean  @default(false) @map("is_read")
  createdAt   DateTime @default(now()) @map("created_at")

  monitor Monitor @relation(fields: [monitorId], references: [id], onDelete: Cascade)

  @@map("alerts")
}
```

### Tables to KEEP as-is:
- `accounts` (NextAuth)
- `sessions` (NextAuth)
- `disarm_tactics` (for misinfo module later)
- `disarm_techniques` (for misinfo module later)

### Tables to REMOVE or DEPRIORITIZE:
- `courses`, `lessons`, `quizzes`, `quiz_questions`, `user_progress`, `user_badges` (education hub — not in MLP)
- `reports`, `community_votes`, `expert_verifications` (community — not in MLP)
- `claims`, `sources`, `scan_disarm_tags` (misinformation-specific — Phase 5)
- Keep the old `scans` and `scan_results` tables but rename or mark as deprecated

---

## Task 3: Update Dashboard Shell

Update the sidebar navigation for the pivoted product:

### New Sidebar:
- **Dashboard** (home icon) — Overview of org security posture
- **Security Scan** (shield icon) — Run a new scan
- **Reports** (file-text icon) — View past scan reports
- **Monitoring** (activity icon) — Active monitors and alerts — "Coming Soon" badge
- **Misinfo Shield** (eye icon) — Disinformation detection — "Coming Soon" badge
- **Settings** (settings icon)

### Dashboard Home Updates:
- "Security Score: 72/100" (large gauge)
- "Open Vulnerabilities: 5" (with severity breakdown)
- "Last Scan: 2 days ago"
- "Recent Scans" list
- "Quick Scan" button prominently placed

---

## Task 4: Update Registration Flow

Add organization registration step after user signup:
1. User creates account (email + password) — existing flow
2. New step: "Register Your Organization"
   - Organization name (required)
   - Organization type (dropdown: NGO, Media, Activist Group, Community Org, Other)
   - Website URL (required)
   - Country (default: Azerbaijan)
   - Brief description (optional)
3. After registration, auto-trigger first security scan of their website

---

## Deliverables Checklist
- [ ] Landing page copy updated for security focus
- [ ] Problem stats updated for cybersecurity
- [ ] Scanner preview shows security checks instead of misinfo engines
- [ ] Features grid reflects new product pillars
- [ ] Database schema updated with Organization, SecurityScan, ScanCheckResult, Monitor, Alert models
- [ ] Dashboard sidebar updated for security-focused navigation
- [ ] Registration flow includes organization setup
- [ ] Remove/hide education and community sections from navigation
- [ ] Landing page CTA changed to "Register Your Organization"
