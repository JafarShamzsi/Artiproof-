#!/bin/bash
# Print row counts for every main table after a full import.
# Required env vars: NEON_HOST, NEON_USER, NEON_PASSWORD, NEON_DB
# Optional: NEON_PORT (default 5432)
set -euo pipefail

: "${NEON_HOST:?NEON_HOST not set}"
: "${NEON_USER:?NEON_USER not set}"
: "${NEON_PASSWORD:?NEON_PASSWORD not set}"
: "${NEON_DB:?NEON_DB not set}"
NEON_PORT="${NEON_PORT:-5432}"

CONN="host=$NEON_HOST port=$NEON_PORT dbname=$NEON_DB user=$NEON_USER password=$NEON_PASSWORD sslmode=require"

psql "$CONN" -c "
SELECT 'users' as tbl, count(*) FROM users
UNION ALL SELECT 'source_checks', count(*) FROM source_checks
UNION ALL SELECT 'claims', count(*) FROM claim_analyses
UNION ALL SELECT 'ai_detections', count(*) FROM ai_detection_results
UNION ALL SELECT 'citations', count(*) FROM citation_checks
UNION ALL SELECT 'researchers', count(*) FROM researcher_profiles
UNION ALL SELECT 'publications', count(*) FROM publication_analyses
UNION ALL SELECT 'reports', count(*) FROM reports
ORDER BY tbl;"
