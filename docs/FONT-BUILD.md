# BUILD-02: deterministic production fonts

Issue: [#30](https://github.com/JafarShamzsi/ArtiProof/issues/30). Dependency:
[PR #22](https://github.com/JafarShamzsi/ArtiProof/pull/22).
Agent-Tag: BUILD-02. Device-Tag: axel-windows.
Reviewed foundation: `bfee6bf3dec196a3cf688d00cc3311d9ccc84f3c`.

## Failure and fix

Hosted run `42247244384`, frontend job `127992569795`, failed in the real
webpack production build at `src/app/layout.tsx`, with
`TypeError: Cannot read properties of null (reading '1')` in the installed
Next 16.2.0 `dist/compiled/@next/font/dist/google/loader.js:122:78`.

The loader extracts URLs from Google CSS (`find-font-files-in-css.js`), fetches
the binaries, then executes:

```js
const ext = /\.(woff|woff2|eot|ttf|otf)$/.exec(googleFontFileUrl)[1];
```

That is an unchecked assumption about the remote response URL shape. A URL
without that terminal extension makes the match null. The hosted response body
was not retained, so its precise URL/content and upstream cause are unknown.
This is not evidence that any particular family always fails. Earlier successful
builds do not remove the build-time response dependency.

Root layout now uses the documented `next/font/local` API, literal `src` paths,
per-face string weight ranges/styles, the same four CSS variables and unchanged
body classes. No metadata, product copy, global styles, dependencies, lockfiles,
CI, build checks or other lane files changed. There is no retry workaround,
response mock or loader patch. Next emits self-hosted fonts. Its local-font API
defaults to `preload: true`, but actual preload delivery was not established by
the original implementation evidence; the follow-up below found none locally.

The five same-family variable TTFs are pinned, checked in, and accompanied by
the exact upstream SIL OFL 1.1 texts. See
[`frontend/src/app/fonts/README.md`](../frontend/src/app/fonts/README.md) for
source URLs, revision, copyright, byte sizes, checksums and coverage rationale.
Full upstream coverage rather than Latin-only WOFF2 costs 2.23 MiB before HTTP
compression, avoids per-weight duplication and retains Azerbaijani glyphs.

## Regression-first and verification

The first implementation commit contains only
`frontend/src/app/font-build.contract.test.ts`. Against the unchanged base all
six cases failed: remote loader dependency and all five local face contracts.
The tests use TypeScript's real AST and Next's bundled real font parser, not
mock font responses or mocked font objects. They check family identity
(Newsreader has legacy family name `Newsreader 16pt`, preferred family
`Newsreader`), italic metadata, actual variable weight bounds, Azerbaijani glyph
coverage, checksums, source declarations and CSS-variable bindings.

Local environment: Windows, Node **26.12.1**, installed Next **16.2.0**. CI's
Node 22/Linux is separate acceptance, not established by these local results.

| Check | Actual result |
| --- | --- |
| `npm ci` | Passed; no manifest/lock changes. Existing audit: 30 vulnerabilities (2 low, 13 moderate, 11 high, 4 critical), not fixed in this lane |
| `npm run test:unit` | 57 passed; one expensive network-build test intentionally opt-in, separately executed below |
| `npx tsc --noEmit` | Passed |
| `npm run lint` | Passed, full frontend |
| `npm run build` | Default Turbopack production build passed, including TypeScript and all 27 static pages |
| `node node_modules/next/dist/bin/next build --webpack` | Real webpack production build passed, including TypeScript, all 27 static pages and trace collection |
| Opt-in network-denied contract below | 7 passed, including a real webpack build, emitted-asset SHA-256 and actual generated CSS face/range/style checks |

The local npm version rejected `npm run build -- --webpack` as
`EUNKNOWNCONFIG: Unknown cli flag --webpack`. Invoking the installed Next CLI
directly runs the identical `next build --webpack` operation; no build option
or check was removed. Initial post-fix test failures exposed a stale comment
in unchanged global CSS and Newsreader's legacy family name; the contract now
ignores block comments and reads the font's preferred family name.

### Process-isolated font-network enforcement

Run from `frontend`, with no concurrent build using the same `.next` directory:

```powershell
# For a COLD run, first manually remove or move aside generated frontend/.next.
# The test itself does NOT remove .next or enforce cache coldness.
$env:BUILD02_NETWORK_BUILD = '1'
npx vitest run src/app/font-build.contract.test.ts
Remove-Item Env:BUILD02_NETWORK_BUILD
```

This opt-in check requires a Node version with network permissions (verified on
26.12.1); it is not enabled in ordinary Node 22 CI unit runs. It spawns a probe
and a real webpack build with child-only `NODE_OPTIONS`:

```text
--permission --allow-fs-read=* --allow-fs-write=* --allow-child-process --allow-worker --allow-addons
```

Crucially, **no `--allow-net`** is granted. Real HTTPS fetches to both
`fonts.googleapis.com` and `fonts.gstatic.com` must fail specifically with
`ERR_ACCESS_DENIED`, rather than merely timing out. The build then runs under
the same permissions; Node child processes inherit `NODE_OPTIONS`. The first
denied webpack run followed the Turbopack build, not an earlier successful
webpack font fetch. A final cold run moved the entire generated `.next` directory
to approved temporary storage before executing the seven-case opt-in suite;
it passed with a fresh `.next`, including all emitted TTF checksums. Its log is
`C:/Users/Axel/AppData/Local/Temp/opencode/build02-network-cold.log`.
That coldness was a manual precondition, not a test assertion. Running the opt-in
command alone against an existing `.next` is not evidence of a cold build.

No hosts-file/firewall/global proxy changes, fake DNS, HTTP-response interception,
or Google response fixtures are involved. Telemetry is disabled only in these
child processes. This proves the Node font-fetch path cannot use the network;
it is **not** an OS/container-wide air-gap claim. Next requires child processes,
workers and native addons; Node warns that these permissions can escape its
sandbox. Native code/non-Node subprocess networking is not contained by this
test. No opaque proxy-based denial is claimed.

## Typography and browser evidence

| Voice | Before | After generated production CSS |
| --- | --- | --- |
| Sans | Inter, normal variable | Inter binary, normal 100–900, `--font-sans` |
| Display | Fraunces normal + italic, 400/500/600/700/800 | Same family, both real faces, 400–800, `--font-display` |
| Editorial | Newsreader italic, 400/500 | Same family, real italic face, 400–500, `--font-editorial` |
| Mono | JetBrains Mono normal, 400/500 | Same family, normal 400–500, `--font-mono` |

`font-display: swap` remains configured. `preload: true` is the local-font API
default, not proof of a delivered preload link/header. Generated family aliases
are Next implementation details, not substituted typefaces. Local-font computes
fallback adjustments from actual asset metrics, with Arial for sans/mono and
Times New Roman for both serifs (same fallback families as the Google loader).
The adjustment values are **not identical** to Google's bundled metric table:

| Family | Previous Google size-adjust | Local generated size-adjust |
| --- | ---: | ---: |
| Inter | 107.12% | 107.89% |
| Fraunces | 115.45% | 127.27% |
| Newsreader | 105.48% | 91.64% |
| JetBrains Mono | 134.59% | 131.49% |

Browser verification used the real webpack production server at loopback port
3102, a fresh headless Firefox profile, and the existing Playwright package.
Playwright's expected Firefox 1522 was absent; the already-installed Firefox
1569 executable was explicitly selected, without installing browsers or
dependencies. The test-owned server/browser were stopped afterward.

- Landing page rendered at 1440×1100; screenshot inspected for the intended
  editorial serif/italic/sans/mono hierarchy and obvious clipping/overlap.
- 18 font/weight/style cases loaded through `document.fonts.load`, including
  both Fraunces styles and Azerbaijani text. All returned loaded real faces;
  measured canvas advances differed from generic monospace fallback.
- All five binary requests were same-origin `/_next/static/media/*.ttf`;
  no Google font requests and no page JavaScript errors were observed.
- An injected specimen checked each declared weight/style without changing
  application source. This is runtime font evidence, not merely variable presence.

Local evidence files (not committed):
`C:/Users/Axel/AppData/Local/Temp/opencode/build02-{landing.png,specimen.png,browser.json}`.
The landing screenshot is viewport-only; the specimen includes offscreen
animation sections and is not a full-site visual QA claim.

**Remaining visual limitations:** no retained historical browser screenshot or
remote font response exists for a pixel/line-break comparison. Full upstream
variable fonts retain optical-size axes that a Google-served instance may freeze;
browser automatic optical sizing and fallback-period layout can therefore differ.
Same family/style and successful rendering do not prove pixel-identical historical
metrics, zero CLS, cross-browser equivalence or mobile layout equivalence. Manager
visual acceptance should explicitly review these differences and the asset-size
tradeoff. No deployment or real-provider verification is claimed.

### Manager-renewed desktop/mobile acceptance follow-up (2026-11-06)

Manager integrated main's security/CI baseline at
`4b8226131295b549e37553a6aa871e4bab2eed45`. The latest PR #31 review comment
records independent PASS of the original code/assets and verification that all
13 font paths were unchanged by integration. This bounded follow-up changes
only this document and `frontend/src/app/fonts/README.md`; application layout,
fonts, notices, tests, dependencies and CI remain untouched.

A new local webpack production build of that combined head passed, including
TypeScript and prerendering. A test-owned server on loopback port 3102 and the
existing isolated headless Firefox executable (reported browser version 158.0,
Playwright distribution directory `firefox-1569`) verified the public `/` route.
Each viewport used a fresh browser context with no imported authentication,
cookies or storage. Reduced-motion preference was enabled to make screenshot
inspection reproducible; this is not normal-motion animation QA. Both route
responses were HTTP 200. The server/browser were stopped after the checks.

| Observation | Desktop 1440×1100 CSS px | Mobile 375×1100 CSS px |
| --- | --- | --- |
| Document client/scroll width | 1440 / 1440 px | 375 / 375 px |
| Horizontal document overflow, before/after bounded scroll | 0 / 0 px | 0 / 0 px |
| `document.fonts.status` after navigation and after awaiting `document.fonts.ready` | `loaded` / `loaded` | `loaded` / `loaded` |
| Real font faces | All five loaded with declared styles/ranges | All five loaded with declared styles/ranges |
| Font HTTP responses | Five same-origin TTFs, HTTP 200 | Five same-origin TTFs, HTTP 200 |
| Font response decoded payload total | 2,334,812 bytes | 2,334,812 bytes |
| Google font requests / page JavaScript errors | 0 / 0 | 0 / 0 |
| Main response HTTP `Link` header | Absent | Absent |
| Raw HTML / live DOM font preload links (`rel=preload`, `as=font`) | 0 / 0 | 0 / 0 |

The raw HTML and DOM each contained one **script** preload, not a font preload.
The generated `.next/server/next-font-manifest.json` contained `app: {}` and
`pages: {}`, with both size-adjust flags false. Combined with the absent response
`Link` header, these observations establish **no observed font preload delivery
in this local production verification**, despite the API's configured default.
They do not establish delivery behavior on a hosted deployment, early-hints
behavior on another server, or a reason to change the reviewed font code.

Font responses used `Content-Encoding: gzip` and chunked transfer, with no
Content-Length. The totals above are actual decoded response bodies, not an
estimate of compressed wire transfer. Wire bytes, mobile loading performance,
CLS, LCP and other performance metrics were **not measured**; no performance
clearance or zero-layout-shift conclusion follows from font readiness.

Top and full-page screenshots were inspected for serif/italic/sans/mono hierarchy,
headline/body wrapping and obvious overlap. At 375px the headline, editorial
copy and CTAs wrap within the viewport, and navigation collapses. The existing
fixed cookie banner covers part of the lower viewport at both sizes; it is
particularly prominent on mobile. This was retained in screenshots, not hidden
to fabricate an unobstructed page. Element-level bounds also identify offscreen
blur decorations and a 512px-wide comparison table on mobile; these do not create
document-level horizontal overflow. The table's full contents/interactions were
not accepted as mobile usability QA. No UI corrections were authorized or made.

Artifacts for manager visual acceptance (not committed), all under
`C:/Users/Axel/AppData/Local/hermes/cache/scratch/build02-acceptance/`:

- `1440-top.png`, `1440-full.png`: desktop screenshots.
- `375-top.png`, `375-full.png`: mobile screenshots.
- `report.json`: font readiness/faces, overflow measurements, response metadata,
  decoded payload sizes, errors and preload observations.
- `1440-headers.json`, `375-headers.json`, `1440-response.html`,
  `375-response.html`: actual public route response headers/HTML.
- `build.log`, `browser.log`, `verify.cjs`: bounded build/browser evidence and
  scratch-only verification script.

These checks establish local desktop/mobile rendering observations, **not
historical pixel equivalence**, cross-browser/mobile performance clearance or
manager visual approval. Final exact-head hosted CI results/counts/skips are
recorded in the PR handoff after a bounded observation window; earlier-head CI
or a pending run is not a passing result for a later documentation commit.

## Handoff and rollback

Draft PR targets `main`, depends on PR #22, and records the exact head SHA for
independent review. Do not merge/deploy from this lane. The manager has now
integrated main's security baseline in the renewed combined head above; the
earlier `f551c5b...` main observation is historical, not the current integration
state. Hosted exact-head Node 22/Linux CI and manager visual acceptance remain
separate gates. Do not rebase or alter the assigned dependency stack without
manager coordination.

Rollback: manager-reviewed revert of the BUILD-02 commits restores Google-font
loading and removes these assets/tests/docs; that also restores the known remote
response failure risk. Never treat rollback as a deterministic-build fix.
