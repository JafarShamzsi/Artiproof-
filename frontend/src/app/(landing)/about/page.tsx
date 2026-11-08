import Image from "next/image";
import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "About ArtiProof — Research Integrity, Made Auditable",
  description:
    "ArtiProof is built by a small team in Baku for universities across Azerbaijan and the Eastern Partnership region. Meet the people behind the platform.",
};

/**
 * /about — public team + story page. Linked from the landing footer and
 * exposed in the sitemap. The team images live under /public/team/ as
 * compressed WebPs (Phase 0). Alt text describes role + name so screen
 * readers and search snippets get useful context, not just "image".
 *
 * Real names + roles are placeholders until the team approves their
 * public bio copy. Update this file when bios firm up; the image
 * filenames are stable (member-1 … member-4).
 */

interface TeamMember {
  name: string;
  role: string;
  bio: string;
  image: string;
}

const TEAM: TeamMember[] = [
  {
    name: "Team Member 1",
    role: "Founder · Engineering",
    bio: "Backend pipeline, scoring engines, and the integrity governance layer.",
    image: "/team/member-1.webp",
  },
  {
    name: "Team Member 2",
    role: "Frontend & Product",
    bio: "Dashboard, report compose, and the institutional-buyer experience.",
    image: "/team/member-2.webp",
  },
  {
    name: "Team Member 3",
    role: "Research & Methodology",
    bio: "Citation analysis, ring detection thresholds, and benchmark validation.",
    image: "/team/member-3.webp",
  },
  {
    name: "Team Member 4",
    role: "Partnerships & Outreach",
    bio: "University engagement across the Eastern Partnership region.",
    image: "/team/member-4.webp",
  },
];

export default function AboutPage() {
  return (
    <>
      <Navbar />
      <main
        id="main-content"
        tabIndex={-1}
        className="relative z-10 min-h-[100dvh] bg-zinc-950 pb-24 pt-32"
      >
        <article className="mx-auto max-w-4xl px-6 text-zinc-300">
          <Link
            href="/"
            className="text-sm text-emerald-400 hover:text-emerald-300"
          >
            &larr; Back to home
          </Link>

          <h1 className="mt-6 text-4xl font-bold text-white">About ArtiProof</h1>
          <p className="mt-4 max-w-2xl text-lg text-zinc-400">
            ArtiProof is a research-integrity platform built by a small team
            in Baku. We run five integrity engines — plagiarism, AI content
            detection, citation-ring detection, citation accessibility, and
            researcher-integrity scoring — on a single submission and return a
            credibility score with a per-deduction breakdown that researchers
            and committee members can defend in writing.
          </p>

          <section className="mt-16">
            <h2 className="text-2xl font-semibold text-white">Our story</h2>
            <p className="mt-4 max-w-2xl text-zinc-400">
              We built ArtiProof for the research integrity offices we&apos;ve
              talked to across Azerbaijan and the Eastern Partnership — deans,
              grant program managers, and journal editors who needed scoring
              they could defend in front of a faculty meeting, not a black box.
              That&apos;s why every score comes with a per-deduction
              breakdown, why prompts and model versions are recorded on every
              analysis, and why &ldquo;citation ring&rdquo; in our UI says
              &ldquo;mutual citation pattern&rdquo; with a disclaimer rather
              than a verdict.
            </p>
          </section>

          <section className="mt-16">
            <h2 className="text-2xl font-semibold text-white">The team</h2>
            <p className="mt-3 max-w-2xl text-zinc-400">
              Four people, one product. We answer our own support email.
            </p>

            <ul
              role="list"
              className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-2"
            >
              {TEAM.map((m) => (
                <li
                  key={m.name}
                  className="flex gap-5 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5"
                >
                  <Image
                    src={m.image}
                    alt={`Portrait of ${m.name}, ${m.role}`}
                    width={80}
                    height={80}
                    className="h-20 w-20 flex-shrink-0 rounded-full object-cover"
                  />
                  <div>
                    <h3 className="text-base font-semibold text-white">
                      {m.name}
                    </h3>
                    <p className="text-xs uppercase tracking-wider text-emerald-400">
                      {m.role}
                    </p>
                    <p className="mt-2 text-sm text-zinc-400">{m.bio}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="mt-16">
            <h2 className="text-2xl font-semibold text-white">Get in touch</h2>
            <p className="mt-3 max-w-2xl text-zinc-400">
              Press, partnerships, or institutional pilots:{" "}
              <a
                href="mailto:info@example.invalid"
                className="text-emerald-400 hover:text-emerald-300"
              >
                info@example.invalid
              </a>
              .
            </p>
            <p className="mt-3 max-w-2xl text-zinc-400">
              Security disclosures:{" "}
              <Link
                href="/security"
                className="text-emerald-400 hover:text-emerald-300"
              >
                /security
              </Link>
              .
            </p>
          </section>
        </article>
      </main>
      <Footer />
    </>
  );
}
