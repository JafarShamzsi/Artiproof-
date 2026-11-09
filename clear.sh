#!/bin/bash
# Truncate all main tables in the Neon database. DESTRUCTIVE — use with care.
# Required env vars: NEON_HOST, NEON_USER, NEON_PASSWORD, NEON_DB
# Optional: NEON_PORT (default 5432)
set -euo pipefail

: "${NEON_HOST:?NEON_HOST not set}"
: "${NEON_USER:?NEON_USER not set}"
: "${NEON_PASSWORD:?NEON_PASSWORD not set}"
: "${NEON_DB:?NEON_DB not set}"
NEON_PORT="${NEON_PORT:-5432}"

CONN="host=$NEON_HOST port=$NEON_PORT dbname=$NEON_DB user=$NEON_USER password=$NEON_PASSWORD sslmode=require"

psql "$CONN" -c "TRUNCATE reports, coauthor_relations, citation_edges, publication_analyses, scraped_publications, researcher_profiles, citation_checks, ai_detection_results, claim_analyses, source_checks, sessions, accounts, users RESTART IDENTITY CASCADE;"
