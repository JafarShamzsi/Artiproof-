# ArtiProof Platform Recommendations

Full analysis of what's missing, what's weak, and what to build next — across dashboard, settings, backend, and product-wide UX.

---

## 1. Settings Page — What's Missing

The current settings page has only two sections: a basic profile editor (name, institution) and a high-contrast toggle. For a SaaS platform, this is skeletal.

### Must-Have Settings

**Notification Preferences** — The page literally has a TODO comment saying "restore once the backend has a notification-prefs API." Build it. Users need toggles for: email on analysis complete, email on low-credibility alert (score < 40), weekly digest of activity, and report shared/downloaded notifications.

**Usage & Limits Dashboard** — Free users get 10 checks/month. There's zero visibility into how many they've used. Add a usage bar showing "7 of 10 checks used this month" with a reset date. Link to upgrade when approaching the limit.

**API Key Management** — If you want institutional adoption, researchers and IT admins will want API access. Add a section for generating, viewing (masked), and revoking API keys.

**Password & Security** — The auth router has no password reset flow, no email verification, and no two-factor auth. The settings page needs: change password, enable 2FA (TOTP), manage active sessions (list devices, revoke), and email verification status.

**Data Export** — GDPR and institutional compliance require users to export their data. Add a "Download my data" button that packages all source checks, researcher analyses, and reports into a ZIP.

**Account Deletion** — Same compliance reason. Add a "Delete my account" flow with confirmation and a grace period.

**Language & Locale** — You're targeting Azerbaijan first. Add language selection (Azerbaijani, English, Russian at minimum) and date format preferences.

**Theme Preference** — The app supports dark/light mode via system preference, but there's no manual override in settings. Add a three-way toggle: Light / Dark / System. The high-contrast toggle should stay separate.

### Nice-to-Have Settings

- Default analysis options (e.g., always check citations, preferred AI detection model)
- Connected accounts (Google OAuth status, link/unlink)
- Keyboard shortcut reference panel

---

## 2. Dashboard Page — What's Missing

### Data & Filtering

**Date Range Filter** — The trend chart is hardcoded to 30 days. Add a date picker: 7d / 30d / 90d / All time. The backend `/trends` endpoint needs a `days` query param.

**Search & Filter on Activity** — The recent activity list shows the last 10 items with no filtering. Add: search by title, filter by type (source check vs researcher), filter by status (completed/failed/processing), sort by date or score.

**Usage Limits Widget** — Free-tier users have no idea they're about to hit their cap. Show a small card: "3 checks remaining this month · Resets May 31 · Upgrade to Pro."

### Missing Dashboard Widgets

**Integrity Score Distribution** — A histogram or pie showing how many checks scored High (70-100), Medium (40-69), Low (0-39). Gives a quick sense of the quality of sources you've been checking.

**Top Flagged Issues** — A summary card showing the most common problems across all checks: "AI content detected in 12 checks, 8 retracted citations found, 3 citation rings flagged."

**Pinned / Starred Items** — Let users pin important checks or researcher profiles to the dashboard for quick access.

**Team Activity Feed** — For institutional accounts, show activity from team members (with privacy controls).

### UX Improvements

**Welcome / Onboarding Flow** — New users land on an empty dashboard with zero guidance. Add a first-run experience: welcome message with user's name, 3-step guide (check a source, analyze a researcher, generate a report), dismissible progress tracker.

**Quick Search (Command Palette)** — `Cmd+K` / `Ctrl+K` to search across all checks, researchers, and reports. This is standard in modern SaaS (Linear, Notion, Vercel). No backend endpoint for global search exists yet.

**Toast Notifications** — The settings page uses inline "Saved!" text. Replace with a toast/snackbar system for all success/error feedback across the app.

---

## 3. Source Check Page — What's Missing

**Bulk Checks** — Users can only submit one URL/text/PDF at a time. Add a bulk mode: paste multiple URLs (one per line) or upload multiple PDFs. Queue them all and show a batch progress view.

**Check History Search** — The "Past Source Checks" list loads all items with no search, filter, or pagination controls. Add: search by title/URL, filter by score range, filter by status, sort options, and proper pagination with page numbers.

**Re-run Analysis** — No way to re-analyze a source with updated models or after content changes. Add a "Re-check" button on completed results.

**Comparison View** — Let users compare two source check results side-by-side. Useful for checking the same article from different sources.

**Shareable Check Links** — Reports have share tokens, but individual source checks don't. Add shareable read-only links for checks (not just full PDF reports).

**Export Results** — No way to export check results as CSV, JSON, or PDF without generating a full report. Add lightweight export options.

---

## 4. Researcher Analysis Page — What's Missing

**Researcher Comparison** — No way to compare two researchers side-by-side. Useful for hiring committees or editorial boards evaluating reviewers.

**Watchlist** — Let users add researchers to a watchlist and get notified when their metrics change significantly (new publications, integrity score shifts).

**Batch Analysis** — Upload a CSV of researcher identifiers and analyze them all. Essential for institutional use cases.

**Historical Tracking** — Re-analyzing a researcher overwrites the previous analysis. Keep a history so users can track integrity changes over time.

---

## 5. Reports Page — What's Missing

**Report Templates** — Only one report format exists. Add templates: executive summary (1-page), full detailed report, comparison report (multiple sources), and institutional audit report (multiple researchers).

**Scheduled Reports** — Weekly or monthly automated reports summarizing all checks and analyses. Email delivery.

**Report Annotations** — Let users add notes or comments to generated reports before sharing.

