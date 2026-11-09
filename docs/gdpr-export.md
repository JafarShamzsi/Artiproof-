# GDPR data export — schema reference

The `GET /api/auth/me/export` endpoint returns a ZIP containing every
record we hold for the calling user. This document is the authoritative
description of what's in that ZIP, what each field means, and what is
**deliberately not included** (and why).

The endpoint covers **GDPR Article 20 — right to portability**. For
deletion (Article 17), see [gdpr-runbook.md](./gdpr-runbook.md).

## Endpoint

| | |
|---|---|
| Path | `GET /api/auth/me/export` |
| Auth | Bearer token required |
| Rate limit | 2 / hour / user |
| Response | `application/zip`, attachment |
| Filename | `artiproof-export-<user-id-prefix>-<YYYYMMDD>.zip` |

Implementation: `backend/app/routers/auth.py::export_user_data`.

## ZIP contents

```
README.txt
profile.json
source_checks.json
researcher_profiles.json
reports.json
sessions.json
```

Each JSON file is pretty-printed with `indent=2` for human inspection.
Encoding is UTF-8.

### profile.json

Top-level account record. Shape:

```json
{
  "id": "<uuid>",
  "email": "user@example.com",
  "full_name": "...",
  "institution": "..." | null,
  "role": "researcher" | "faculty" | "admin",
  "tier": "free" | "pro" | "team",
  "organization_id": "<uuid>" | null,
  "locale": "en",
  "created_at": "ISO-8601",
  "email_verified_at": "ISO-8601" | null,
  "notification_preferences": { ... },
  "analysis_preferences": { ... },
  "watchlist": [ { "researcher_id": "...", "added_at": "..." }, ... ]
}
```

The notification and analysis preference dicts are merged with the
server-side defaults (`DEFAULT_NOTIFICATION_PREFERENCES`,
`DEFAULT_ANALYSIS_PREFERENCES` in `backend/app/constants.py`) so the
export always represents the user's *effective* preferences, not just
the overrides they've explicitly set.

### source_checks.json

Array of every source check the user has ever submitted, **including
soft-deleted ones**. Each item:

```json
{
  "id": "<uuid>",
  "input_type": "url" | "text" | "document",
  "input_title": "...",
  "input_content": "...",
  "status": "pending" | "processing" | "completed" | "failed",
  "overall_credibility_score": 0.0-100.0,
  "ai_content_percentage": 0.0-100.0,
  "misinfo_claims_found": int,
  "score_breakdown": { ... },
  "model_metadata": { ... },
  "created_at": "ISO-8601",
  "completed_at": "ISO-8601" | null,
  "deleted_at": "ISO-8601" | null,
  "claims": [ {...}, ... ],
  "ai_detections": [ {...}, ... ],
  "citations": [ {...}, ... ]
}
```

`model_metadata` is the governance record — see
`backend/app/schemas/governance.py::ModelMetadata` for the full shape.
The salient fields for reproducibility are:

- `model_provider`, `model_name` — which LLM ran the analysis.
- `formula_version` — the scoring weight bundle.
- `prompt_version` + `prompt_hashes` — exact prompt revision used.
- `prompt_drift_detected` — true iff the live prompt hash diverged
  from the expected snapshot at analysis time. A 3-month-old analysis
  with `prompt_drift_detected=true` indicates the analysis ran during
  a window when prompts had been edited without a version bump (a
  governance failure on our side, captured here for honesty).

### researcher_profiles.json

Array of every researcher integrity analysis. Same governance shape as
above for `model_metadata`. Per-publication breakdown lives under
`publications[]`.

### reports.json

Generated-PDF report **metadata** only. The PDFs themselves are
re-generatable from the source records and are excluded to keep the
ZIP small. Each entry retains the share token so a previously-shared
report can be re-distributed without re-issuing.

### sessions.json

Every authentication session ever issued for the account, including
revoked ones. Used for the user's own audit of login history.

```json
{
  "id": "<uuid>",
  "user_agent": "Mozilla/5.0 ...",
  "ip_address": "...",
  "label": "...",
  "created_at": "ISO-8601",
  "last_used_at": "ISO-8601" | null,
  "revoked_at": "ISO-8601" | null
}
```

## Deliberately excluded

- **Generated PDFs.** Re-derivable from source records; would balloon
  archive size.
- **2FA backup codes (raw).** Stored as bcrypt hashes server-side;
  exporting hashes would leak no actual code but also serves no
  user purpose. The `totp_enabled` boolean is in the profile (via the
  derived API) but the codes themselves stay server-side.
- **Hashed password.** Never exported under any circumstance.
- **Other users' data, even from shared resources.** A team-tier
  user's export contains only rows they personally own. Cross-org
  reads happen through the dashboard, not through this export.
- **Server logs.** Application logs are aggregate and not
  attributable to a single user at the export grain.

## Operational notes

- Rate limited to 2/hour. A user double-clicking the export button
  gets one zip and a 429 on the second click; the rate-limit headers
  tell the UI when to retry.
- Building the zip is read-heavy (multiple queries per source check
  for child rows). For users with thousands of analyses we'll need to
  page or background the job — current scale stays in the synchronous
  path because the 99th-percentile user has < 200 records.
- The endpoint streams via `StreamingResponse` but buffers the full
  zip in memory. If individual exports exceed ~50 MB, switch to
  streaming the zip directly to `response.body` (see implementation
  note in the docstring).

## Changelog

- 2026-05-29 — added `sessions.json`, `analysis_preferences`,
  `organization_id`, `email_verified_at`, `watchlist`, plus
  governance fields (`prompt_version`, `prompt_hashes`,
  `prompt_drift_detected`) inside `model_metadata`. Rate-limited to
  2/hour.
- 2026-05-28 (initial) — profile, source_checks, researcher_profiles,
  reports.
