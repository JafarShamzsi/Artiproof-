# UX-01: mobile landing measurement and bounded usability fixes

References #33. Agent: UX-01. Device: axel-windows. Local evidence date:
2026-11-06 UTC. This is not a deployment or launch-readiness sign-off.

## Scope and source identity

- Baseline: `e1372a722b2f4e25ff38505238c62b93d0af49ad`, also the fetched
  `origin/main` at start. Assigned branch: `agent/ux-01/pilot-readiness`.
- Later fetched main `e39cfdd6dcc0513aed55798a76fa425ed484921c` adds only manager
  coordination/docs/config, with no frontend runtime/assets change. It was read,
  not merged into this lane. Manager owns combined-tree integration/review.
- Regression/measurement commit: `ac14041402949c0b90ebb0ad765a59213718e429`.
- Only the cookie component changes product behavior. Comparison, application
  layouts, CSS, fonts, licenses, manifests, dependencies, CI and auth are unchanged.
- Exact final head, hosted checks and independent-review status belong to the
  draft PR and issue handoff, not a self-referential commit hash in this file.

## Reproduction and isolation

Use this worktree's own `frontend/node_modules` (`npm ci --no-audit --no-fund`).
No dependency links, global installs, backend, database, Redis, provider calls,
existing credentials or `.env` files were needed. Port 3204 was checked unused
before binding on `127.0.0.1`; only this lane's server is stopped afterward.

PowerShell, from the repository root (build and server commands from `frontend`):

```powershell
$scratch = 'C:/Users/Axel/AppData/Local/hermes/cache/scratch/ux-01'
$env:PLAYWRIGHT_BROWSERS_PATH = "$scratch/browsers"
# From frontend: npx playwright install chromium
# From frontend: npm run build
# From frontend: npm run start -- --hostname 127.0.0.1 --port 3204
$env:UX_BASE_URL = 'http://127.0.0.1:3204'
$env:UX_OUTPUT = "$scratch/baseline-normal" # use a new directory per build
node scripts/ux_measure/measure.cjs
node scripts/ux_measure/summarize.cjs "$env:UX_OUTPUT/report.json"
$env:UX_OUTPUT = "$scratch/usability" # separate from performance artifacts
node scripts/ux_measure/inspect.cjs
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:3204'
$env:PLAYWRIGHT_NO_WEBSERVER = '1'
# From frontend, with an external output directory:
# npx playwright test e2e/ux-mobile.spec.ts --workers=1 --output=<scratch>/results
```

Do not reuse a server while rebuilding its `.next` tree. Stop the lane-owned
server first, build once, then restart. Build and frontend checks must not overlap
performance measurement. Initial `baseline/` was a harness shakedown with reduced
motion and overlapping inspection; it is **excluded from timing acceptance**.
`baseline-normal/` is the sequential normal-motion baseline.

### Measurement method and limitations

- Windows, Intel Core Ultra 7 155U (14 logical CPUs), Node 26.13.0,
  Next 16.2.0 production server, Playwright 1.60.0 Chromium
  148.0.7778.96. CSS viewports 375x900 and 1440x900, DPR 1, light scheme,
  normal motion. These are controlled browser widths, not physical mobile devices.
- Three cold navigations per width/profile. Fresh isolated context each time,
  no cookies/storage/service workers, CDP HTTP cache disabled, same-origin only
  request routing. Server/OS caches remain warm; this is browser-cold, not a
  cold server, DNS, CDN, TLS or mobile-radio experiment.
- Native profile has no artificial throttling. `slow4g-cpu4` uses supported CDP
  network emulation: 150ms latency, 1,600,000 bit/s download, 750,000 bit/s upload,
  and CPU slowdown 4x. This is lab emulation, not a calibrated handset.
  No builds/tests in this lane overlap timing runs; system-wide idle state and
  other lanes' host load were not controlled. Small timing differences are not
  causal proof.
- Observe before navigation with buffered `PerformanceObserver` entries, then
  wait for load, `document.fonts.ready`, and another 10 seconds without input or
  scrolling. LCP is the last observed candidate, not field p75. CLS uses the
  maximum session window (gaps strictly below 1000ms and spans strictly below
  5000ms; exact boundaries reset), excluding recent-input entries.
  Raw candidates, shifts, timestamps and supported entry types are retained.
