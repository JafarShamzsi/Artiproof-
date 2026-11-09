#!/bin/bash
# Remove placeholder researcher profiles that never got scraped.
# Required env vars: NEON_HOST, NEON_USER, NEON_PASSWORD, NEON_DB
# Optional: NEON_PORT (default 5432)
set -euo pipefail

: "${NEON_HOST:?NEON_HOST not set}"
: "${NEON_USER:?NEON_USER not set}"
: "${NEON_PASSWORD:?NEON_PASSWORD not set}"
: "${NEON_DB:?NEON_DB not set}"
NEON_PORT="${NEON_PORT:-5432}"

CONN="host=$NEON_HOST port=$NEON_PORT dbname=$NEON_DB user=$NEON_USER password=$NEON_PASSWORD sslmode=require"

psql "$CONN" << 'SQL'
DELETE FROM researcher_profiles WHERE official_h_index IS NULL AND researcher_name IN ('Yoshua Bengio', 'Yann LeCun', 'E. Jafarov', 'A. Maharramov');
SELECT researcher_name, official_h_index, official_citation_count, scrape_status FROM researcher_profiles;
SQL
