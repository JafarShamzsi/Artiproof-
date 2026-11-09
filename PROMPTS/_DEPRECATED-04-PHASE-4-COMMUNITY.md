# Phase 4 — Community & Pro Dashboard

## Context
Read `00-PROJECT-BRIEF.md` for full context. Phases 1-3 (foundation, scanner, education) are built. Now we build the community verification system and the professional dashboard for researchers/journalists.

## Objective
Build a community-driven fact-checking layer where users report, vote on, and discuss suspicious content. Also build the pro dashboard with analytics, bulk scanning, and advanced features for power users.

---

## Task 1: Community Hub

**Location**: `/dashboard/community`

### Community Feed:
- Reverse-chronological feed of community-submitted reports
- Each report card shows:
  - Submitter avatar + name (or "Anonymous")
  - Content preview (URL title or text snippet)
  - Time submitted ("2 hours ago")
  - Current community verdict: vote tally (e.g., "12 say Misleading, 3 say Credible, 5 say False")
  - Status badge: Pending / Under Review / Verified / Dismissed
  - Expert verification badge (if expert-verified, show checkmark + expert name)
  - "View Details" and "Vote" buttons
- Filters: All, Pending, Verified, My Reports
- Sort: Newest, Most Voted, Trending

### Submit a Report:
- Button: "Report Suspicious Content"
- Modal/page with:
  - URL input (optional)
  - Text description (required)
  - Category dropdown: News, Social Media, Image/Video, Health, Politics, Science, Other
  - "I already scanned this" toggle — link to existing scan results
  - Submit button
- After submission, auto-trigger a scan if not already scanned

### Report Detail Page (`/dashboard/community/[reportId]`):
- Full content display
- Linked scan results (if scanned) — embed the scan result card
- Community votes visualization (horizontal bar chart or pie chart)
- Vote buttons: "Credible" / "Misleading" / "False" (user can only vote once per report)
- Discussion thread (simple comments, chronological)
- Expert verification section (if verified)
- Related reports (similar content from DB)

### Voting System:
- One vote per user per report
- Can change vote
- Weight votes by user reputation:
  - New users: 1x weight
  - Users with >50 completed lessons: 1.5x weight
  - Users with >100 scans: 2x weight
  - Expert-verified users: 3x weight
- Show aggregated results as percentage bars

### Expert Verification:
- Users can apply for "Expert" status (journalist, researcher, academic)
- Experts get a verified badge
- Expert verdicts are displayed prominently on reports
- Admin approval required for expert status

---

## Task 2: Pro Dashboard

**Location**: `/dashboard/analytics` (Pro users only)

### Analytics Overview:
- **Personal Stats Cards:**
  - Total scans this month
  - Average threat score across scans
  - Most common DISARM techniques encountered
  - Sources scanned most frequently
  - Scans by verdict distribution (pie chart)

- **Trend Charts (recharts):**
  - Scans over time (line chart, last 30 days)
  - Threat score distribution (histogram)
  - DISARM techniques frequency (bar chart)
  - Top flagged sources (horizontal bar chart)

### Scan Comparison:
- Select 2-3 past scans and compare results side by side
- Highlight differences in engine verdicts
- Useful for tracking how a story evolves

### Export & Reports:
- Export scan results as PDF report (include all engine results, DISARM classification, threat score)
- Export scan history as CSV
- Export analytics data as CSV

### Bulk Scanning (Pro/Enterprise):
- Upload a CSV of URLs or claims (max 100 for Pro, unlimited for Enterprise)
- Queue all for processing
- Show progress dashboard
- Download results as CSV when complete

---

## Task 3: Notification System

### In-App Notifications:
- Bell icon in top bar with unread count badge
- Notification dropdown panel showing recent notifications
- Types:
  - "Your scan is complete" — click to view results
  - "Your report was verified by an expert"
  - "Someone voted on your report"
  - "New badge earned: [badge name]!"
  - "Your streak is at risk — complete a lesson today!"
  - "A claim you scanned was re-checked and the verdict changed"
- Mark as read / Mark all as read
- Notification settings page to toggle which types to receive