- Supported but zero shifts means **zero observed during that window only**.
  Unsupported LCP/CLS is `null`, never zero. Prior Firefox acceptance did not
  measure CLS; its CLS remains unknown. This does not measure full-lifetime CLS,
  interaction/scroll shifts, INP, real Safari/Firefox timing or field performance.
- The runner records resource timing plus CDP `Network.loadingFinished` values.
  `decodedBodySize` is decompressed content, **not wire transfer**.
  `encodedBodySize` is the compressed response-body payload. Resource Timing
  `transferSize` includes Chromium's header accounting, not packet capture.
  CDP encoded response transfer is a separate browser-reported HTTP-level count.
- An independent Node `http` probe does not decompress and counts actual gzip
  response-body chunks. This verifies encoded payload lengths independently, but
  is a **separate request**, not a browser packet capture. It excludes headers,
  HTTP chunk framing and TCP/IP. Packet-level wire totals, retransmissions,
  target Linux/CDN compression and real-device conditions remain unmeasured.

## Font delivery

The baseline requested five same-origin TTFs, all HTTP 200, gzip/chunked, with no
disk cache or service-worker hits. Browser encoded body totals match independent
raw HTTP probes. These are current measured sizes, **not a demonstrated regression**.

| Font | Decoded bytes | Gzip response-body bytes |
|---|---:|---:|
| Inter | 876,576 | 468,926 |
| Fraunces normal | 360,440 | 250,444 |
| Fraunces italic | 414,904 | 299,345 |
| Newsreader italic | 495,684 | 307,771 |
| JetBrains Mono | 187,208 | 91,326 |
| **Total** | **2,334,812** | **1,417,812** |

Do not describe 2,334,812 as bytes downloaded over the wire. Exact per-run
browser transfer accounting, preload observations and timing results are in
`report.json`; summarized results and final verification follow in the handoff.

Baseline Turbopack browser font accounting was 1,419,312 Resource Timing transfer
bytes (including its header accounting), and 1,423,033–1,423,077 CDP encoded
response-transfer bytes. Neither is a TCP packet-byte total. The compressed body
total was exactly 1,417,812 on every run and all five independent raw probes.

### Baseline timing samples (Turbopack, normal motion)

Each bracket lists all three runs, not confidence intervals. Units: LCP ms;
CLS unitless. No sample is discarded.

| Profile | CSS width | LCP samples (median) | Observed CLS samples |
|---|---:|---|---|
| Native | 375 | 1336, 1248, 1256 (1256) | 0, 0, 0 |
| Native | 1440 | 1548, 1520, 1428 (1520) | 0, 0, 0 |
| Slow4G/CPU4 | 375 | 10996, 10956, 11976 (10996) | .004763, .004763, .004763 |
| Slow4G/CPU4 | 1440 | 12340, 11712, 11796 (11796) | .2519996, .011187, .011187 |

Observation ended about 10.2s after navigation on native and 19.7–20.2s on the
slow profile (load/fonts readiness precedes the extra 10s). The last observed LCP
candidate is hero explanatory text at 375px and illustrative report text at 1440px.
The .252 desktop CLS sample is retained, not hidden behind the .011 median. Its
sources are hero DIVs; this lane does not establish font loading as the sole cause.

This Turbopack build produced **five DOM font preload links**, no HTTP Link header,
and manifest entries for five fonts per application page. Prior BUILD-02 acceptance
used webpack and reported no font preloads. These are different build conditions,
not evidence that the cookie edit changes preloading. The CI command explicitly
uses webpack; its verification must be labeled separately from the paired
Turbopack baseline/fix comparison.

### Cookie-fix timing samples (same Turbopack build mode)

Product source: `09dc0de4fd14aca4a02ebfbd3eb6f48781d9ebcd`. Subsequent test/script
and documentation adjustments do not change the built product components.

| Profile | CSS width | LCP samples (median) | Observed CLS samples |
|---|---:|---|---|
| Native | 375 | 1360, 1244, 1244 (1244) | 0, 0, 0 |
| Native | 1440 | 1452, 1472, 1680 (1472) | 0, 0, 0 |
| Slow4G/CPU4 | 375 | 13016, 12824, 10804 (12824) | .004763, .004763, .004763 |
| Slow4G/CPU4 | 1440 | 11292, 11008, 11720 (11292) | .011187, .011187, .011187 |

All font body/transfer totals and preload counts stayed the same. No page errors,
console errors, failed requests or blocked external requests occurred in the fixed
measurement runs. Baseline collected page errors but not console errors, so there
is no baseline-console-error claim.

