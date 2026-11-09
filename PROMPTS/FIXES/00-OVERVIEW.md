# ArtiProof — Fix Phases Overview

Run these prompts in order. Each phase builds on the previous one.

## Phase Order

| # | File | What It Fixes | Issues | Time Est. |
|---|------|--------------|--------|-----------|
| 1 | `01-SECURITY-FIXES.md` | Exposed credentials, auth bypass, privilege escalation, CORS | 16 issues | 30-45 min |
| 2 | `02-LANDING-PAGE.md` | Wrong pricing, fake stats, dead links, messaging, social proof | 15 issues | 45-60 min |
| 3 | `03-DATABASE-SCHEMA.md` | Migrations, indexes, enums, constraints, soft deletes | 12 issues | 30-45 min |
| 4 | `04-BACKEND-SERVICES.md` | Incomplete implementations, error handling, retry logic, scoring transparency | 30 issues | 90-120 min |
| 5 | `05-FRONTEND-CODE.md` | Type safety, memory leaks, error states, missing pages, UX gaps | 28 issues | 60-90 min |
| 6 | `06-ACCESSIBILITY.md` | ARIA labels, focus management, keyboard navigation, screen readers | 8 issues | 30-45 min |
| 7 | `07-INFRASTRUCTURE.md` | Docker, dependencies, config, deployment, logging, monitoring | 12 issues | 30-45 min |
| 8 | `08-TESTING.md` | Unit tests, integration tests, test infrastructure, fixtures | 9 issues | 60-90 min |
| 9 | `09-POLISH.md` | Code quality, documentation, cleanup, missing features | 6 issues | 30 min |

**Total: 136 issues across 9 phases**

## How To Use

1. Open Claude Code in the ArtiProof project
2. Copy-paste the contents of each phase prompt
3. Let Claude Code work through it
4. Verify the changes before moving to the next phase
5. Commit after each phase

## Important Rules (apply to ALL phases)

- Brand name: **ArtiProof** (NOT CivicGuards — old name)
- Brand color: Emerald `#10B981`
- Dark background: `#0a0a0a` / `#1A1A2E`
- Tech stack: Next.js 14+ (App Router), FastAPI, PostgreSQL, Redis, Tailwind CSS
- Frontend: `/frontend/src/`
- Backend: `/backend/app/`
- Do NOT break existing functionality while fixing
- Do NOT remove high-contrast mode CSS in `globals.css`
- Preserve all framer-motion animations on landing page
