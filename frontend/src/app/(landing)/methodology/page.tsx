import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Brain,
  GitBranch,
  Shield,
  Users,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Methodology — ArtiProof",
  description:
    "How ArtiProof evaluates source credibility and researcher integrity. The five engines, the scoring formula, the data sources, and the limits we publish so reviewers can independently verify our results.",
};

/**
 * Public methodology page — answers the #1 question institutional buyers
 * ask before procurement: "how does this actually work, and where does
 * it fail?" The goal is to be specific enough that a domain expert can
 * decide whether to trust the platform without us telling them they should.
 *
 * Each engine section names: what it does, what data sources it uses,
 * what its weight in the final score is, and where it's known to fail.
 * The honest limits paragraph is intentional — institutional reviewers
 * expect a vendor that lies about coverage and we want them to expect
 * the opposite of us.
 */
export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
      <Link
        href="/"
        className="text-sm text-fg-secondary hover:text-fg-primary"
      >
        ← Back to ArtiProof
      </Link>

      <header className="mt-8 border-b border-border-default pb-8">
        <p className="label-eyebrow text-brand-fg">Methodology</p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-fg-primary sm:text-5xl">
          How ArtiProof reads a source
        </h1>
        <p className="editorial-italic mt-4 max-w-2xl text-lg leading-relaxed text-fg-secondary">
          Five engines, five distinct signals, one composite score. Every
          deduction is recorded next to its source so a reviewer can replay
          the decision.
        </p>
      </header>

      {/* Pipeline overview */}
      <section className="mt-12">
        <h2 className="font-display text-2xl font-semibold text-fg-primary">
          Pipeline
        </h2>
        <p className="mt-3 text-base leading-relaxed text-fg-primary">
          An analysis runs the five engines in two phases. Phase one extracts
          the artifacts from the source: claims, paragraphs, citations,
          authorship. Phase two scores each artifact against external
          ground truth and computes the composite credibility number.
          Engine output, prompts, and model versions are stored alongside
          every run so disputes can be replayed against the exact code
          and prompt revision that produced the score.
        </p>
        <ol className="mt-6 space-y-3 border-l border-border-default pl-6">
          {PIPELINE_STEPS.map((step, i) => (
            <li key={step.title} className="relative">
              <span
                aria-hidden="true"
                className="absolute -left-[28px] flex h-5 w-5 items-center justify-center rounded-full border border-border-default bg-surface-card text-[10px] font-medium text-fg-secondary"
              >
                {i + 1}
              </span>
              <div className="text-sm text-fg-primary">
                <strong>{step.title}.</strong> {step.detail}
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* Engines */}
      <section className="mt-16">
        <h2 className="font-display text-2xl font-semibold text-fg-primary">
          The five engines
        </h2>
        <p className="mt-3 text-base leading-relaxed text-fg-primary">
          Every score is the sum of these five engines&rsquo; deductions,
          starting from 100. The weights below ship with each report under
          the <code className="rounded bg-surface-card px-1 py-0.5 text-xs">formula_version</code>
          {" "}field so you can confirm the version your report was scored
          against didn&rsquo;t shift in the meantime.
        </p>

        <div className="mt-8 grid gap-6 md:grid-cols-2">
          {ENGINES.map((engine) => (
            <article
              key={engine.name}
              className="rounded-lg border border-border-default bg-surface-card p-6"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-brand/10 text-brand-fg">
                  <engine.icon className="h-5 w-5" />
                </div>
                <h3 className="font-display text-lg font-semibold text-fg-primary">
                  {engine.name}
                </h3>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-fg-primary">
                {engine.does}
              </p>
              <dl className="mt-4 space-y-2 text-xs">
                <div className="flex gap-2">
                  <dt className="w-28 shrink-0 font-medium text-fg-secondary">
                    Sources
                  </dt>
                  <dd className="text-fg-primary">{engine.sources}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-28 shrink-0 font-medium text-fg-secondary">
                    Max impact
                  </dt>
                  <dd className="text-fg-primary">{engine.maxImpact}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-28 shrink-0 font-medium text-fg-secondary">
                    Known limits
                  </dt>
                  <dd className="text-fg-primary">{engine.knownLimits}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      {/* Scoring */}
      <section className="mt-16">
        <h2 className="font-display text-2xl font-semibold text-fg-primary">
          Scoring formula
        </h2>
        <p className="mt-3 text-base leading-relaxed text-fg-primary">
          Source credibility starts at 100 and walks down by deductions.
          Researcher integrity starts at 100 and walks down by the same
          mechanism but with different weights. Both are clamped to the
          range 0&ndash;100.
        </p>
        <div className="mt-4 rounded-lg border border-border-default bg-surface-card p-4 font-mono text-xs leading-relaxed text-fg-primary">
          credibility = max(0, min(100, base
          <br />
          &nbsp;&nbsp;&minus; 15 × false_claims
          <br />
          &nbsp;&nbsp;&minus; 10 × misleading_claims
          <br />
          &nbsp;&nbsp;&minus; 5 × partially_true_claims
          <br />
          &nbsp;&nbsp;&minus; 3 × unverified_claims
          <br />
          &nbsp;&nbsp;&minus; 0.3 × max(0, ai_percent &minus; 50)
          <br />
          &nbsp;&nbsp;&minus; 15 × retracted_citations
          <br />
          &nbsp;&nbsp;&minus; 5 × inaccessible_citations)
        </div>
        <p className="mt-4 text-sm leading-relaxed text-fg-primary">
          Every deduction in the formula appears verbatim in the{" "}
          <code className="rounded bg-surface-card px-1 py-0.5 text-xs">
            score_breakdown.deductions
          </code>{" "}
          array of every report. The base value, intermediate sum, and clamp
          are all visible to the reviewer. No hidden coefficients.
        </p>
      </section>

      {/* Honest limits */}
      <section className="mt-16">
        <h2 className="font-display text-2xl font-semibold text-fg-primary">
          What ArtiProof is not
        </h2>
        <ul className="mt-4 space-y-3 border-l border-amber-500/40 pl-5 text-sm leading-relaxed text-fg-primary">
          <li>
            <strong>Not a plagiarism checker for unpublished work.</strong>{" "}
            The plagiarism signal relies on indexed and cited corpora. If
            you&rsquo;re checking against a private document repository,
            point us at it as a source &mdash; we don&rsquo;t guess at
            archives we don&rsquo;t have access to.
          </li>
          <li>
            <strong>Not a deepfake detector.</strong> The AI-content engine
            scores text for LLM-generation probability. Image and video
            content pass through unscored.
          </li>
          <li>
            <strong>Not a peer reviewer.</strong> ArtiProof can confirm
            that citations resolve, that claims agree with external
            ground truth, and that the author&rsquo;s pattern of
            self-citation is within norms. It does not evaluate the
            novelty or significance of the work.
          </li>
          <li>
            <strong>Not a substitute for retraction watch.</strong> We
            cross-check citations against CrossRef and OpenAlex. When
            those databases haven&rsquo;t indexed a recent retraction
            yet, ArtiProof can&rsquo;t see it either &mdash; expect a
            lag of days to weeks for fresh retractions.
          </li>
        </ul>
      </section>

      {/* Reproducibility */}
      <section className="mt-16">
        <h2 className="font-display text-2xl font-semibold text-fg-primary">
          Reproducibility
        </h2>
        <p className="mt-3 text-base leading-relaxed text-fg-primary">
          Every analysis stores the engine version, prompt version, and
          prompt hash that produced it. When a prompt is edited without
          a version bump, the next analysis fires a drift warning to
          our error tracker. Disputes get the same engine + same prompt
          + same external API snapshot at the time of the dispute.
        </p>
        <p className="mt-3 text-base leading-relaxed text-fg-primary">
          Institutional buyers get a separate audit log: the operator
          tier-change ledger and the per-call API metric (tokens, latency,
          model) for every analysis run by users in their organization.
        </p>
      </section>

      {/* CTA */}
      <section className="mt-16 flex flex-col items-center gap-4 rounded-2xl border border-border-default bg-surface-card px-6 py-10 text-center">
        <h2 className="font-display text-2xl font-semibold text-fg-primary">
          Try it on your own source
        </h2>
        <p className="max-w-lg text-sm text-fg-secondary">
          The free tier runs the full five-engine pipeline. No card required.
          Read the sample report first if you want to see what an analysis
          looks like before signing up.
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/register?plan=free"
            className="inline-flex h-11 items-center gap-2 rounded-sm bg-brand px-6 text-sm font-semibold text-white shadow-sm shadow-brand/20 transition-colors hover:bg-brand-hover"
          >
            Start free
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/demo"
            className="inline-flex h-11 items-center rounded-sm border border-border-strong px-6 text-sm font-medium text-fg-primary transition-colors hover:bg-surface-base"
          >
            See sample report
          </Link>
        </div>
      </section>
    </div>
  );
}

const PIPELINE_STEPS = [
  {
    title: "Ingest",
    detail:
      "Pull the source. URL: scrape with politeness + cite-pull. PDF: extract text and bounding boxes for annotation. Pasted text: tokenize and segment into paragraphs.",
  },
  {
    title: "Extract claims",
    detail:
      "An LLM lifts the verifiable factual statements out of the text. Opinions, rhetorical questions, and untestable predictions are skipped. Up to 15 claims per source.",
  },
  {
    title: "Verify in parallel",
    detail:
      "Each claim is cross-referenced against Google Fact Check Tools and an LLM panel. AI-generation probability is scored per paragraph. Citations are checked against CrossRef and OpenAlex for retraction status.",
  },
  {
    title: "Trace origins",
    detail:
      "False or misleading claims are traced to their likely point of origin (platform, publication, date) so a reader can see where the misinformation started.",
  },
  {
    title: "Score and explain",
    detail:
      "The composite score is computed by summing weighted deductions. Every deduction is preserved next to its evidence. Coverage caveats are surfaced when the source was sampled rather than fully analysed.",
  },
];

const ENGINES = [
  {
    name: "Claim extraction & fact-checking",
    icon: Shield,
    does:
      "An LLM segments the source into discrete, verifiable claims and assigns each a verdict (true / false / misleading / partially true / unverified) backed by named sources.",
    sources:
      "Google Fact Check Tools API; Gemini 2.0 Flash for inference; the model's training distribution as a fallback.",
    maxImpact:
      "Up to &minus;15 per false claim; up to &minus;10 per misleading. No upper cap on number of claims (top-15 sampled).",
    knownLimits:
      "Claims that are too long or compound get split inconsistently. Fact-check coverage is strongest for English-language political and scientific topics.",
  },
  {
    name: "AI-content detection",
    icon: Brain,
    does:
      "Scores each paragraph 0&ndash;1 for the probability that it was authored by an LLM. Signals include uniform sentence rhythm, lack of personal voice, and absence of domain-specific colloquialism.",
    sources:
      "Gemini 2.0 Flash with a calibrated prompt. No proprietary classifier.",
    maxImpact:
      "Probabilistic. Per-percent deductions kick in past 50% (&minus;0.3 per point above 50).",
    knownLimits:
      "Probabilistic by design. Edited or post-processed AI text reads cleaner than first-pass output. Always shipped with a confidence number; treat as one signal, not proof.",
  },
  {
    name: "Citation verification",
    icon: BookOpen,
    does:
      "Each citation in the source is resolved against CrossRef and OpenAlex. The engine flags broken (unresolvable), inaccessible (paywalled or gone), and retracted references.",
    sources:
      "CrossRef Works API; OpenAlex; the source's own citation list when scraped.",
    maxImpact: "Up to &minus;15 per retracted citation; up to &minus;5 per broken or inaccessible.",
    knownLimits:
      "Recent retractions (within days) may not be indexed yet. Behind-paywall citations are marked inaccessible rather than verified.",
  },
  {
    name: "Citation ring detection",
    icon: GitBranch,
    does:
      "Builds the local citation graph around the researcher and surfaces tightly-cyclic subgroups whose mutual citation rate exceeds normal field baselines.",
    sources:
      "Semantic Scholar; Scopus when an API key is provided; CrossRef for fallback.",
    maxImpact:
      "Researcher-tier signal: contributes to integrity_score adjustments and the citation_ring_flags array.",
    knownLimits:
      "Coverage gaps in non-English literature can hide rings that span Russian-, Chinese-, or Arabic-language venues. The 25% mutual-citation threshold is calibrated against representative samples of English-language CS/biology/medicine literature.",
  },
  {
    name: "Researcher integrity scoring",
    icon: Users,
    does:
      "Adjusts a researcher's h-index by stripping out self-citations and citations from suspected rings, then re-computing. Topic-relevance scoring flags publications outside the researcher's stated field.",
    sources:
      "Same as the ring detector. Publication list pulled from Semantic Scholar plus ORCID when available.",
    maxImpact:
      "Adjusted-vs-official h-index delta is the headline number. Per-publication flags are listed in the integrity report.",
    knownLimits:
      "Topic-relevance is bounded by the venue tagging in Semantic Scholar's training data. Career transitions (e.g. moving fields legitimately) can produce false positives.",
  },
] as const;