**Concern, not an optimization success:** slow-profile mobile LCP median rose
10,996 to 12,824ms (+1,828ms, +16.6%). Three-run ranges overlap and are noisy;
these samples do not isolate a causal effect of the three cookie class changes.
The >500ms increase deserves follow-up, not a blanket performance-pass claim.
Likewise, absence of the baseline .252 CLS outlier after the fix does not prove
that cookie styles fixed hero shifts. Fonts/layout remain a separate acceptance
gate regardless of these local functional passes.

### Fixed webpack delivery, separate build condition

Build ID `4vimLTIL6KHzSlXGMX5Aq`, same product source
`09dc0de4fd14aca4a02ebfbd3eb6f48781d9ebcd`. This is the build mode selected by CI,
but these timings are still **local Windows**, not hosted Linux timing evidence.

| Profile | CSS width | LCP samples (median) | Observed CLS samples |
|---|---:|---|---|
| Native | 375 | 1508, 1416, 1472 (1472) | .007627, .007627, .007627 |
| Native | 1440 | 2256, 1876, 1876 (1876) | .019913, .019913, .019913 |
| Slow4G/CPU4 | 375 | 6712, 4884, 8176 (6712) | .012069, .012069, .038635 |
| Slow4G/CPU4 | 1440 | 5496, 11428, 10376 (10376) | .020621, .011187, .051682 |

All 12 navigations requested the same five gzip TTF bodies: encoded 1,417,812
bytes, decoded 2,334,812 bytes, Resource Timing transfer 1,419,312 bytes. CDP encoded
response-transfer totals ranged 1,423,017–1,423,077 bytes. All five independent
raw HTTP probes matched the body sizes above. No page/console errors, failed
requests or attempted external requests were recorded. All real font faces loaded.

Webpack emitted **zero DOM font preload links**, no HTTP Link header, and empty
`app`/`pages` font manifest maps, reproducing the earlier delivery observation.
Do not combine these samples with Turbopack to claim a cookie-caused speedup or
regression. On the slow profile, some last LCP candidates retain fallback-era
text bounds before final fonts settle; LCP alone does not certify final typography.
Observation ends 10.4–11.0s on native and 20.1–21.4s on slow runs. All raw shifts
remain available; neither these nonzero scores nor prior unsupported Firefox
measurement may be replaced with a "zero CLS" assertion.

Font assets are read-only. `scripts/ux_measure/font_inventory.py` records hashes,
file lengths and cmap coverage for `ƏəĞğİıÖöŞşÇçÜü` using fontTools from an
existing scratch venv. No conversion, subsetting or glyph changes are authorized.
All five cmap checks passed with no missing listed characters. An initial attempt
failed only while printing Unicode to Windows cp1252; ASCII-escaped JSON output
fixed the measurement script, and the rerun passed without modifying any font.

## Local verification record

Commands below ran from `frontend` unless noted. No concurrent production builds
ran in this worktree.

| Command | Actual result / evidence |
|---|---|
| `npm ci --no-audit --no-fund` | Passed; independent local dependency directory, no links |
| `npm run build` before/after fix | Turbopack production builds passed |
| `npx playwright test e2e/ux-mobile.spec.ts --workers=1` | Baseline 8 pass/3 fail, fixed Turbopack 11 pass; no skips |
| `npx playwright test --workers=1 --reporter=list,json` against webpack production | **22 pass, no skips/retries/flaky cases**; includes 11 UX checks and existing anonymous smoke checks |
| `npm run test:unit` | Initial 74 pass/1 explicit opt-in build skip, not 75 passes |
| `BUILD02_NETWORK_BUILD=1 npm run test:unit` | **75 pass, no skips**; includes actual webpack production build under Node network-denial permissions |
| `npm run lint` | Full frontend lint passed, including new browser spec |
| `npx tsc --noEmit` | Initial error in new test's unsupported `test.use.reducedMotion`; corrected to `contextOptions.reducedMotion`, rerun passed |
| Existing scratch Python + `scripts/ux_measure/font_inventory.py` (repo root) | Five font hashes/cmaps recorded; all listed glyphs present |
| `node --check scripts/ux_measure/{measure,inspect,summarize}.cjs` (each, repo root) | Passed |
| `git diff --check` | Passed; configured LF/CRLF notices only |

