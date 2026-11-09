#!/bin/bash
# Import an ArtiProof SQL dump into a remote (Neon) Postgres database.
#
# Replaces the older import{,2,3,4}.sh which were iterations that fixed
# different cleanup quirks; this script collects every fix and is the
# single supported entry point.
#
# Required env:
#   NEON_HOST  NEON_USER  NEON_PASSWORD  NEON_DB
# Optional env:
#   NEON_PORT  (default 5432)
#   DUMP_FILE  (default /tmp/data-ordered.sql)
#
# Flags:
#   --no-truncate   Skip the TRUNCATE step (use for fresh-DB initial loads)
#   --dump=PATH     Override DUMP_FILE without exporting an env var
#
# What it does:
#   1. (default) TRUNCATE all known tables with CASCADE + identity reset.
#   2. Strip lines that need superuser (DISABLE/ENABLE TRIGGER, SET SESSION
#      AUTHORIZATION) — Neon doesn't grant those, and pg_dump emits them by
#      default.
#   3. Run psql with ON_ERROR_STOP=1 so any failure aborts immediately.
#   4. Print row counts for every table so you can verify the load.

set -euo pipefail

NO_TRUNCATE=0
for arg in "$@"; do
  case "$arg" in
    --no-truncate) NO_TRUNCATE=1 ;;
    --dump=*)      DUMP_FILE="${arg#--dump=}" ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | sed 's/^# \?//; $d'
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 2
      ;;
  esac
done

: "${NEON_HOST:?NEON_HOST not set}"
: "${NEON_USER:?NEON_USER not set}"
: "${NEON_PASSWORD:?NEON_PASSWORD not set}"
: "${NEON_DB:?NEON_DB not set}"
NEON_PORT="${NEON_PORT:-5432}"
DUMP_FILE="${DUMP_FILE:-/tmp/data-ordered.sql}"

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "Dump file not found: $DUMP_FILE" >&2
  exit 1
fi

CONN="host=$NEON_HOST port=$NEON_PORT dbname=$NEON_DB user=$NEON_USER password=$NEON_PASSWORD sslmode=require"

if [[ "$NO_TRUNCATE" -eq 0 ]]; then
  echo "Truncating tables..."
  psql "$CONN" -c "TRUNCATE \
    reports, \
    coauthor_relations, citation_edges, publication_analyses, scraped_publications, researcher_profiles, \
    citation_checks, ai_detection_results, claim_analyses, source_checks, \
    sessions, accounts, users \
    RESTART IDENTITY CASCADE;"
fi

CLEAN="$(mktemp -t artiproof-import-clean.XXXXXX.sql)"
trap 'rm -f "$CLEAN"' EXIT

echo "Sanitizing $DUMP_FILE -> $CLEAN ..."
sed -e '/DISABLE TRIGGER ALL/d' \
    -e '/ENABLE TRIGGER ALL/d' \
    -e '/SET SESSION AUTHORIZATION/d' \
    "$DUMP_FILE" > "$CLEAN"
echo "Lines: $(wc -l < "$CLEAN")"

echo "Importing..."
psql "$CONN" -v ON_ERROR_STOP=1 -q -f "$CLEAN" | tail -10

echo
echo "=== Row counts ==="
psql "$CONN" -c "
  SELECT 'users'                  AS tbl, count(*) FROM users
  UNION ALL SELECT 'source_checks',         count(*) FROM source_checks
  UNION ALL SELECT 'researcher_profiles',   count(*) FROM researcher_profiles
  UNION ALL SELECT 'scraped_publications',  count(*) FROM scraped_publications
  UNION ALL SELECT 'citation_edges',        count(*) FROM citation_edges
  UNION ALL SELECT 'coauthor_relations',    count(*) FROM coauthor_relations
  UNION ALL SELECT 'publication_analyses',  count(*) FROM publication_analyses
  UNION ALL SELECT 'reports',               count(*) FROM reports
  ORDER BY tbl;
"