### Backend:
```
GET  /api/v1/notifications           — List user notifications (paginated)
POST /api/v1/notifications/read      — Mark notification(s) as read
GET  /api/v1/notifications/unread-count — Get unread count
```

Store notifications in a `notifications` table:
```
notifications: id, user_id, type, title, message, link, read, created_at
```

---

## Task 4: User Profiles & Settings

### Profile Page (`/dashboard/profile` or `/dashboard/settings`):
- Edit name, avatar (upload)
- View email (non-editable)
- Account type badge (Free / Pro / Enterprise)
- Change password
- Connected accounts (Google, GitHub — if OAuth set up)
- Delete account option

### Public Profile (`/profile/[userId]` — optional):
- Display name, avatar
- Member since date
- Badge showcase
- Stats: scans completed, lessons completed, community contributions
- Learning streak
- Recent activity (public scans only)

### Settings:
- Notification preferences (toggles per notification type)
- Privacy: Make profile public/private
- Theme: Dark/Light/System (implement theme toggle)
- Language (placeholder for future i18n)
- Subscription management (link to Stripe portal — Phase 6)

---

## Task 5: Search System

### Global Search:
- Search bar in dashboard top bar
- Searches across:
  - Scan history (by content text)
  - Community reports (by content text)
  - Claims database (by claim text)
  - Courses and lessons (by title)
  - DISARM techniques (by name/description)
- Results grouped by category
- Uses PostgreSQL full-text search (tsvector) for fast queries
- Consider adding pgvector semantic search for "fuzzy" matching

### Backend:
```
GET /api/v1/search?q=query&type=all|scans|reports|claims|education|disarm — Search endpoint
```

---

## Task 6: Admin Panel (Basic)

**Location**: `/dashboard/admin` (ADMIN role only)

- User management: list users, change roles, ban/unban
- Report moderation: review pending reports, verify/dismiss
- Expert applications: approve/reject
- Basic platform stats: total users, total scans, active reports, daily active users
- Content moderation queue

Simple table-based UI using shadcn DataTable pattern.

---

## Backend Endpoints Summary:

```
# Community
POST /api/v1/reports                    — Submit a report
GET  /api/v1/reports                    — List reports (paginated, filtered)
GET  /api/v1/reports/{id}               — Report detail
POST /api/v1/reports/{id}/vote          — Vote on a report
GET  /api/v1/reports/{id}/votes         — Get vote tallies
POST /api/v1/reports/{id}/verify        — Expert verification (experts only)
POST /api/v1/reports/{id}/comments      — Add comment
GET  /api/v1/reports/{id}/comments      — Get comments

# Analytics (Pro)
GET  /api/v1/analytics/overview         — Dashboard stats
GET  /api/v1/analytics/trends           — Chart data
GET  /api/v1/analytics/export/scans     — Export scans CSV
GET  /api/v1/analytics/export/report    — Export scan as PDF

# Bulk Scan (Pro/Enterprise)
POST /api/v1/scans/bulk                 — Submit bulk scan job
GET  /api/v1/scans/bulk/{jobId}         — Check bulk scan progress
GET  /api/v1/scans/bulk/{jobId}/results — Download bulk results

# Notifications
GET  /api/v1/notifications              — List notifications
POST /api/v1/notifications/read         — Mark as read

# Search
GET  /api/v1/search                     — Global search

# Admin
GET  /api/v1/admin/users                — List users
PATCH /api/v1/admin/users/{id}          — Update user role
GET  /api/v1/admin/reports              — Moderation queue
GET  /api/v1/admin/stats                — Platform stats
POST /api/v1/admin/experts/{id}/approve — Approve expert application
```

---

## Deliverables Checklist
- [ ] Community feed with report cards
- [ ] Report submission form
- [ ] Report detail page with scan results integration
- [ ] Voting system with weighted reputation
- [ ] Discussion comments on reports
- [ ] Expert verification UI
- [ ] Pro analytics dashboard with charts (recharts)
- [ ] Scan comparison feature
- [ ] Export (PDF reports, CSV)
- [ ] Bulk scanning interface
- [ ] Notification system (in-app)
- [ ] User profile and settings pages
- [ ] Dark/Light theme toggle
- [ ] Global search across all content
- [ ] Admin panel for moderation
- [ ] Notifications database table + endpoints
