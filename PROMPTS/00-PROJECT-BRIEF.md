# CivicGuards — Project Brief & Architecture

## Vision
CivicGuards is a **Cyber Security Shield for Civil Society** — a free, accessible platform that helps civil society organizations (NGOs, independent media, activists, community groups) in Azerbaijan assess their website security, discover vulnerabilities, and protect themselves from both cyber attacks and coordinated disinformation campaigns. Think of it as a friendly security consultant that any non-technical organization can use.

## Why This Matters
Civil society organizations in Azerbaijan are prime targets for cyber attacks and disinformation, but they can't afford professional security audits (€5,000–€50,000/year) or enterprise tools like Cloudflare Enterprise. CivicGuards fills this gap with a free, AI-powered platform that speaks their language — plain, actionable recommendations instead of technical jargon.

## Core Pillars
1. **The Security Scanner** — Automated website vulnerability assessment (SSL, headers, CMS, exposed endpoints, misconfigurations)
2. **The Misinfo Shield** — Detection of disinformation campaigns targeting an organization (domain spoofing, impersonation, content manipulation)
3. **The Report Engine** — Plain-language security reports with prioritized, step-by-step fix instructions
4. **The Monitoring Dashboard** — Ongoing security posture tracking and alerts when new vulnerabilities appear

## Target Users (Primary)
- **Civil society organizations in Azerbaijan**: NGOs, human rights groups, media outlets, community organizations
- **Non-technical staff**: Executive directors, communications managers, volunteers who manage websites
- **Secondary**: Journalists, researchers, small businesses in the region

## Tech Stack
- **Frontend**: Next.js 16+ (App Router), TypeScript, shadcn/ui, Tailwind CSS
- **Backend**: Python FastAPI (scanning engine), Next.js API routes (auth, user management)
- **Database**: PostgreSQL with pgvector extension (for misinformation similarity search)
- **AI**: Gemini API (report generation, misinfo analysis), Grok API (secondary analysis)
- **Security Tools**: OWASP ZAP (via API/CLI), Nuclei (template-based scanning), SSL Labs API, SecurityHeaders.com API
- **Auth**: NextAuth.js (credentials + OAuth)
- **Queue**: Redis + Celery (async scan processing)
- **ORM**: Prisma (Next.js side), SQLAlchemy (Python side)

## Database Schema Overview

### Core Tables
- `users` — id, email, name, password_hash, role (free/pro/admin), organization_name, organization_type, created_at
- `organizations` — id, name, type (ngo/media/activist/community/other), website_url, country, description, created_at
- `security_scans` — id, org_id, user_id, target_url, status (pending/scanning/completed/failed), overall_score (0-100, higher=safer), created_at
- `scan_results` — id, scan_id, check_type (ssl/headers/cms/ports/xss/sqli/misconfig/dns), severity (critical/high/medium/low/info), title, description, recommendation, raw_data, created_at
- `vulnerability_history` — id, org_id, check_type, severity, first_detected, last_detected, resolved_at, status (open/resolved/accepted)

### Misinformation Tables
- `misinfo_scans` — id, org_id, user_id, target_domain, status, threat_score (0-100), created_at
- `misinfo_findings` — id, scan_id, finding_type (domain_spoof/impersonation/content_manipulation/fake_social), severity, description, evidence_url, created_at
- `disarm_tactics` — id, tactic_id, name, description, phase
- `disarm_techniques` — id, technique_id, tactic_id, name, description, examples

### Monitoring Tables
- `monitors` — id, org_id, target_url, check_interval (daily/weekly), is_active, last_checked, created_at
- `alerts` — id, monitor_id, org_id, alert_type, severity, title, message, is_read, created_at

## Pricing (Hackathon / Grant Phase)
- **Free**: All core features free for civil society organizations in Azerbaijan (funded by EaP grant)
- **Post-Grant Sustainability**: Freemium model — free for NGOs, paid tiers for businesses and international orgs

## DISARM Framework Integration
For the misinformation module, CivicGuards classifies detected disinformation campaigns using the DISARM framework:
- **Phases**: Plan → Prepare → Execute → Assess
- Maps detected attacks to specific DISARM techniques
- Helps organizations understand HOW they're being targeted

## Hackathon Constraints
- **Budget**: €10,000–€12,000 for 6 months
- **Pitch**: 3.5 minutes + 1–1.5 min recorded demo of ONE key feature
- **Evaluation Criteria**: Relevance to objectives, target audience needs, impact, feasibility, sustainability
- **MLP Focus**: One killer feature (security scan) working perfectly > many half-built features

## Build Phases
1. Foundation + Landing Page (update existing)
2. Security Scanner Core (URL → vulnerability report)
3. Report Generation + Recommendations Engine
4. Dashboard + Monitoring + Alerts
5. Misinformation Detection Module
6. Sustainability + API + Scale
