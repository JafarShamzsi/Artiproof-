# Phase 6: Accessibility Fixes
## Priority: MEDIUM — WCAG 2.1 AA compliance

This phase adds ARIA labels, focus management, keyboard navigation, and screen reader support to the ArtiProof frontend. The project already has a high-contrast mode (via `data-high-contrast` attribute) but lacks basic accessibility fundamentals.

---

## Issues To Fix (8 total)

### 1. Add Skip-to-Content Link
File: `frontend/src/app/layout.tsx` or `frontend/src/app/(landing)/layout.tsx`

```typescript
<a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[100] focus:rounded-lg focus:bg-emerald-500 focus:px-4 focus:py-2 focus:text-white"
>
  Skip to main content
</a>
```

Add `id="main-content"` to the `<main>` tag in both landing and dashboard layouts.

### 2. Add ARIA Labels to Dashboard Navigation
File: `frontend/src/app/(dashboard)/layout.tsx`

```typescript
<nav aria-label="Main navigation">
  {/* sidebar links */}
</nav>

<main id="main-content" role="main" aria-label="Dashboard content">
  {children}
</main>
```

Add `aria-label` to all icon-only buttons:
```typescript
<button aria-label="Toggle sidebar">
  <Menu className="size-5" />
</button>
```

### 3. Add ARIA Labels to Interactive Elements

Throughout dashboard pages, add labels to:
- Score gauges: `<div role="meter" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} aria-label="Credibility score">`
- Progress bars: `<div role="progressbar" aria-valuenow={progress} aria-label="Analysis progress">`
- Status badges: `<span role="status" aria-label={`Status: ${status}`}>`
- Tab panels in AudienceSection: Already uses Tabs component, verify `role="tabpanel"` is set
- File upload area: `<div role="button" aria-label="Upload PDF file" tabIndex={0}>`

### 4. Add `aria-live` Regions for Async Updates
Files: check page, researcher page (SSE streaming)

```typescript
<div aria-live="polite" aria-atomic="true" className="sr-only">
  {statusMessage}
</div>
```

Update `statusMessage` whenever the analysis stage changes (extracting claims, checking facts, etc.). Screen readers will announce the change.

### 5. Add Focus Trap to Sheet/Modal Components
File: `frontend/src/components/ui/sheet.tsx`

The Sheet component (mobile nav) should trap focus when open. If using Radix or Base UI, this may already be handled. Verify by:
1. Opening mobile menu
2. Pressing Tab — focus should cycle within the menu
3. Pressing Escape — menu should close and focus returns to trigger

If not working, add:
```typescript
import { FocusTrap } from "@base-ui/react"; // or similar

<SheetContent>
  <FocusTrap>
    {/* sheet content */}
  </FocusTrap>
</SheetContent>
```

### 6. Add Keyboard Navigation to Citation Graph
File: `frontend/src/app/(dashboard)/researcher/[id]/page.tsx`

The SVG citation graph has no keyboard support. Add:
```typescript
{nodes.map(node => (
  <g
    key={node.id}
    role="button"
    tabIndex={0}
    aria-label={`${node.name}, ${node.citation_count} citations${node.is_suspicious ? ', flagged as suspicious' : ''}`}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        handleNodeClick(node);
      }
    }}
  >
    {/* circle and label */}
  </g>
))}
```

### 7. Add Form Label Associations
Files: auth pages, settings page

Ensure all form inputs have associated labels:
```typescript
<label htmlFor="email" className="text-sm text-zinc-400">Email</label>
<input id="email" type="email" ... />
```

Check all forms in:
- `frontend/src/app/(auth)/login/page.tsx`
- `frontend/src/app/(auth)/register/page.tsx`
- `frontend/src/app/(dashboard)/settings/page.tsx`
- `frontend/src/app/(dashboard)/check/page.tsx` (URL input)
- `frontend/src/app/(dashboard)/researcher/page.tsx` (name/ID inputs)

### 8. Add Color-Independent Status Indicators

Currently some statuses rely only on color (red/green/yellow). Add text or icons:
```typescript
// Instead of just color:
<div className="h-2 w-2 rounded-full bg-red-500" />

// Add text equivalent:
<div className="flex items-center gap-1.5">
  <div className="h-2 w-2 rounded-full bg-red-500" aria-hidden="true" />
  <span className="text-xs text-red-400">Failed</span>
</div>
```

This is especially important for the claim verdicts (true/false/misleading) and citation statuses.

---

## Verification

1. Tab through the entire landing page — focus should be visible on every interactive element
2. Screen reader (VoiceOver/NVDA) can navigate the dashboard
3. Mobile menu traps focus when open
4. Score gauges announce their values to screen readers
5. All form inputs have associated labels
6. Status indicators have text equivalents, not just colors
7. Skip-to-content link works on Tab from page load
