# Phase 4 — Dashboard, Monitoring & Alerts

## Context
Read `00-PROJECT-BRIEF.md` for full context. Phases 1-3 (foundation, security scanner, reports) are built. Now we build the **monitoring dashboard** — ongoing security posture tracking, automated re-scans, and alert notifications when new vulnerabilities are discovered or existing ones get worse.

## Objective
Build a security dashboard that gives organizations a clear picture of their security posture over time, with automated monitoring that catches new issues before attackers do.

---

## Task 1: Security Dashboard Home

**Location**: `/dashboard`

### Layout:

**Organization Security Overview:**
- **Score Card** (large, prominent):
  - Current overall security score (0-100) with color-coded gauge
  - Letter grade (A-F)
  - Trend arrow (↑ improving, ↓ declining, → stable) compared to previous scan
  - "Last scanned: X days ago" with "Re-scan now" button

- **Vulnerability Summary Cards** (4-card row):
  - 🔴 Critical Issues: X (clickable → filtered findings list)
  - 🟠 High Issues: X
  - 🟡 Medium Issues: X
  - ✅ Resolved This Month: X

- **Security Score Trend** (line chart, recharts):
  - Score over time (last 6 months)
  - Each data point is a scan
  - Hover shows score + date + key changes
  - Goal line at 80 (recommended minimum)

- **Recent Alerts** (card):
  - Last 5 alerts with severity badges
  - "View all alerts →" link
  - Mark as read inline

- **Quick Actions:**
  - "Run New Scan" button
  - "Download Latest Report" button
  - "View All Findings" button

---

## Task 2: Monitoring System

### Monitor Setup:
After a scan completes, prompt: "Set up monitoring for this URL?"

**Monitor Configuration:**
- Target URL (pre-filled from scan)
- Check interval: Daily / Weekly / Monthly
  - Daily: recommended for critical infrastructure
  - Weekly: default, good balance
  - Monthly: for lower-priority sites
- Alert preferences:
  - Alert on: New critical findings, New high findings, Score drops > X points, SSL expiring soon
  - Alert channels: In-app notification, Email (future)

**How Monitoring Works:**
```python
# Celery Beat (periodic tasks):
# 1. Every hour, check which monitors are due for a re-scan
# 2. For each due monitor:
#    a. Run the full security scan orchestrator
#    b. Compare results to previous scan
#    c. Identify: new findings, resolved findings, changed severities
#    d. If alert conditions met → create Alert records
#    e. Update monitor.last_checked_at
# 3. Store scan results (each re-scan creates a new SecurityScan record)
```

### Monitor Management (`/dashboard/monitoring`):
- Table of active monitors:
  - URL
  - Current score
  - Last checked
  - Next check due
  - Status (active/paused)
  - Alerts count (unread)
- Toggle monitoring on/off per URL
- Edit check interval
- Delete monitor

---

## Task 3: Alert System

### Alert Types:
- `new_critical` — New critical vulnerability found
- `new_high` — New high-severity issue found
- `ssl_expiring` — SSL certificate expiring within 30 days
- `score_dropped` — Security score dropped by 10+ points since last scan
- `score_improved` — Security score improved by 10+ points (positive alert)
- `finding_resolved` — A previously-found issue is now resolved (positive)

### In-App Notifications:
- Bell icon in top bar with unread count badge
- Notification dropdown showing recent alerts:
  - Severity-colored dot
  - Alert title (e.g., "New critical vulnerability found on yourorg.az")
  - Time ("2 hours ago")
  - Click to view the relevant scan results
- Mark as read / Mark all as read

### Alert Detail:
When clicking an alert, show:
- What changed (new finding details OR score comparison)
- Link to the full scan report
- Recommended immediate action
- "Dismiss" or "Acknowledge" button

### Backend:
```
GET  /api/v1/alerts                    — List alerts for org (paginated)
GET  /api/v1/alerts/unread-count       — Unread count for badge
POST /api/v1/alerts/{id}/read          — Mark alert as read
POST /api/v1/alerts/read-all           — Mark all as read

GET  /api/v1/monitors                  — List monitors for org
POST /api/v1/monitors                  — Create a monitor
PATCH /api/v1/monitors/{id}            — Update monitor (interval, active)
DELETE /api/v1/monitors/{id}           — Delete monitor
```

