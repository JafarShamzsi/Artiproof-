# Phase 5: Frontend Code Fixes
## Priority: HIGH — User-facing bugs and gaps

This phase fixes type safety issues, memory leaks, missing error/loading states, UX gaps, and adds missing pages.

---

## Context

ArtiProof frontend: Next.js 14+ (App Router), React 19, Tailwind CSS, Framer Motion, Zustand. Pages are in `frontend/src/app/`. Components in `frontend/src/components/`. The dashboard is at `(dashboard)/` route group, landing at `(landing)/`, auth at `(auth)/`.

---

## Issues To Fix (28 total)

### GROUP A: Type Safety (Issues 1-3)

**1. Replace all `any` types with proper interfaces**

Create a types file: `frontend/src/types/api.ts`

```typescript
// Source Check types
export interface SourceCheck {
  id: string;
  user_id: string;
  input_type: "url" | "text" | "pdf";
  input_url?: string;
  input_content?: string;
  status: "pending" | "processing" | "completed" | "failed";
  credibility_score?: number;
  score_breakdown?: ScoreBreakdown;
  ai_probability?: number;
  claims?: Claim[];
  citations?: Citation[];
  sources?: Source[];
  origin_trace?: OriginTrace;
  model_metadata?: ModelMetadata;
  created_at: string;
  updated_at: string;
}

export interface ScoreBreakdown {
  base: number;
  deductions: Array<{
    reason: string;
    count?: number;
    weight?: number;
    impact: number;
  }>;
  final: number;
  confidence: number;
  formula_version: string;
}

export interface Claim {
  id: string;
  text: string;
  verdict: "true" | "false" | "misleading" | "unverifiable" | "unknown";
  confidence: number;
  explanation?: string;
  position_in_text?: { start: number; end: number };
  sources?: string[];
}

export interface Citation {
  url: string;
  title?: string;
  is_accessible: boolean;
  is_retracted: boolean;
  credibility_score: number;
  domain_credibility: string;
  suggested_alternative?: string;
}

// Researcher types
export interface ResearcherProfile {
  id: string;
  user_id: string;
  researcher_name: string;
  orcid?: string;
  analysis_status: string;
  integrity_score?: number;
  integrity_breakdown?: IntegrityBreakdown;
  official_h_index?: number;
  adjusted_h_index?: number;
  official_citation_count?: number;
  adjusted_citation_count?: number;
  self_citation_rate?: number;
  citation_ring_flags?: CitationRingFlags;
  publications?: PublicationAnalysis[];
  created_at: string;
}

export interface CitationRingFlags {
  has_ring: boolean;
  ring_members?: Array<{
    name: string;
    citations_to_target: number;
    citations_from_target: number;
  }>;
  suspicious_pairs?: Array<{ author_a: string; author_b: string; mutual_count: number }>;
  graph?: { nodes: GraphNode[]; edges: GraphEdge[] };
}

export interface GraphNode {
  id: string;
  name: string;
  citation_count: number;
  is_target: boolean;
  is_suspicious: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
  is_suspicious: boolean;
}

export interface PublicationAnalysis {
  id: string;
  title: string;
  year?: number;
  citation_count: number;
  is_self_cited_heavily: boolean;
  topic_relevance_score?: number;
  flags?: string[];
}
```

Then update ALL pages that use `any`:
- `frontend/src/app/(dashboard)/check/page.tsx` — `useState<any[]>` → `useState<SourceCheck[]>`
- `frontend/src/app/(dashboard)/researcher/page.tsx` — `useState<any[]>` → `useState<ResearcherProfile[]>`
- `frontend/src/app/(dashboard)/check/[id]/page.tsx` — all `any` props
- `frontend/src/app/(dashboard)/researcher/[id]/page.tsx` — `citation_ring_flags: any`

**2. Add return types to all API helper functions**
File: `frontend/src/lib/` — any API call functions should have explicit return types.

**3. Remove Prisma and bcryptjs from frontend**
File: `frontend/package.json`

Remove these — they're backend-only dependencies that shouldn't be in the frontend:
```bash
cd frontend
npm uninstall @prisma/adapter-pg @prisma/client bcryptjs dotenv
npm uninstall -D @types/bcryptjs
```

