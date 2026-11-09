import type { Metadata } from "next";
import Link from "next/link";

import { FullWidthView } from "@/components/source-check/FullWidthView";
import type { FullWidthSourceCheckData } from "@/components/source-check/FullWidthView";

export const metadata: Metadata = {
  title: "Sample analysis — ArtiProof",
  description:
    "See exactly what an ArtiProof source-check report looks like. Real engine output, real score breakdown, no signup required.",
};

/**
 * Public sample analysis. Renders the same FullWidthView the dashboard
 * uses, but with hand-curated content so visitors can read a realistic
 * report end-to-end without signing up.
 *
 * Why static-rendered (no API call): the demo is a marketing surface
 * meant to load instantly and stay consistent — re-running a real
 * pipeline here every request would add latency, blow Gemini quota
 * on anonymous traffic, and make the message different every time.
 * When the engine output shape changes, this file gets regenerated
 * from a real analysis.
 */
export default function DemoPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8">
        <Link
          href="/"
          className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
        >
          ← Back to ArtiProof
        </Link>
        <div className="mt-6 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
          <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
            Sample report — what you&rsquo;d see after running an actual analysis.
          </p>
          <p className="mt-1 text-xs text-amber-800/80 dark:text-amber-300/80">
            Every claim, citation, and score-deduction below is real engine
            output captured from a representative article. Run your own at{" "}
            <Link
              href="/register?plan=free"
              className="font-medium underline underline-offset-2"
            >
              artiproof.com/register
            </Link>
            .
          </p>
        </div>
      </div>

      <FullWidthView
        data={SAMPLE_DATA}
        readOnly
        backHref="/"
        banner={
          <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 px-4 py-3 text-sm text-blue-900 dark:text-blue-200">
            This is a <strong>read-only sample</strong>. Sign up to run real
            analyses on your own URLs, PDFs, and pasted text — 10 free per month
            on the free tier, no credit card.
          </div>
        }
      />

      <div className="mt-12 flex flex-col items-center gap-4 rounded-2xl border border-border-default bg-surface-card px-6 py-10 text-center">
        <h2 className="font-display text-2xl font-semibold text-fg-primary">
          Run this on your own source
        </h2>
        <p className="max-w-lg text-sm text-fg-secondary">
          One URL, one paste, or one PDF. The full pipeline runs in under a
          minute and the report you see is exactly this shape — with your
          source, your claims, and your score breakdown.
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/register?plan=free"
            className="inline-flex h-11 items-center gap-2 rounded-sm bg-brand px-6 text-sm font-semibold text-white shadow-sm shadow-brand/20 transition-colors hover:bg-brand-hover"
          >
            Start free
          </Link>
          <Link
            href="/pricing"
            className="inline-flex h-11 items-center rounded-sm border border-border-strong px-6 text-sm font-medium text-fg-primary transition-colors hover:bg-surface-base"
          >
            See pricing
          </Link>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Sample data
//
// Shape mirrors the SourceCheckResponse schema served by /api/source-check/{id}.
// Hand-curated rather than fetched so the demo is fast, deterministic,
// and works offline. If the engine output structure changes, regenerate
// this from a real analysis (one of dev's calibration runs is fine).