---

## Task 4: Organization Settings & Profile

**Location**: `/dashboard/settings`

### Organization Profile:
- Organization name (editable)
- Organization type
- Primary website URL
- Description
- Country
- Logo upload (optional)

### Team Management (Simple):
- Invite team members by email
- Team members see the same dashboard and scan history
- Roles: Admin (full control), Member (view + scan, no settings)
- For MLP: even just showing the org info is fine, full team management can be Phase 6

### User Profile:
- Name, email, password change
- Notification preferences (which alert types to receive)
- Theme: Dark/Light toggle

---

## Task 5: Vulnerability Tracking

### Vulnerability Lifecycle:
Track each unique vulnerability across scans:

```python
# When a scan completes:
# 1. For each finding, check vulnerability_history table
# 2. If this exact issue was found before (same check_type + same title + same URL):
#    - Update last_detected timestamp
#    - If was previously resolved → reopen it
# 3. If this is a new issue:
#    - Create new vulnerability_history record, status=open
# 4. For issues that were in previous scan but NOT in this scan:
#    - Mark as resolved, set resolved_at timestamp

# This gives us:
# - How long each vulnerability has been open
# - Which issues keep recurring
# - Resolution rate over time
```

### Vulnerability Dashboard (`/dashboard/vulnerabilities`):
- Table of all known vulnerabilities across scans:
  - Severity badge
  - Title
  - Status: Open / Resolved / Recurring
  - First detected date
  - Days open
  - URL affected
- Filters: by severity, by status, by check type
- Sort by: severity, age, status
- "Resolved" tab showing successfully fixed issues (celebration!)

---

## Task 6: Admin Panel (Basic)

**Location**: `/dashboard/admin` (ADMIN role only)

For platform administration:
- **Organization management**: List all registered orgs, verify civil society status
- **Scan statistics**: Total scans run, average scores, most common vulnerabilities
- **User management**: List users, change roles
- **Platform health**: Celery queue status, recent errors
- Simple table-based UI using shadcn components

---

## Backend Endpoints Summary:

```
# Dashboard
GET  /api/v1/dashboard/overview         — Score, summary, trends
GET  /api/v1/dashboard/trends           — Score history chart data

# Monitors
POST /api/v1/monitors                   — Create monitor
GET  /api/v1/monitors                   — List monitors
PATCH /api/v1/monitors/{id}             — Update
DELETE /api/v1/monitors/{id}            — Delete

# Alerts
GET  /api/v1/alerts                     — List alerts
GET  /api/v1/alerts/unread-count        — Unread count
POST /api/v1/alerts/{id}/read           — Mark as read

# Vulnerabilities
GET  /api/v1/vulnerabilities            — List vulnerabilities with status
GET  /api/v1/vulnerabilities/stats      — Vulnerability statistics

# Settings
GET  /api/v1/organization               — Get org profile
PATCH /api/v1/organization              — Update org profile
POST /api/v1/organization/members       — Invite team member
GET  /api/v1/organization/members       — List team members

# Admin
GET  /api/v1/admin/organizations        — List all orgs
PATCH /api/v1/admin/organizations/{id}  — Verify org
GET  /api/v1/admin/stats                — Platform stats
```

---

## Deliverables Checklist
- [ ] Security dashboard with score overview and trend chart
- [ ] Vulnerability summary cards (critical/high/medium/resolved)
- [ ] Monitoring system with configurable check intervals
- [ ] Celery Beat for automated periodic scans
- [ ] Alert system with in-app notifications
- [ ] Alert types: new_critical, ssl_expiring, score_dropped, etc.
- [ ] Notification bell with unread count
- [ ] Vulnerability lifecycle tracking (open → resolved → recurring)
- [ ] Vulnerability dashboard with filters and status
- [ ] Organization settings page
- [ ] Basic team management (invite by email)
- [ ] Scan comparison (previous scan vs current)
- [ ] Admin panel for org verification and platform stats
- [ ] All new API endpoints