Also remove `shadcn` from dependencies (it's a CLI tool, not a runtime dep):
```bash
npm uninstall shadcn
```

---

### GROUP B: Memory Leaks & State Issues (Issues 4-8)

**4. Close EventSource streams on unmount**
File: `frontend/src/app/(dashboard)/check/page.tsx`

```typescript
useEffect(() => {
  const eventSource = new EventSource(`/api/source-check/${checkId}/stream`);
  
  eventSource.onmessage = (e) => { ... };
  eventSource.onerror = () => { eventSource.close(); };
  
  // CRITICAL: Close on unmount
  return () => {
    eventSource.close();
  };
}, [checkId]);
```

Apply same pattern in:
- `frontend/src/app/(dashboard)/researcher/page.tsx`

**5. Fix Promise.all silent failures on dashboard**
File: `frontend/src/app/(dashboard)/dashboard/page.tsx:56-68`

```typescript
// BAD:
const [checks, analyses] = await Promise.all([
  fetchChecks().catch(() => []),
  fetchAnalyses().catch(() => []),
]);

// GOOD:
try {
  const [checks, analyses] = await Promise.all([
    fetchChecks(),
    fetchAnalyses(),
  ]);
  setChecks(checks);
  setAnalyses(analyses);
} catch (error) {
  setError("Failed to load dashboard data. Please refresh.");
}
```

**6. Add proper error state to dashboard**

Add error state and display:
```typescript
const [error, setError] = useState<string | null>(null);

// In JSX:
{error && (
  <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">
    {error}
    <button onClick={refetch} className="ml-2 underline">Retry</button>
  </div>
)}
```

**7. Fix settings page cleanup race condition**
File: `frontend/src/app/(dashboard)/settings/page.tsx:39-56`

Ensure AbortController is used for fetch cleanup:
```typescript
useEffect(() => {
  const controller = new AbortController();
  
  async function loadProfile() {
    try {
      const res = await fetch("/api/auth/me", { signal: controller.signal });
      if (!controller.signal.aborted) {
        const data = await res.json();
        setProfile(data);
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setError("Failed to load profile");
    }
  }
  
  loadProfile();
  return () => controller.abort();
}, []);
```

**8. Add retry mechanism for failed API calls**

Create a utility:
```typescript
// frontend/src/lib/fetchWithRetry.ts
export async function fetchWithRetry(
  url: string, 
  options?: RequestInit, 
  maxRetries = 2
): Promise<Response> {
  let lastError: Error | null = null;
  for (let i = 0; i <= maxRetries; i++) {
    try {
      const res = await fetch(url, options);
      if (res.ok || res.status < 500) return res;
      lastError = new Error(`HTTP ${res.status}`);
    } catch (e) {
      lastError = e as Error;
    }
    if (i < maxRetries) await new Promise(r => setTimeout(r, 1000 * (i + 1)));
  }
  throw lastError;
}
```

---

### GROUP C: Missing Pages & States (Issues 9-16)

**9. Create 404 page**
File: `frontend/src/app/not-found.tsx`

```typescript
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-6">
      <h1 className="text-6xl font-bold text-white">404</h1>
      <p className="mt-4 text-zinc-400">Page not found</p>
      <Link
        href="/"
        className="mt-8 rounded-lg bg-emerald-500 px-6 py-3 text-sm font-medium text-white hover:bg-emerald-600"
      >
        Go Home
      </Link>
    </div>
  );
}
```

**10. Create error page**
File: `frontend/src/app/error.tsx`

```typescript
"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-950 px-6">
      <h1 className="text-4xl font-bold text-white">Something went wrong</h1>
      <p className="mt-4 text-zinc-400">{error.message || "An unexpected error occurred"}</p>
      <button
        onClick={reset}
        className="mt-8 rounded-lg bg-emerald-500 px-6 py-3 text-sm font-medium text-white hover:bg-emerald-600"
      >
        Try Again
      </button>
    </div>
  );
}
```

**11. Show file upload errors in UI**
File: `frontend/src/app/(dashboard)/check/page.tsx:92`

Error state is set but never rendered. Add error display:
```typescript
{error && (
  <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-sm text-red-400">
    {error}
  </div>
)}
```

**12. Add loading spinners for Google auth**
File: `frontend/src/app/(auth)/login/page.tsx`

```typescript
const [googleLoading, setGoogleLoading] = useState(false);

<button
  onClick={() => { setGoogleLoading(true); signIn("google"); }}
  disabled={googleLoading}
  className="..."
>
  {googleLoading ? (
    <span className="animate-spin">⟳</span>
  ) : (
    "Continue with Google"
  )}
</button>
```

**13. Create privacy policy page**
File: `frontend/src/app/(landing)/privacy/page.tsx`

Minimal placeholder with real content about data handling.

**14. Create terms of service page**
File: `frontend/src/app/(landing)/terms/page.tsx`

Minimal placeholder.

**15. Add password validation feedback**
File: `frontend/src/app/(auth)/register/page.tsx`

Show password requirements:
```typescript
<p className="mt-1 text-xs text-zinc-500">
  Minimum 8 characters
</p>
```

**16. Fix notification preferences**
File: `frontend/src/app/(dashboard)/settings/page.tsx`

Either make them functional (with backend API) or remove them entirely. Non-functional checkboxes are misleading.

Recommended: Remove the notifications section and add a comment `// TODO: Add notification preferences when backend supports it`

---

### GROUP D: UX Improvements (Issues 17-24)

**17. Show score breakdown in check results**
File: `frontend/src/app/(dashboard)/check/[id]/page.tsx`

If the API returns `score_breakdown`, display it:
```typescript
{data.score_breakdown && (
  <div className="mt-4 space-y-2">
    <h4 className="text-sm font-medium text-zinc-300">Score Breakdown</h4>
    {data.score_breakdown.deductions.map((d, i) => (
      <div key={i} className="flex justify-between text-xs">
        <span className="text-zinc-400">{d.reason.replace(/_/g, " ")}</span>
        <span className="text-red-400">{d.impact}</span>
      </div>
    ))}
    <div className="flex justify-between text-xs border-t border-zinc-800 pt-1">
      <span className="text-zinc-300">Confidence</span>
      <span className="text-zinc-400">{Math.round(data.score_breakdown.confidence * 100)}%</span>
    </div>
  </div>
)}
```

**18. Add coverage indicators**

Show users what was analyzed:
```typescript
{data.model_metadata && (
  <div className="mt-2 flex flex-wrap gap-2">
    {data.model_metadata.text_truncated && (
      <span className="text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">
        First {data.model_metadata.analyzed_length?.toLocaleString()} chars analyzed
      </span>
    )}
    <span className="text-[10px] text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded">
      {data.model_metadata.claims_extracted} claims extracted
    </span>
  </div>
)}
```

**19. Add AI detection disclaimer**

```typescript
<p className="text-[10px] text-zinc-600 mt-2">
  AI detection is probabilistic and should be used as one signal among many, not as proof.
</p>
```

**20. Add publications pagination**
File: `frontend/src/app/(dashboard)/researcher/[id]/page.tsx:390`

Currently `.slice(0, 50)` with no pagination:
```typescript
const [pubPage, setPubPage] = useState(0);
const PUB_PAGE_SIZE = 20;
const paginatedPubs = publications.slice(
  pubPage * PUB_PAGE_SIZE, 
  (pubPage + 1) * PUB_PAGE_SIZE
);

// Add pagination controls
<div className="flex justify-between mt-4">
  <button 
    onClick={() => setPubPage(p => Math.max(0, p - 1))} 
    disabled={pubPage === 0}
  >Previous</button>
  <span className="text-xs text-zinc-500">
    {pubPage * PUB_PAGE_SIZE + 1}-{Math.min((pubPage + 1) * PUB_PAGE_SIZE, publications.length)} 
    of {publications.length}
  </span>
  <button 
    onClick={() => setPubPage(p => p + 1)} 
    disabled={(pubPage + 1) * PUB_PAGE_SIZE >= publications.length}
  >Next</button>
</div>
```

**21. Fix citation graph label clarity**

Replace "Suspicious (5+ cites)" with:
```typescript
<span className="text-red-400">● Flagged — unusually frequent citations</span>
```

**22. Extend saved confirmation time**
File: `frontend/src/app/(dashboard)/settings/page.tsx`

```typescript
// Change from 2000ms to 4000ms
setTimeout(() => setSaved(false), 4000);
```

**23. Enable Next.js image optimization**
File: `frontend/next.config.ts`

```typescript
// Remove or conditionally apply:
images: {
  unoptimized: process.env.GITHUB_PAGES === "true",
  // Only disable for static export, not normal builds
},
```

**24. Add security headers**
File: `frontend/next.config.ts`

```typescript
async headers() {
  return [
    {
      source: "/(.*)",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ],
    },
  ];
},
```

---

### GROUP E: Responsive & Polish (Issues 25-28)

**25. Improve mobile check results layout**

Test on mobile viewport and fix any stacking issues in the split view.

**26. Add loading skeleton to settings page**

While profile is loading, show skeleton instead of empty form.

**27. Memoize expensive computations**

In researcher page, memoize citation graph path calculations:
```typescript
const graphPaths = useMemo(() => 
  computeGraphLayout(citationData), 
  [citationData]
);
```

**28. Centralize color tokens**

Create `frontend/src/lib/colors.ts`:
```typescript
export const scoreColor = (score: number) =>
  score >= 70 ? "text-emerald-400" : score >= 40 ? "text-yellow-400" : "text-red-400";

export const scoreBgColor = (score: number) =>
  score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-yellow-500" : "bg-red-500";
```

Remove duplicate definitions from individual page files.

---

## Verification

1. `grep -r "any\[\]" frontend/src/app/` returns 0 results
2. 404 page renders at `/nonexistent-path`
3. Error page renders when component throws
4. Upload errors display in the UI
5. EventSource cleanup logged on page navigation
6. Publications table has working pagination
7. Settings confirmation shows for 4 seconds
8. Security headers present in response (check with `curl -I`)
