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
  if (score >= 85) return { label: "Few recorded deductions", tone: "excellent" };
  if (score >= 70) return { label: "Some recorded deductions", tone: "good" };
  if (score >= 50) return { label: "Several recorded deductions", tone: "fair" };
  if (score >= 30) return { label: "Many recorded deductions", tone: "poor" };
  return { label: "Large recorded deductions", tone: "critical" };
}

function bucketIntegrity(score: number): { label: string; tone: ScoreTone } {
  if (score >= 85) return { label: "Few heuristic deductions", tone: "excellent" };
  if (score >= 70) return { label: "Some heuristic deductions", tone: "good" };
  if (score >= 50) return { label: "Several heuristic deductions", tone: "fair" };
  if (score >= 30) return { label: "Many heuristic deductions", tone: "poor" };
  return { label: "Large heuristic deductions", tone: "critical" };
}

export function explainCredibility(input: CredibilityInputs): ScoreExplanation {
  if (input.score == null) {
    return {label: "Assessment unavailable", tone: "fair",
      summary: "Required verification evidence is missing. Available findings do not establish accuracy or inaccuracy.",
      reasons: ["Review the status, coverage and available findings."]};
  }
  const score = input.score;
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
  if (ai >= 10) {
    reasons.push(`AI style estimate: ${ai.toFixed(0)}% in sampled paragraphs; this is separate from factual accuracy`);
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
    reasons.push("No citation findings available; references may not have been checked");
  }

  if (reasons.length === 0) {
    reasons.push(
      "No listed scored findings in this sample; unassessed content may contain issues"
    );
  }

  const summary = "This score summarizes recorded findings within the analyzed sample. Inspect claims, citation signals and coverage; it does not certify accuracy or authorship.";

  return { label, tone, summary, reasons };
}

export function explainIntegrity(input: IntegrityInputs): ScoreExplanation {
  if (input.score == null) {
    return {
      label: "Assessment unavailable", tone: "fair",
      summary: "Required evidence is missing or a step failed. Available publications do not establish integrity or misconduct.",
      reasons: ["Review citation coverage and the available evidence before drawing a conclusion."],
    };
  }
  const score = input.score;
  const { label, tone } = bucketIntegrity(score);
  const reasons: string[] = [];

  const self = input.selfCitationRate ?? 0;
  const topic = input.topicRelevanceScore ?? 1;
  const flags = input.flagCount ?? 0;
  const pubs = input.publicationsCount ?? 0;

  if (self >= 0.4) {
    reasons.push(`Very high sampled self-citation (${(self * 100).toFixed(0)}%)`);
  } else if (self >= 0.25) {
    reasons.push(`Elevated sampled self-citation (${(self * 100).toFixed(0)}%)`);
  }
  if (input.topicRelevanceScore != null && topic < 0.5) {
    reasons.push(
      `Average estimated paper-to-venue topic match: ${(topic * 100).toFixed(0)}%`
    );
  }
  if (flags > 0) {
    reasons.push(`${flags} sample observation${flags === 1 ? "" : "s"} available for review`);
  }
  if (pubs > 0 && pubs < 3) {
    reasons.push("Limited publication history for confident assessment");
  }

  if (reasons.length === 0) {
    reasons.push(
      "No listed sample observations; this does not establish absence of misconduct."
    );
  }

  const summary = "This heuristic reflects a sampled citation record, not a validated assessment of a person's integrity. Incoming citation concentration does not establish a ring or misconduct; inspect the evidence and coverage.";

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
