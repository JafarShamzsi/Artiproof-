export type ScoreTone = "excellent" | "good" | "fair" | "poor" | "critical";

export interface ScoreExplanation {
  label: string;
  tone: ScoreTone;
  summary: string;
  reasons: string[];
}

export interface CredibilityInputs {
  score: number | null | undefined;
  aiPercent?: number | null;
  misinfoCount?: number | null;
  citationsTotal?: number | null;
  retractedCitations?: number | null;
  brokenCitations?: number | null;
}

export interface IntegrityInputs {
  score: number | null | undefined;
  selfCitationRate?: number | null;
  topicRelevanceScore?: number | null;
  flagCount?: number | null;
  publicationsCount?: number | null;
}

function bucketCredibility(score: number): { label: string; tone: ScoreTone } {
  if (score >= 85) return { label: "Highly Credible", tone: "excellent" };
  if (score >= 70) return { label: "Credible", tone: "good" };
  if (score >= 50) return { label: "Mixed", tone: "fair" };
  if (score >= 30) return { label: "Low Credibility", tone: "poor" };
  return { label: "Not Credible", tone: "critical" };
}

function bucketIntegrity(score: number): { label: string; tone: ScoreTone } {
  if (score >= 85) return { label: "Exemplary", tone: "excellent" };
  if (score >= 70) return { label: "Sound", tone: "good" };
  if (score >= 50) return { label: "Mixed", tone: "fair" };
  if (score >= 30) return { label: "Weak", tone: "poor" };
  return { label: "Serious Concerns", tone: "critical" };
}

export function explainCredibility(input: CredibilityInputs): ScoreExplanation {
  const score = input.score ?? 0;
  const { label, tone } = bucketCredibility(score);
  const reasons: string[] = [];

  const misinfo = input.misinfoCount ?? 0;
  const ai = input.aiPercent ?? 0;
  const retracted = input.retractedCitations ?? 0;
  const broken = input.brokenCitations ?? 0;
  const citations = input.citationsTotal ?? 0;

  if (misinfo > 0) {
    reasons.push(
      `${misinfo} misinformation claim${misinfo === 1 ? "" : "s"} detected`
    );
  }
  if (ai >= 30) {
    reasons.push(`${ai.toFixed(0)}% of text appears AI-generated`);
  } else if (ai >= 10) {
    reasons.push(`Some AI-generated content (${ai.toFixed(0)}%)`);
  }
  if (retracted > 0) {
    reasons.push(
      `${retracted} retracted citation${retracted === 1 ? "" : "s"}`
    );
  }
  if (broken > 0) {
    reasons.push(
      `${broken} inaccessible citation link${broken === 1 ? "" : "s"}`
    );
  }
  if (citations === 0 && score < 70) {
    reasons.push("No citations found");
  }

  if (reasons.length === 0) {
    reasons.push(
      score >= 70
        ? "Claims verified, citations intact, low AI signal"
        : "No single issue dominates — score reflects overall signal strength"
    );
  }

  const summary =
    tone === "excellent"
      ? "This source passes every integrity check with room to spare — treat it as reliable."
      : tone === "good"
      ? "Generally trustworthy. Minor concerns exist but nothing disqualifying."
      : tone === "fair"
      ? "Mixed signals. Verify the key claims and citations independently before relying on this source."
      : tone === "poor"
      ? "Substantial issues detected. Treat claims here with caution and cross-reference primary sources."
      : "Severe credibility problems. Do not rely on this source without independent confirmation.";

  return { label, tone, summary, reasons };
}

export function explainIntegrity(input: IntegrityInputs): ScoreExplanation {
  const score = input.score ?? 0;
  const { label, tone } = bucketIntegrity(score);
  const reasons: string[] = [];

  const self = input.selfCitationRate ?? 0;
  const topic = input.topicRelevanceScore ?? 1;
  const flags = input.flagCount ?? 0;
  const pubs = input.publicationsCount ?? 0;

  if (self >= 0.4) {
    reasons.push(`Very high self-citation (${(self * 100).toFixed(0)}%)`);
  } else if (self >= 0.25) {
    reasons.push(`Elevated self-citation (${(self * 100).toFixed(0)}%)`);
  }
  if (topic > 0 && topic < 0.5) {
    reasons.push(
      `Only ${(topic * 100).toFixed(0)}% of work stays within core research topic`
    );
  }
  if (flags > 0) {
    reasons.push(`${flags} integrity flag${flags === 1 ? "" : "s"} raised`);
  }
  if (pubs > 0 && pubs < 3) {
    reasons.push("Limited publication history for confident assessment");
  }

  if (reasons.length === 0) {
    reasons.push(
      score >= 70
        ? "Healthy citation patterns, strong topic focus, no flags"
        : "No single red flag dominates — score reflects overall signal strength"
    );
  }

  const summary =
    tone === "excellent"
      ? "Strong publication record with clean citation patterns and no integrity red flags."
      : tone === "good"
      ? "Solid researcher profile. A few minor signals but nothing that undermines the record."
      : tone === "fair"
      ? "Worth a closer look — citation or topic patterns suggest the record needs scrutiny."
      : tone === "poor"
      ? "Multiple integrity concerns. Review the flagged publications before citing this work."
      : "Severe integrity issues. Independent verification is strongly advised before relying on this record.";

  return { label, tone, summary, reasons };
}

export function explainScore(
  kind: "credibility" | "integrity",
  inputs: CredibilityInputs | IntegrityInputs
): ScoreExplanation {
  return kind === "credibility"
    ? explainCredibility(inputs as CredibilityInputs)
    : explainIntegrity(inputs as IntegrityInputs);
}