**Branding / White-label** — Institutional customers need reports with their logo and branding, not ArtiProof's.

---

## 6. Backend & Infrastructure Gaps

### Security (Critical)

**SSE Endpoints Are Unauthenticated** — Both `/api/source-check/{id}/stream` and `/api/researcher/{id}/stream` have no auth. The code comments explicitly flag this as "phase 5" security debt. Anyone with a check ID can connect and even force pipeline re-runs. Fix by: migrating frontend to `@microsoft/fetch-event-source` (supports Authorization headers) or using signed short-lived query-param tokens.

**No Password Reset** — The auth router has register, login, and Google OAuth, but zero password recovery flow. Users who forget their password are locked out.

**No Email Verification** — Users can register with any email without verifying ownership. This enables impersonation.

**No Rate Limiting on Analysis Endpoints** — Auth routes are rate-limited (3-5/min), but source check and researcher analysis endpoints have no limits. A bad actor could drain your API credits by submitting hundreds of analyses.

### Data Integrity

**No Concurrent Task Guard** — If two SSE connections open for the same check, the pipeline can run twice simultaneously. Add a distributed lock (Redis-based) to prevent duplicate runs.

**Ephemeral File Storage** — PDF files are stored on Railway's filesystem, which resets on deploy. The code handles this by regenerating on miss, but it's fragile. Move to S3/R2 for persistent file storage.

**Soft-Delete Janitor Missing** — Soft-deleted records (source checks, researchers, reports) are never hard-deleted. No janitor/cleanup job exists. Implement a scheduled task to purge records older than 30 days and their associated files.

### API Quality

**No API Versioning** — All endpoints are unversioned (`/api/source-check/`). Add `/api/v1/` prefix now before you have external consumers.

**No OpenAPI Documentation** — FastAPI generates Swagger docs automatically, but there's no evidence it's enabled or accessible. Expose `/docs` and `/redoc` for developer onboarding.

**No Webhook Support** — Institutional integrations need webhooks for "analysis completed" events. Add a webhook registration endpoint and fire events on status changes.

**Inconsistent Pagination** — Source checks return `{ items: [...] }` but researchers return a flat array. Standardize on `{ items, total, page, per_page }`.

---

## 7. Product-Wide UX Gaps

### Navigation & Discovery

**No Breadcrumbs on All Pages** — The check result page has breadcrumbs, but other pages don't. Add consistent breadcrumb navigation across all detail pages.

**No Global Search** — No way to search across all checks, researchers, and reports from one place. Build a command palette (`Cmd+K`).

**No Keyboard Shortcuts** — Beyond `Alt+H` for high contrast, there are no keyboard shortcuts. Add: `Cmd+K` for search, `Cmd+N` for new check, `Cmd+,` for settings.

**Sidebar Badge Counts** — The sidebar shows static labels. Add live counts: "Reports (3)" or a notification dot on "Dashboard" when there are unread alerts.

### Feedback & Communication

**No In-App Help** — No tooltips, no help center link, no onboarding tooltips, no contextual help. Add a `?` icon that links to docs or shows inline guidance.

**No Feedback Channel** — No way for users to report bugs or request features from within the app. Add a feedback widget.

**No Changelog / What's New** — No way to communicate product updates to users. Add a changelog accessible from the navbar.

### Accessibility Gaps

**Focus Management** — The `main` content area has `tabIndex={-1}` but there's no skip-to-content link in the layout. Add one.

**Score Colors Alone** — Credibility scores use red/amber/green colors as the primary indicator. Add text labels (High/Medium/Low) alongside colors for colorblind users. The `ScoreLabel` component exists but isn't used everywhere.

**Mobile Sidebar** — The Sheet component works for mobile nav, but there's no swipe-to-open gesture. Add it for better mobile UX.

---

## 8. Missing Product Pages

**Admin Panel** — No admin interface exists. Admins have a role in the user model but no special UI. Build: user management (list, role changes, suspend), system-wide analytics (total users, checks, API usage), and content moderation tools.

**Team / Organization Management** — No concept of teams or organizations in the data model. For institutional pricing, you need: org creation, member invites, role-based access, shared check history, and usage pooling.

**Billing & Subscription** — No billing page, no Stripe integration, no plan management. The pricing page promises Free/Pro/Institution tiers but there's no enforcement. Build: plan selection, payment method management, invoice history, and usage-based billing enforcement.

**Public Profile Pages** — Researcher integrity scores could be made public (opt-in) with a shareable profile page showing verified metrics. Good for academic transparency.

**API Documentation Page** — If you offer API access, you need a developer portal with docs, code examples, and API key management.

**Status Page** — No uptime monitoring or status page. Important for institutional trust.

---

## 9. Priority Ranking

### P0 — Before Hackathon Demo
1. Usage limits visibility (free tier counter)
2. Fix unauthenticated SSE endpoints
3. Add password reset flow
4. Onboarding flow for new users
5. Toast notification system

### P1 — Before Launch
6. Notification preferences in settings
7. Theme toggle in settings (Light/Dark/System)
8. Global search (Cmd+K)
9. Check history search & filtering
10. Rate limiting on analysis endpoints
11. Email verification
12. Billing & subscription enforcement

### P2 — Growth Features
13. Bulk source checks
14. Researcher watchlist
15. Team/organization management
16. API key management
17. Report templates
18. Data export (GDPR)
19. Webhook support

### P3 — Polish
20. Keyboard shortcuts
21. Comparison views (sources & researchers)
22. Scheduled reports
23. Admin panel
24. Public researcher profiles
25. Changelog / What's New
26. Language & locale support