The opt-in test runs `node node_modules/next/dist/bin/next build --webpack`, checks
both Google font origins fail with `ERR_ACCESS_DENIED`, and verifies emitted font
hashes, CSS faces/ranges/display and no remote font CSS. That is a real build, not
a mocked network response. Normal CI uses its own webpack build and does not opt
into that extra test. Hosted results and independent review remain separate gates.
This run did not clear `.next` first, so this is not a new cold-build test. Node's
network permissions are not an OS-wide air gap for native/child processes.
Existing Node 26 `module.register` deprecation and permission-model warnings are
recorded in logs, not suppressed by source/config changes.

## Reproduced usability findings

Baseline new browser suite: **8 pass, 3 fail**, before changing the component.
Logs: `regression-red-full.log`; screenshots/traces: `red-full-results/`, under
the lane scratch directory. Existing successful behavior is not called a defect.

| Finding | Baseline evidence | Minimal correction |
|---|---|---|
| Short viewport clips cookie preferences | 375x320: panel height 343px, top -23px, overflow visible; wheel cannot reveal clipped title | Limit the existing dialog to `100dvh`, with internal vertical overflow |
| Cookie explanation low contrast | Rendered foreground versus sampled adjacent translucent backdrop: 3.692:1 | Existing zinc-400 text becomes zinc-300 |
| Preference descriptions low contrast | All three 12px descriptions on opaque panel: 4.121:1, below AA 4.5:1 | Existing zinc-500 text becomes zinc-400 |

Browser tests measure resolved sRGB colors (Tailwind emits Lab), not assumed hex
tokens. The explanation test samples actual screenshot padding at the text-line
height; this is a local scene sample, not an exhaustive backdrop contrast audit.
Consent copy, default-deny, essential-cookie pinning, opt-in selection, persistence,
GPC and choice semantics are unchanged. Both optional choices, custom keyboard
selection and reload dismissal are covered. Unit guards also cover unchanged
preferences and selective opt-in.

Fixed webpack browser measurements: short panel top 0px, height 320px,
clientHeight 319px, scrollHeight 342px, overflow `auto`. Explanation contrast is
6.553:1 on the sampled rendered scene; all three preference descriptions are
7.585:1. The privacy link/title can be scrolled into view and Save dismisses the
panel, removing `--banner-h`. These are functional and contrast checks, not an
audit of every theme, zoom level or assistive-technology combination.

### Real screenshot and raw-result locations

Artifact root: `C:/Users/Axel/AppData/Local/hermes/cache/scratch/ux-01/`.
These local artifacts are preserved for the manager, not public hosted assets.

- Before: `baseline-usability/375-{cookie,settings,short-settings,comparison-right}.png`.
- After (webpack): `fixed-usability/375-{cookie,settings,short-settings,comparison-right}.png`
  and `fixed-usability/1440-{cookie,settings,comparison-right}.png`.
- `*-comparison-section.png` is an element capture; it can include the fixed
  navbar overlay. Use `*-comparison-right.png` for the actual viewport view.
- Production timing screenshots: `{baseline-normal,fixed-turbo,fixed-webpack}/`
  followed by `{native,slow4g-cpu4}-{375,1440}-{1,2,3}-top.png`.
- Each measurement directory has `report.json`. `full-smoke.json` contains browser
  results plus exact contrast/geometry attachments. `fixed-usability/usability.json`
  contains dimensions, computed colors, focus/scroll measurements and synthetic
  local consent state. Red failure traces/screenshots remain in `red-full-results/`.
- All 36 retained timing navigations were checked for HTTP 200, five noncached
  fonts, exact encoded/decoded totals, supported LCP/CLS and raw-probe agreement.
  CLS was recomputed from retained raw shifts with identical results.
- Screenshots were opened and inspected, not inferred from DOM bounds. No
  historical pixel-equivalence claim is made.

### Comparison: no product change

At 375px, document width/scroll width are both 375px. The comparison scrollport
is 327px and table 512px; its horizontal range is 185px. In this Chromium version,
the scroll container naturally participates in Tab order despite `tabIndex=-1`.
Ten Tabs from the skip link reach it; ArrowRight changes scrollLeft from 0 to 40,
and repeated arrow keys reach the final column. ArrowLeft returns toward the
first column. Six rows and all three column headers remain available.

At 1440px, scrollport/table are 976px with no horizontal scrolling needed. Cookie
banner dismissal is available at both widths. At 375x812 the initial banner is
151px tall and preferences 343px, leaving usable page area; at 1440x812 they are
89px and 269px. Off-viewport table bounds alone did not establish a defect.
No comparison component or layout changes were made. Touch swipes, assistive
technology and older browsers still need device-specific acceptance.

