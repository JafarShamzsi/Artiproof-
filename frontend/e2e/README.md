# Frontend smoke tests (Playwright)

Catches deploy-blocking regressions in the routes that anonymous traffic
hits: landing render, pricing copy, auth-form rendering, and dashboard
auth-gate redirects.

## What's NOT here

End-to-end flows that need a real backend + Celery + DB seed:

- Signup → first source-check analysis → result page
- Researcher analysis end-to-end
- Scheduled report fire
- Stripe checkout (deferred; payment processor TBD)

Those live in a separate integration suite that's tracked in the
roadmap. They need Gemini, CrossRef, Resend, and Celery wired with
test-mode credentials.

## Run locally

```bash
cd frontend
npm install
npx playwright install chromium
npm run test:smoke
```

The config starts a fresh `npm run dev` server on 3000 by default. To
point at an already-running server (e.g. you have `npm run dev` open):

```bash
PLAYWRIGHT_NO_WEBSERVER=1 npx playwright test
```

To use a deployed preview / staging URL:

```bash
PLAYWRIGHT_BASE_URL=https://preview.example.com PLAYWRIGHT_NO_WEBSERVER=1 npx playwright test
```

## CI

The CI workflow runs the smoke suite against a freshly-built Next.js
server. No backend needed — every test in `e2e/` is designed to pass
without a running API. Tests that would require the backend should be
moved to an `integration/` suite instead.