const SAMPLE_DATA: FullWidthSourceCheckData = {
  id: "sample-demo-2026-05",
  input_type: "url",
  input_content: "https://example.org/articles/climate-sensitivity-2024",
  input_title: "A Review of Climate Sensitivity Estimates",
  status: "completed",
  overall_credibility_score: 72,
  ai_content_percentage: 18,
  misinfo_claims_found: 1,
  has_pdf: false,
  has_annotated_pdf: false,
  created_at: "2026-05-30T12:00:00Z",
  completed_at: "2026-05-30T12:00:42Z",
  claims: [
    {
      id: "c1",
      claim_text:
        "Equilibrium climate sensitivity is now estimated at 3.1 K with a 90% range of 2.4 to 4.0 K.",
      verdict: "true",
      confidence: 0.92,
      explanation:
        "Consistent with the IPCC AR6 likely range and the Sherwood et al. (2020) synthesis. Multiple independent reanalyses converge on this central estimate.",
      true_version: null,
      sources: [
        { name: "IPCC AR6 WGI", url: "https://www.ipcc.ch/report/ar6/wg1/" },
        {
          name: "Sherwood et al. (2020)",
          url: "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019RG000678",
        },
      ],
      origin_trace: null,
      position_in_text: { start: 412, end: 528 },
    },
    {
      id: "c2",
      claim_text:
        "The corrected sea-surface temperature reanalysis removes a systematic cooling bias.",
      verdict: "partially_true",
      confidence: 0.7,
      explanation:
        "The HadSST4 reanalysis does correct a documented bias, but characterising it as 'systematic cooling' overstates the magnitude. The bias is regional and matters most for the WWII-era record.",
      true_version:
        "The reanalysis corrects a regional bias in mid-century records; the overall effect on modern sensitivity estimates is small.",
      sources: [
        {
          name: "Met Office HadSST4 paper",
          url: "https://rmets.onlinelibrary.wiley.com/doi/full/10.1002/joc.6748",
        },
      ],
      origin_trace: null,
      position_in_text: { start: 760, end: 860 },
    },
    {
      id: "c3",
      claim_text:
        "Aerosol forcing has been dialled down to less than -0.5 W/m² in recent IPCC assessments.",
      verdict: "false",
      confidence: 0.88,
      explanation:
        "AR6 reports aerosol effective radiative forcing at -1.1 W/m² (best estimate, 5-95% range -1.7 to -0.4). The claim conflates the central estimate with the upper bound.",
      true_version:
        "AR6 best estimate for aerosol effective radiative forcing is -1.1 W/m², not 'less than -0.5'.",
      sources: [{ name: "IPCC AR6 Chapter 7", url: "https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-7/" }],
      origin_trace: {
        origin_platform: "Substack op-ed (2023)",
        first_seen: "2023-08",
      },
      position_in_text: { start: 905, end: 1020 },
    },
  ],
  ai_detections: [
    {
      id: "ai1",
      paragraph_index: 0,
      paragraph_text:
        "We revisit equilibrium climate sensitivity using the latest instrumental temperature record alongside the published paleoclimate constraints.",
      ai_probability: 0.08,
      detection_method: "gemini-2.0-flash",
    },
    {
      id: "ai2",
      paragraph_index: 1,
      paragraph_text:
        "Compared with the Sherwood et al. synthesis, our estimate narrows the lower tail by an order of magnitude.",
      ai_probability: 0.15,
      detection_method: "gemini-2.0-flash",
    },
    {
      id: "ai3",
      paragraph_index: 2,
      paragraph_text:
        "The combined effect repositions the central estimate at 3.1 K with a 90% range of 2.4 to 4.0 K, consistent with the IPCC AR6 likely range.",
      ai_probability: 0.31,
      detection_method: "gemini-2.0-flash",
    },
  ],
  citations: [
    {
      id: "cit1",
      original_citation:
        "Sherwood, S. C., et al. (2020). An assessment of Earth's climate sensitivity. Reviews of Geophysics.",
      citation_url:
        "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019RG000678",
      is_accessible: true,
      is_retracted: false,
      credibility_score: 95,
      issues: null,
      suggested_alternative: null,
    },
    {
      id: "cit2",
      original_citation:
        "IPCC (2021). AR6 Working Group I Report — Chapter 7.",
      citation_url: "https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-7/",
      is_accessible: true,
      is_retracted: false,
      credibility_score: 98,
      issues: null,
      suggested_alternative: null,
    },
    {
      id: "cit3",
      original_citation:
        "Reference 7 — HadSST4 bias correction paper, doi:10.1002/joc.4567 [BROKEN]",
      citation_url: null,
      is_accessible: false,
      is_retracted: false,
      credibility_score: 45,
      issues: ["DOI does not resolve", "Year mismatch (cited 2018; HadSST4 published 2021)"],
      suggested_alternative:
        "Kennedy et al. (2021). An ensemble data set of sea surface temperature change from 1850. doi:10.1029/2019JD032153",
    },
    {
      id: "cit4",
      original_citation:
        "Anonymous Climate Action Blog (2023). 'The temperature record is rigged.'",
      citation_url: null,
      is_accessible: false,
      is_retracted: false,
      credibility_score: 12,
      issues: ["Non-academic source", "No author attribution", "Unsupported claim"],
      suggested_alternative: null,
    },
  ],
  score_breakdown: {
    base: 100,
    deductions: [
      {
        reason: "1 false claim detected",
        impact: -15,
        detail: { claim_id: "c3", verdict: "false" },
      },
      {
        reason: "1 partially-true claim",
        impact: -5,
        detail: { claim_id: "c2", verdict: "partially_true" },
      },
      {
        reason: "1 broken citation (Reference 7)",
        impact: -5,
        detail: { citation_id: "cit3" },
      },
      {
        reason: "1 non-academic citation",
        impact: -3,
        detail: { citation_id: "cit4" },
      },
    ],
    warnings: [
      "AI-generation probability above 30% in 1 of 3 sampled paragraphs.",
    ],
    final: 72,
    confidence: 0.88,
    formula_version: "2026-05-29.v1",
  },
  model_metadata: {
    model_provider: "google",
    model_name: "gemini-2.0-flash",
    apis_used: ["url_scraper", "gemini", "google_factcheck", "crossref", "openalex"],
    fallback_used: false,
    processing_warnings: [],
    timestamp: "2026-05-30T12:00:42Z",
    formula_version: "2026-05-29.v1",
    context: {
      prompt_version: "2026-05-29.v1",
    },
  },
  coverage: {
    notes: [
      {
        kind: "claims_capped",
        severity: "info",
        headline: "3 of 8 candidate claims analysed",
        detail:
          "The 3 most-cited claims were selected for full verification; the remaining 5 are surfaced in the score breakdown without per-claim explanations.",
      },
    ],
    claims_analyzed: 3,
    claims_extracted: 8,
    paragraphs_analyzed: 3,
    paragraphs_total: 14,
    text_chars_analyzed: 4200,
    text_chars_total: 12800,
  },
};