## Next measured scope, not authorization

Manager should assign a separate font-delivery lane after reviewing this evidence:

1. Verify equivalent Linux/target delivery and repeat the defined cold profile.
2. Evaluate lossless WOFF2 first, preserve families/styles/weight ranges, upstream
   licenses and Azerbaijani cmap coverage. Treat selective preloading as a measured
   experiment; do not preload everything by assumption. Subsetting needs explicit
   repertoire approval beyond just the listed Azerbaijani test string.
3. Proposed review budgets, **not manager-approved acceptance**: cold font encoded
   body <=300 KiB; slow-profile LCP median <=2.5s; observed initial-window CLS
   <=0.1 on each run. Report raw samples and variance, not just medians.
4. Do not claim this cookie fix optimizes fonts or resolves landing render shifts.
   Layout/font files require separate ownership. No deployment or merge here.

## PR #42 exact-boundary / hydration correction

Manager review [6695152018](https://github.com/JafarShamzsi/ArtiProof/pull/42#issuecomment-6695152018)
accepted the cookie runtime at `f8893b08bf8081bb1aa53a2f537ebf61c7bbafa9` but blocked
the measurement helper and reload-test evidence. This correction changes no
component, product, style, font, manifest, dependency or CI file.

The original CLS implementation used `>1000` / `>5000`. Its earlier raw-score
recomputation repeated that algorithm and did **not** test the exact boundaries.
The production calculation is now a single browser-serializable
`scripts/ux_measure/cls.cjs` helper, passed directly to `page.evaluate` by the live
runner and imported by both Node tests and offline recomputation. There is no
second CLS algorithm in a test or the runner.

Regression-first: extraction initially preserved the bug. Actual-helper tests
observed **3 failures / 4 passes**, including exact 1000ms gap and exact 5000ms
span (each incorrectly .375 instead of .25). Only after that observation were
both comparisons corrected to `>=`. Seven Node tests now cover exact boundaries,
just-below boundaries, recent-input exclusion, maximum versus summed windows and
empty observations. A browser test also passes the same imported function to
Chromium at both exact boundaries, matching the live runner's execution path.

No expensive remeasurement was performed. Run from repo root:

```powershell
node --test scripts/ux_measure/cls.test.cjs
$root = 'C:/Users/Axel/AppData/Local/hermes/cache/scratch/ux-01'
node scripts/ux_measure/recompute-cls.cjs "$root/baseline-normal/report.json" "$root/fixed-turbo/report.json" "$root/fixed-webpack/report.json"
```

The shared corrected helper recomputed **all 36 preserved scores: 36 unchanged,
0 differences**. Raw reports were read only, not overwritten. Thus all historical
LCP/CLS tables and delivery measurements above remain the recorded values, not
new measurements. The full per-sample comparison is preserved in
`correction-recomputed-cls.json`; red/green Node logs are
`correction-cls-{red,green}.log` under the same artifact root.

After each cookie-choice/custom-preferences reload, negative banner absence now
follows **real client interaction**: click Dark, require its rendered radio state
and HTML dark class, click Light, require its radio state and removal of the dark
class. Neither SSR markup nor stored consent alone can satisfy that sequence.
There is no arbitrary hydration delay. An SSR-only, JavaScript-disabled negative
control demonstrates that banner absence alone passes while the interaction gate
rejects the unhydrated page. This is a test-only probe, not a product/theme change.

Local browser verification reuses the preserved webpack production build
`4vimLTIL6KHzSlXGMX5Aq` after checking port 3204 unused; product code is unchanged.
Correction-only results: **7 Node helper tests pass**, **24 production browser
tests pass with no skips/retries/flaky cases**, full frontend lint/types pass,
and ordinary unit suite **74 pass / 1 explicit optional network-build skip**.
The original three raw `report.json` hashes still match the earlier evidence
index, independently confirming recomputation did not rewrite them. The local
server/browser are stopped after verification. Logs/results use the
`correction-` prefix in the existing artifact directory.
Current correction checks/results and exact successor hosted results are recorded
in the PR/issue handoff. The expensive optional network-denied build is not rerun
for this test/helper-only correction; ordinary unit skips remain explicit.
All performance, real-device, screen-reader, full-lifetime CLS, packet-level wire,
target Linux/CDN timing and production exclusions above remain in force.
