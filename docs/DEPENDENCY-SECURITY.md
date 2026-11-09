# Dependency security: bounded queue slice

Assessment: 2026-11-06 UTC (2026-11-07 local). Issue #26,
`DEPENDENCIES-01`, device `axel-windows`. Source baseline:
`e1372a722b2f4e25ff38505238c62b93d0af49ad`.

**Not release clearance. Critical/high advisories remain.** This change only
upgrades the queue group, adds compatibility/exposure regressions and records
the advisory inventory. No application changes, frontend upgrades, advisory
ignores, gate changes, Dependabot merges, deployment or production access.
The manager-confirmed issue comment authorizes this slice over the older
backlog no-upgrade note. Independent exact-SHA review remains required.

## Queue decision and current primary sources

| Package | Baseline fresh resolution | New fresh resolution | Manifest range |
| --- | --- | --- | --- |
| Celery | 5.4.0 | 5.7.0 | `>=5.7.0,<5.8` with Redis extra |
| Kombu | 5.6.2 | 5.7.0 | `>=5.7.0,<5.8` with Redis extra |
| redis-py | 5.3.1 | 8.1.0 | `>=8.1.0,<8.2` |

Verified against current PyPI JSON metadata and upstream releases, not an old
Dependabot description. Celery 5.7.0 requires Kombu >=5.7.0; Kombu 5.7.0's
Redis extra requires redis-py >=6.4.0,<9.0.0 and packaging==26.3. All three
declare Python >=3.10. Minor-series caps intentionally prevent a later feature
release entering this bounded acceptance without review.

Primary sources inspected:

- [Celery v5.7.0 release](https://github.com/celery/celery/releases/tag/v5.7.0),
  published 2026-11-05; [stable documentation](https://docs.celeryq.dev/en/stable/)
  identifies 5.7.0 as current. However,
  [Celery SECURITY.md](https://github.com/celery/celery/blob/main/SECURITY.md)
  still lists only 5.4.x as supported. **Explicit security-policy coverage for
  5.7 is ambiguous**, not proven by the current-release label. Manager should
  obtain upstream clarification before public-launch support clearance.
- [Kombu SECURITY.md](https://github.com/celery/kombu/blob/main/SECURITY.md)
  explicitly supports 5.7.x, omits 5.6.x; omission was a maintenance uncertainty,
  not evidence of a vulnerability. [v5.7.0](https://github.com/celery/kombu/releases/tag/v5.7.0)
  published 2026-11-03.
- [redis-py v8.1.0](https://github.com/redis/redis-py/releases/tag/v8.1.0),
  published 2026-07-30, is the current stable release.
  [Upstream README](https://github.com/redis/redis-py/blob/master/README.md)
  documents Redis server >=7.2 support for recent clients and RESP3 as default
  since client 8.0, with legacy-compatible response shapes. This is not a
  promise of security backports for older clients. No SECURITY.md was found
  at repository root or `.github/SECURITY.md` (404); do not invent an LTS policy.
- Metadata: [Celery](https://pypi.org/pypi/celery/5.7.0/json),
  [Kombu](https://pypi.org/pypi/kombu/5.7.0/json),
  [redis-py](https://pypi.org/pypi/redis/8.1.0/json).

Celery upstream explicitly does not support Windows. Local Windows/Python
3.14.9 checks are supplementary; the existing Ubuntu/Python 3.12 hosted suite
is the real Redis/PostgreSQL acceptance authority. It uses `redis:7-alpine`;
actual server version must be read from hosted service logs rather than
assuming a particular patch from a floating image tag.

### Dependabot PR #9 reconciliation

Read its body, comments and diff. It only changes Celery's lower bound to
5.6.3 under the former `<6.0` range and retains redis-py `<6.0`, without the
current Kombu group constraint. It does not establish the coordinated transport
compatibility or resolve Kombu maintenance coverage. This lane supersedes that
proposal with the tested trio. Leave PR #9 unmerged; manager may close it as
superseded after reviewing this draft. Its missing-label warning is unrelated.

## Verification and reproducibility

Own environment, never the shared audit venv:
`C:/Users/Axel/AppData/Local/hermes/cache/scratch/dependencies-01/venv`.
Artifacts use the same scratch parent. No `.env` exists at the settings search
paths in this worktree; none was read. Provider keys, telemetry and email keys
were explicitly cleared in the test process. No local service was bound.

Commands use that environment's Python, from `backend` unless stated:

```text
python -m pip install -r requirements.txt -r requirements-dev.txt --report <scratch>/queue-install.json
python -m pip check
python -m pytest tests/test_queue_dependency_compatibility.py -q
python -m pytest -q --junitxml=<scratch>/unit.xml
python -m ruff check --select E9,F63,F7,F82 app
python -m pip_audit --format json --output <scratch>/queue-pip-audit.json
# From frontend, inventory only, no install or lockfile rewrite:
npm audit --json --package-lock-only
```

- Original two queue probes passed on baseline 5.4.0/5.6.2/5.3.1.
- New maintained-series regression failed on all three baseline versions
  (`3 failed, 2 passed`) before changing bounds, as intended.
- Deliberately invalid, separate `mismatch-venv`: install the old trio, then
  replace only Kombu with 5.7.0 using `pip install --no-deps kombu==5.7.0`.
  Calling the original probes without mocking reproduced both the Redis-extra
  metadata assertion and the real `kombu.exceptions.VersionMismatch` requiring
  redis-py >=6.1.0. This invalid environment is only a negative fixture, never
  an acceptance install; the accepted venv was not mutated by this experiment.
- New trio: full local backend **704 passed, 141 integration tests deselected**,
  3,886 warnings (notably Python 3.14/pytest-asyncio and existing datetime
  deprecations). `pip check` and required Ruff checks pass. Deselections are
  **not** integration acceptance. Native WeasyPrint is unavailable locally;
  the exposure call-boundary test uses a spy, not a native-renderer proof.
- Hosted CI must run the unchanged full backend suite, migrations and required
  integration list, including real Redis worker delivery, broker-failure retry,
  duplicate ownership, killed-worker recovery and terminal persistence. Existing
  zero-skip XML assertion remains intact. A green unit component alone is not
  acceptance. Exact SHA/run URLs/results belong in the PR/issue handoff.
- Frontend files are unchanged. Full frontend types/lint/unit/build/browser
  gates still run on the exact draft head in hosted CI; no local Node 26 result
  is substituted for the workflow's Node 22 result.

`test_dependency_security.py` protects the observed HMAC-only and PDF-resource
boundaries below. Those tests do not patch dependencies or prove every
configuration safe. Requirements are ranges, not a complete Python lockfile;
archive actual install reports with every acceptance run. Future resolutions
and platform-specific dependencies can differ.

### Observed hosted implementation checkpoint

Implementation head `937efe84229183d939ccfc55640078c657c075ee`:
[CI run 42287194417](https://github.com/JafarShamzsi/ArtiProof/actions/runs/42287194417)
completed successfully. This paragraph is a documentation-only follow-up;
final-head rerun and exact SHA are recorded in draft PR #39's handoff.

- GitHub checked out synthetic merge `eefe2e7` of that head with
  `e39cfdd6dcc0513aed55798a76fa425ed484921c`. Main had advanced only with
  manager coordination/docs/config since the assigned source baseline; no
  application, dependency or CI changes appeared in that base delta. This is
  PR-head-associated **combined-tree** evidence, not a standalone-head checkout
  or permission to merge another combined tree without review.
- Ubuntu, Python **3.12.16**: actual install log confirms Celery **5.7.0**,
  Kombu **5.7.0**, redis-py **8.1.0**, packaging **26.3**. Service log confirms
  Redis server **7.4.12**, inside redis-py's advertised supported server family.
- Backend: required Ruff, Alembic upgrade, **704 unit tests passed**, 141
  integration tests deselected in the unit command. The required named
  integration command then reports **139 passed, zero skips** and its XML
  zero-skip assertion passed. All 16 analysis-run cases passed, including
  `test_real_redis_delivery_runs_without_a_stream`, broker-failure retry,
  duplicate fencing and killed-worker recovery. Remaining two integration
  cases (`test_health_endpoint.py` and live artifact-storage integration) are
  outside that existing hosted list, **not acceptance established here**.
- Frontend: TypeScript, ESLint, production webpack build and **11 Playwright
  smoke tests passed**. Vitest **72 passed, 1 skipped**: existing opt-in
  `BUILD02_NETWORK_BUILD=1` network-denied font build contract is not enabled
  by routine CI. The normal production build passed; it is not that opt-in
  network-denial experiment.
- [Security run 42287194199](https://github.com/JafarShamzsi/ArtiProof/actions/runs/42287194199)
  passed its release-gate contracts and high-severity/high-confidence Bandit
  scan. [CodeQL run 42287194178](https://github.com/JafarShamzsi/ArtiProof/actions/runs/42287194178)
  reported **NOT SCANNED**, analysis skipped because licensing/enablement is
  unconfirmed. A successful availability job is not a clean CodeQL scan.
- Both advisory-only audit steps reported findings. Their wrapper success is
  not an audit pass. No workflow/gate was altered to produce this result.

## Audit method and interpretation

Inventory is a point-in-time advisory match, not a demonstrated exploit list.
Python: `pip-audit` against actual installed fresh baseline and upgraded
environments, including dev/scanner tools, using default PyPI advisory service.
Both report **7 records in 4 packages**, but **5 unique advisories**: ecdsa and
pytest each appear twice under the same ID. Do not count duplicates as new
vulnerabilities. Neither baseline nor upgraded scan reports a queue advisory.
The hosted workflow separately audits requirements via OSV; its scanner result
must not be conflated with this local inventory.

Cross-check using installed-environment OSV returns **10 records in 4 packages**;
hosted requirements-only OSV returns **8 records in 3 runtime packages** (pytest
excluded). OSV duplicates the WeasyPrint and ecdsa entries and merges the new
python-jose issue with historical PYSEC-2024-232 / GHSA-6c5p-j8vq-pqhj /
CVE-2024-33663. GitHub's reviewed historical advisory explicitly fixes that
older issue at 3.4.0, below installed 3.5.0. Preserve this scanner discrepancy;
do not claim a second independently confirmed old vulnerability or suppress
the new unpatched DER-key confusion. Raw scans are saved in scratch.

npm: lockfile-only scan (npm 12.0.2), unchanged committed package-lock, no
`npm audit fix`. **30 affected package entries: 4 critical, 11 high, 13 moderate,
2 low.** These are package aggregate severities, not 30 unique CVEs. Inherited
`via` findings are not additional independent advisories. Lockfile presence is
not proof every package ships to production. Runtime/dev classifications below
come from lockfile flags; actual deployed bundles/host configuration were not
inspected. All findings remain open unless explicitly described as absent from
the inspected configuration. No blanket suppression or risk acceptance.

Read-only GitHub Dependabot API cross-check: **96 open alerts**, all against
`frontend/package-lock.json`: 9 critical, 44 high, 37 medium, 6 low. Every
alert's GHSA ID is represented among the **85 unique direct npm advisory IDs**
in the inventory below; multiple dependency instances/ranges explain why
alert count is not unique-ID count or npm's 30 aggregate-package count.
No alerts were dismissed or closed. A fresh latest-allowed Python resolution
does not establish security of every older version permitted by the ranges,
nor of any existing deployment; other lower-bound tightening is deferred.

### Exposure priority (not a replacement for advisory severity)

1. **Frontend runtime, urgent manager follow-up:** Next 16.2.0 and sharp 0.34.5
   retain critical/high advisories. Normal Node configuration leaves image
   optimization enabled (`frontend/next.config.ts`); only static export disables
   it. Inspect input routing, SVG/AVIF acceptance and deployed OS before claiming
   exploitability. Windows-hosted Next RCE has an OS-specific precondition;
   local Windows development is not evidence production is Windows. The
   `next/og` attacker-controlled SVG and `use cache` typed-array preconditions
   were not found in inspected application sources, but upstream still urges
   upgrading. Middleware protection is used in `frontend/middleware.ts`;
   App Router bypass advisories therefore deserve targeted regression review.
2. **Untrusted PDF rendering, high priority:** pdfjs-dist 5.6.205 is used through
   `react-pdf` in `frontend/src/components/pdf-viewer.tsx` for uploaded PDFs.
   GHSA-hq66-cqwq-w95j requires scripting enabled and no blocking CSP. The
   component does not explicitly disable scripting; effective React-PDF/PDF.js
   defaults require verification. CSP defaults to Report-Only and permits
   unsafe script execution, so do not claim CSP mitigation. The worker is loaded
   from unpkg using `pdfjs.version`. Coordinate worker, viewer and React-PDF API
   compatibility; a blind direct-major bump is not authorized in this slice.
3. **Auth, critical advisory but bounded observed exposure:** next-auth uses
   credentials and optional Google, not email/magic-link provider, so the
   email-normalizer takeover precondition is absent in inspected configuration.
   Malformed-Bearer getToken DoS may remain reachable through middleware;
   provider-cookie binding matters if Google is enabled. Backend python-jose
   3.5.0 critical DER-key confusion requires asymmetric public-key material
   accepted as an HMAC key. Inspected JWT callers explicitly restrict algorithms
   and default to HS256 with JWT_SECRET, not asymmetric public-key verification.
   This reduces observed exposure but is not a package fix or validation of any
   deployed secret/configuration. Do not read production keys to investigate.
4. **Backend PDF, conditional high:** WeasyPrint 69.0 still has EPS/Ghostscript
   and resource-option advisories. `assets.py` only accepts embedded PNG bytes;
   `pdf_generator.py` supplies a restrictive fetcher and passes no stylesheets
   or xmp_metadata options. Tests preserve those boundaries. No native attack
   replay or deployed Ghostscript inventory was performed. ecdsa 0.19.2 timing
   issue affects signing/keygen/ECDH, not signature verification; inspected
   default auth uses HMAC, not ECDSA signing. No patched version is advertised.
5. **Build/dev tooling, still residual critical/high:** Vitest UI, tinypool,
   Vite/launch-editor, YAML/glob/CSS parsers need separate tooling work. Current
   scripts use `vitest run`/watch, not a published UI server; no public tooling
   listener was started. Attacker-controlled test config, worker options,
   source maps or repository content remain supply-chain/local preconditions.
   pytest's Unix temporary-directory issue does not reproduce on this Windows
   host; hosted runners are Unix. Do not mark it fixed merely because CI is
   ephemeral. Dev-only findings retain their published severity in this report.

### Python residual inventory

Each GHSA links to the reviewed advisory and upstream references. Severities
were checked through GitHub's advisory API; pip-audit itself does not emit them.

| Installed package | Severity | Advisory IDs | Fixed version / observed exposure |
| --- | --- | --- | --- |
| python-jose 3.5.0 | Critical | [GHSA-3qf3-8w2g-rqmx](https://github.com/advisories/GHSA-3qf3-8w2g-rqmx), CVE-2026-85394, PYSEC-2026-4298 | No fix listed; asymmetric-key/HMAC confusion precondition not found in default auth |
| ecdsa 0.19.2 | High | [GHSA-wj6h-64fc-37mp](https://github.com/advisories/GHSA-wj6h-64fc-37mp), CVE-2024-23342, PYSEC-2026-1325 | No fix planned; signing timing attack, HMAC default does not call ECDSA signing |
| WeasyPrint 69.0 | High | [GHSA-r543-q48m-4c9j](https://github.com/advisories/GHSA-r543-q48m-4c9j), CVE-2026-106443, PYSEC-2026-4311 | 70.0; EPS/Ghostscript interpreter input, restricted renderer fetcher boundary present |
| WeasyPrint 69.0 | Medium | [GHSA-jf6q-chmf-3h3v](https://github.com/advisories/GHSA-jf6q-chmf-3h3v), CVE-2026-55073, PYSEC-2026-3940 | 70.0; stylesheet/XMP option bypass, options not forwarded by app |
| pytest 8.4.2 (dev) | Medium | [GHSA-6w46-j5rx-g56g](https://github.com/advisories/GHSA-6w46-j5rx-g56g), CVE-2025-71176, PYSEC-2026-1845 | 9.0.3; Unix shared temporary directory, current `<9` excludes fix |

### npm residual inventory

All IDs below are GitHub advisory IDs, resolvable at
`https://github.com/advisories/<ID>` and through their upstream references.
For compactness `C/H/M/L` means published critical/high/moderate/low.
All remain in the unchanged lockfile. Suggested versions are audit candidates,
not verified compatible upgrades or a claim to cover future advisories.

| Package and locked version(s) | Scope / advisory IDs |
| --- | --- |
| next 16.2.0 | Runtime. C: GHSA-p293-qw3h-jr36 (Windows RCE), GHSA-2xp9-vwfh-vxw4 (AVIF), GHSA-vcvr-r3jv-pc5j (next/og), GHSA-2464-fhr4-w9xw (SVG), GHSA-673q-mjm6-r5xr (use cache). H: GHSA-267c-6grr-h53f, GHSA-26hh-7cqf-hhc6, GHSA-36qx-fr4f-26g5, GHSA-492v-c6pp-mqqv, GHSA-6gpp-xcg3-4w24 (middleware/proxy); GHSA-8h8q-6873-q5fj, GHSA-q4gf-8mx6-v5v3 (RSC DoS); GHSA-m99w-x7hq-7vfj, GHSA-p3m5-59mp-jv5r (Server Actions DoS); GHSA-mg66-mrh9-m8jx (cache exhaustion); GHSA-89xv-2m56-2m9x, GHSA-c4j6-fc7j-m34r, GHSA-cjq9-62q9-8jv4, GHSA-p9j2-gv94-2wf4 (SSRF). M: GHSA-4633-3j49-mh5q, GHSA-68g3-v927-f742, GHSA-4jqv-mc3x-m676, GHSA-mcj8-r9mp-w47p, GHSA-wfc6-r584-vfw7 (cache confusion/poisoning); GHSA-4c39-4ccg-62r3, GHSA-h64f-5h5j-jqjh, GHSA-q8wf-6r8g-63ch (DoS); GHSA-955p-x3mx-jcvp, GHSA-f87g-xv8r-7p7x (disclosure); GHSA-ffhc-5mcf-pf4q, GHSA-gx5p-jg67-6x7h (XSS). L: GHSA-39w2-rjm5-chcv (dev MCP disclosure), GHSA-3g8h-86w9-wvmq, GHSA-vfv6-92ff-j949 (cache poisoning). Also inherits postcss/sharp. Audit proposes 16.4.5; coordinate eslint-config-next. |
| next-auth 4.24.13 | Runtime. C GHSA-7rqj-j65f-68wh (email normalizer), H GHSA-xmf8-cvqr-rfgj (Bearer DoS), M GHSA-x445-f3h2-j279 (OAuth cookie binding); inherits uuid. Email provider absent; middleware/optional Google present. Candidate >=4.24.15 for the listed direct findings. |
| pdfjs-dist 5.6.205 | Runtime. H GHSA-hq66-cqwq-w95j; first patched 6.2.108 per audit range. Viewer/worker compatibility review required. |
| sharp 0.34.5 | Runtime through Next. H GHSA-f88m-g3jw-g9cj (libvips CVE-2026-33327/33328/35590/35591), GHSA-rgj7-g3m4-5g8c (libheif), GHSA-wq5f-xc86-pv6w (librsvg CVE-2026-96889). Candidate >=0.35.5; decoder/OS/input prerequisites apply. |
| postcss 8.4.31 (Next), 8.5.8 (dev) | Runtime dependency plus build tool. H GHSA-6g55-p6wh-862q, GHSA-r28c-9q8g-f849 (source-map file reads); M GHSA-fxqj-rqcc-2cmp (incomplete fix), GHSA-qx2v-qp2m-jg93 (CSS XSS). Hostile CSS/source maps required; audit ranges extend through 8.5.22. |
| source-map-js 1.2.1 | Runtime-marked CSS dependency. H GHSA-68fv-2mgg-jv7q (indexed-map DoS); candidate >=1.2.2; untrusted source-map ingestion not established. |
| nanoid 3.3.11 | Runtime-marked transitive. H GHSA-28wg-ghj8-5hjv, GHSA-2v37-7h3g-55p8, GHSA-xwg4-73v4-xw9w (invalid-size generator loops/overflow). No direct app call found; candidate >=3.3.18. |
| uuid 8.3.2 | Runtime through next-auth. M GHSA-w5hq-g745-h8pq (buffer bounds in v3/v5/v6). No direct app buffer API call found; candidate >=11.1.1 is a major transition. |
| fflate 0.8.2, nested three-stdlib 0.6.10 | Runtime. M GHSA-px8p-9vwx-vf98 applies to nested <0.6.11 only (malformed ZIP64 unzipSync hang). No user archive-to-unzipSync path established; do not flag 0.8.2 as affected by this range. |
| baseline-browser-mapping 2.10.9 | Runtime-marked transitive, browser-target tooling. M GHSA-w5vr-8v7q-w6rv (invalid-input termination), candidate >=2.11.0. Public-input path not established. |
| vitest 3.2.4 | Dev. C GHSA-5xrq-8626-4rwp (listening UI server, fixed 3.2.6); M GHSA-82fw-gwwq-j7x9 (mock path traversal, fixed 4.1.11); inherits tinypool/mocker. Current run script is not a public UI deployment. |
| tinypool 1.1.1 | Dev via Vitest. C GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr (prototype-polluted worker/run options to RCE), candidate >=2.1.2; malicious config/options prerequisite. |
| @vitest/mocker 3.2.4 | Dev. M GHSA-82fw-gwwq-j7x9, GHSA-qxg6-89mg-rqv8 (mock registration code injection); candidate >=4.1.12 for both. |
| vite 7.3.3 | Dev. H GHSA-587h-7wmj-h5pm (Windows launch-editor bypass). M GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-v6wh-96g9-6wx3 (launch-editor escaping/flags/NTLM), GHSA-fx2h-pf6j-xcff, GHSA-rq7h-c2jc-7f22 (filesystem boundaries). L GHSA-9jrq-w75r-8gcw (custom middleware script execution). Server exposure/config prerequisites; audit ranges through 7.3.6. |
| brace-expansion 1.1.12, nested 5.0.4 | Dev. H GHSA-3jxr-9vmj-r5cp, GHSA-mh99-v99m-4gvg (1.x expansion DoS), GHSA-6j4f-fj2g-mc7p, GHSA-qhr7-859c-m2p7, GHSA-rgw5-rvv9-x895 (5.x recursion/intermediate DoS). M GHSA-f886-m6hf-6m8v (1.x zero-step), GHSA-jxxr-4gwj-5jf2, GHSA-q2hr-2g5m-vwhr (5.x range/quadratic DoS). Hostile glob prerequisites; listed ranges need >=1.1.17 and >=5.0.12. |
| picomatch 2.3.1, nested tinyglobby 4.0.3 | Dev. H GHSA-c2c7-rcm5-vvqj (ReDoS), M GHSA-3v7f-55p6-f55p (method injection); candidate >=2.3.2 / >=4.0.4. |
| minimatch 10.2.4 | Dev. M GHSA-g3hv-75wg-m249 (globparts amplification); candidate >=11.0.1; compiler/lint dependency, no public glob input path established. |
| browserslist 4.28.1 | Dev. H GHSA-73wf-gq98-2v4g (custom-stats prototype write/crash), GHSA-c83g-rgw3-j3cx (query cache OOM). Audit ranges <=4.28.6; trusted build inputs reduce observed exposure. |
| js-yaml 4.1.1 | Dev. H GHSA-2883-xcg3-v3hh, GHSA-52cp-r559-cp3m, GHSA-5p4m-2wfm-xmqj; M GHSA-h67p-54hq-rp68 (YAML alias/merge/omap CPU DoS); candidate >=4.3.2. |
| zod 4.3.6 | Dev. H GHSA-mrhx-c7xc-m3w5 (oversized collection validation OOM), candidate >=4.6.6. No public application validation call to this npm instance established. |
| @babel/core 7.29.0 | Dev. L GHSA-4x5r-pxfx-6jf8 (sourceMappingURL file read), range <=7.29.0; hostile source-map comment prerequisite. |
| @humanfs/node 0.16.7 | Dev. M GHSA-p498-v437-472g (recursive copy follows symlinks), candidate >=0.16.8; hostile filesystem tree prerequisite. |
| esbuild 0.27.7 | Dev. L GHSA-g7r4-m6w7-qqqr (Windows dev-server arbitrary file read), candidate >=0.28.1; exposed dev server prerequisite. |
| @typescript-eslint/eslint-plugin, parser, type-utils, typescript-estree, utils 8.57.1; typescript-eslint 8.57.1; eslint-config-next 16.2.0 | Seven dev entries inherit YAML/glob advisories above; no distinct direct advisory objects in npm output. Do not count them as seven additional independent exploit paths or follow npm's suggested config downgrade blindly. |

## Next scope, rollout and rollback

Manager owns assignment and release decisions. Request a separately bounded
frontend runtime slice for Next/sharp plus auth and PDF compatibility, then a
tooling slice. Backend auth-library replacement/no-fix assessment and WeasyPrint
70 compatibility need their own scoped acceptance; they are not silently added
to this queue change. Confirm upstream Celery security coverage explicitly.

Before rollout (not authorized here), resolve and archive the exact full tree,
run hosted zero-skip PostgreSQL/Redis acceptance and independent exact-SHA
review. Do not use passing advisory-only CI steps as an audit clearance.
Keep broker private and JSON-only; no new serializers or message formats are
introduced. Redis-py 8's wire default changed, so test real worker delivery and
reconciliation, not just metadata or imports.

Rollback requires the manager to restore the previous three queue bounds as a
group and rebuild the previous reviewed environment. Do not downgrade just
redis-py under Kombu 5.7. No schema or persisted-data changes occur in this
slice. Drain/coordinate workers before any production version transition; no
rolling-upgrade or mixed-worker compatibility claim was tested here.

This is an AI-assisted dependency assessment, not a professional penetration
test or a guarantee of security. Deployment exposure and real attack paths
require independent verification; no production data or credentials were read.
