import { scoreColor, scoreSolidBorderColor } from "@/lib/colors";
import type { CitationRingFlags, IntegrityBreakdown } from "@/types/api";

export function ResearcherScore({ score, label = "Integrity score" }: {
  score: number | null; label?: string;
}) {
  if (score == null) {
    return <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 border-zinc-300 px-1 text-center text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">Score unavailable</div>;
  }
  return (
    <div role="meter" aria-label={label} aria-valuenow={Math.round(score)}
      aria-valuemin={0} aria-valuemax={100} aria-valuetext={`${Math.round(score)} out of 100`}
      className={`flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 ${scoreColor(score)} ${scoreSolidBorderColor(score)}`}>
      <span className="text-2xl font-bold">{Math.round(score)}</span>
    </div>
  );
}

export function ResearcherCoverage({ findings, assessment }: { findings: CitationRingFlags | null; assessment?: IntegrityBreakdown | null }) {
  const coverage = findings?.coverage;
  const authors = findings?.citation_concentration ?? [];
  return (
    <section aria-label="Citation evidence coverage" className="space-y-2 rounded-md border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-950/40 dark:text-zinc-300">
      <p>Incoming citation samples do not establish reciprocal citation rings or misconduct. Adjusted metrics are estimates from the sampled self-citation rate.</p>
      {assessment?.final === null && assessment.explanation && <p>{assessment.explanation}</p>}
      {coverage?.papers_attempted == null && <p>Citation coverage is not recorded for this analysis. Rerun it to collect current evidence before relying on historical scores or ring labels.</p>}
      {coverage?.papers_attempted != null && coverage.papers_succeeded != null && (
        <p>{coverage.papers_succeeded} of {coverage.papers_attempted} attempted publication lookups succeeded. Each lookup samples up to {coverage.citations_per_paper_limit ?? 50} incoming citations.</p>
      )}
      {findings?.citation_evidence_status === "partial" && <p>Some citation evidence is unavailable or unidentified. The overall assessment is unavailable.</p>}
      {(coverage?.unavailable_paper_ids?.length ?? 0) > 0 && <p>{coverage?.unavailable_paper_ids?.length} citation lookup{coverage?.unavailable_paper_ids?.length === 1 ? "" : "s"} failed.</p>}
      {authors.length > 0 && (
        <ul className="space-y-2">
          {authors.map((author) => (
            <li key={author.id}>
              {author.name}: {author.citations_to_target} incoming citation relationships in this sample.
              {(author.relationships?.length ?? 0) > 0 && (
                <ul className="ml-4 list-disc">
                  {author.relationships.slice(0, 5).map((relationship) => (
                    <li key={`${relationship.citing_paper_id}-${relationship.cited_paper_id}`}>
                      <a className="underline" href={`https://www.semanticscholar.org/paper/${encodeURIComponent(relationship.citing_paper_id)}`} target="_blank" rel="noopener noreferrer">Citing paper</a>
                      {" → "}
                      <a className="underline" href={`https://www.semanticscholar.org/paper/${encodeURIComponent(relationship.cited_paper_id)}`} target="_blank" rel="noopener noreferrer">Cited paper</a>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
