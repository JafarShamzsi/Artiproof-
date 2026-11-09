import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "Changelog — ArtiProof",
  description:
    "User-visible product updates to ArtiProof. Date-sorted, newest first. Smaller infra changes stay in the engineering log.",
};

/**
 * Hand-curated, dated changelog. We don't auto-generate from commits
 * because half the commits are infra/cleanup and the surface a user
 * cares about (new features, behaviour changes, fixes that affected
 * scoring) is the small subset that gets a bullet here.
 *
 * Maintenance: when you ship something user-visible, add an entry at
 * the top. The category tags (feature / fix / governance / security)
 * help institutional buyers scan for what they care about.
 */

type Category = "feature" | "fix" | "governance" | "security" | "infra";

interface Entry {
  date: string;
  category: Category;
  title: string;
  body: string;
}

const CATEGORY_LABEL: Record<Category, string> = {
  feature: "Feature",
  fix: "Fix",
  governance: "Governance",
  security: "Security",
  infra: "Infrastructure",
};

const CATEGORY_TINT: Record<Category, string> = {
  feature: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  fix: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
  governance: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  security: "bg-rose-500/15 text-rose-300 ring-rose-500/30",
  infra: "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30",
};

const ENTRIES: Entry[] = [
  {
    date: "2026-05-29",
    category: "governance",
    title: "Prompt + model versioning on every analysis",
    body: "Every source check and researcher analysis now records the LLM model name, the formula version, and a SHA-256 hash of every prompt used. A CI gate fails the build if a prompt is edited without bumping PROMPT_VERSION — silent score drift is no longer possible.",
  },
  {
    date: "2026-05-29",
    category: "security",
    title: "Tier-aware rate limits on expensive endpoints",
    body: "Source check, researcher analyze, and report generate now enforce per-user, per-tier burst caps (3/min free, 30/min pro, 120/min team). Anonymous requests get the strictest cap regardless of which endpoint they hit.",
  },
  {
    date: "2026-05-29",
    category: "fix",
    title: "Cross-org authorization on shared resources",
    body: "Migration 0012 added an organization_id column to source checks, researcher profiles, and reports back in May. The 24 ownership checks across the routers now route through a single helper so team-tier admins can see their org's work once the role bit lands in Phase C.",
  },
  {
    date: "2026-05-29",
    category: "fix",
    title: "Admin user search debounce + race guard",
    body: "Typing in the admin search box no longer fires one network request per keystroke. The tier dropdown disables itself while a PATCH is in flight, so a stray double-click can no longer fire duplicate updates.",
  },
  {
    date: "2026-05-29",
    category: "infra",
    title: "Deep readiness probe at /api/health/deep",
    body: "External uptime monitors can now hit a single endpoint that pings the database, Redis, Gemini, CrossRef, and OpenAlex in parallel with a 2s timeout each. The shallow /api/health still drives Railway's restart gate.",
  },
  {
    date: "2026-05-28",
    category: "feature",
    title: "Admin panel",
    body: "Operators can now list and search users, change tiers, restore soft-deleted accounts, and review failed pipelines from a real UI. No more SQL sessions for support requests.",
  },
  {
    date: "2026-05-28",
    category: "feature",
    title: "Multi-source retraction lookup",
    body: "Citation retraction checks now query both CrossRef and OpenAlex in parallel. If either source flags a DOI as retracted, the citation is marked — closes a credibility hole for editors.",
  },
  {
    date: "2026-05-28",
    category: "feature",
    title: "Email delivery",
    body: "Password reset, email verification, and scheduled report emails now actually send (Resend integration). Local dev still falls back to a console-log stub when no API key is set.",
  },
  {
    date: "2026-05-28",
    category: "feature",
    title: "Account export, refresh, and logout",
    body: "New /api/auth/refresh and /api/auth/logout endpoints make sessions properly revocable. Account export endpoint will land in Phase B for GDPR portability.",
  },
  {
    date: "2026-05-28",
    category: "feature",
    title: "Report templates + schedules + white-label branding",
    body: "Reports gain templates (executive summary, comparison, institutional audit), recurring schedules with timezone awareness, and per-org branding (logo + colors). Team-tier feature.",
  },
  {
    date: "2026-05-28",
    category: "feature",
    title: "Researcher bulk analysis + compare + watchlist",
    body: "Submit up to 50 researchers at a time, compare two profiles side-by-side, and watch up to 50 researchers for integrity score deltas between snapshots.",
  },
];

export default function ChangelogPage() {
  return (
    <>
      <Navbar />
      <main
        id="main-content"
        tabIndex={-1}
        className="relative z-10 min-h-[100dvh] bg-zinc-950 pb-24 pt-32"
      >
        <article className="mx-auto max-w-3xl px-6 text-zinc-300">
          <Link
            href="/"
            className="text-sm text-emerald-400 hover:text-emerald-300"
          >
            &larr; Back to home
          </Link>

          <h1 className="mt-6 text-4xl font-bold text-white">Changelog</h1>
          <p className="mt-3 text-zinc-400">
            User-visible product updates, newest first. Infrastructure-only
            changes don&apos;t show up here — they live in our engineering
            log.
          </p>

          <ul role="list" className="mt-12 space-y-10">
            {ENTRIES.map((entry, i) => (
              <li
                key={`${entry.date}-${i}`}
                className="border-l-2 border-zinc-800 pl-6"
              >
                <div className="flex items-center gap-3">
                  <time
                    dateTime={entry.date}
                    className="font-mono text-xs uppercase tracking-wider text-zinc-500"
                  >
                    {entry.date}
                  </time>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ring-1 ${CATEGORY_TINT[entry.category]}`}
                  >
                    {CATEGORY_LABEL[entry.category]}
                  </span>
                </div>
                <h2 className="mt-2 text-lg font-semibold text-white">
                  {entry.title}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  {entry.body}
                </p>
              </li>
            ))}
          </ul>
        </article>
      </main>
      <Footer />
    </>
  );
}
