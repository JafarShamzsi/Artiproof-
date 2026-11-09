import { describe, expect, it } from "vitest";

import { explainCredibility, explainIntegrity, explainScore } from "./scoreExplanation";

describe("explainCredibility", () => {
  it("labels scores by bucket", () => {
    expect(explainCredibility({ score: 95 }).label).toBe("Few recorded deductions");
    expect(explainCredibility({ score: 75 }).label).toBe("Some recorded deductions");
    expect(explainCredibility({ score: 55 }).label).toBe("Several recorded deductions");
    expect(explainCredibility({ score: 40 }).label).toBe("Many recorded deductions");
    expect(explainCredibility({ score: 10 }).label).toBe("Large recorded deductions");
  });

  it("does not equate missing evidence with a critical zero", () => {
    expect(explainCredibility({ score: null }).label).toBe("Assessment unavailable");
    expect(explainCredibility({ score: undefined }).label).toBe("Assessment unavailable");
  });

  it("flags misinformation count with singular/plural copy", () => {
    const one = explainCredibility({ score: 60, misinfoCount: 1 });
    expect(one.reasons).toContain("1 misinformation claim detected");
    const many = explainCredibility({ score: 60, misinfoCount: 3 });
    expect(many.reasons).toContain("3 misinformation claims detected");
  });

  it("uses graduated AI thresholds (low/mid/high)", () => {
    const high = explainCredibility({ score: 60, aiPercent: 50 });
    expect(high.reasons.some((r) => r.includes("separate from factual accuracy"))).toBe(true);
    expect(high.reasons.some((r) => r.includes("50%"))).toBe(true);

    const mid = explainCredibility({ score: 60, aiPercent: 20 });
    expect(mid.reasons.some((r) => r.includes("AI style estimate"))).toBe(true);

    // Below the 10% mid threshold, no explicit "AI-generated" detection
    // reason should appear (the fallback default-clean reason may still
    // mention "low AI signal" — that's the positive framing).
    const low = explainCredibility({ score: 80, aiPercent: 5 });
    expect(low.reasons.some((r) => /Some AI-generated/.test(r))).toBe(false);
    expect(low.reasons.some((r) => /\d+% of text appears AI-generated/.test(r))).toBe(false);
  });

  it("falls back to a default reason when no specific issue applies", () => {
    const clean = explainCredibility({
      score: 88,
      misinfoCount: 0,
      aiPercent: 0,
      retractedCitations: 0,
      brokenCitations: 0,
      citationsTotal: 5,
    });
    expect(clean.reasons.length).toBe(1);
    expect(clean.reasons[0]).toContain("unassessed content may contain issues");
  });
});

describe("explainIntegrity", () => {
  it.each([null, undefined])("keeps missing evidence separate from zero (%s)", (score) => {
    expect(explainIntegrity({ score }).label).toBe("Assessment unavailable");
    expect(explainIntegrity({ score: 0 }).label).not.toBe("Assessment unavailable");
  });

  it("does not turn high scores into a clean bill of health", () => {
    const explanation = explainIntegrity({ score: 100 });
    expect(explanation.summary).toContain("not a validated assessment");
    expect(explanation.reasons.join(" ")).toContain("does not establish absence of misconduct");
    expect(explanation.label).not.toBe("Exemplary");
  });

  it("describes topic match as an estimate, including a real zero", () => {
    expect(explainIntegrity({ score: 80, topicRelevanceScore: 0 }).reasons)
      .toContain("Average estimated paper-to-venue topic match: 0%");
  });

  it("labels scores by bucket", () => {
    expect(explainIntegrity({ score: 90 }).label).toBe("Few heuristic deductions");
    expect(explainIntegrity({ score: 75 }).label).toBe("Some heuristic deductions");
    expect(explainIntegrity({ score: 55 }).label).toBe("Several heuristic deductions");
    expect(explainIntegrity({ score: 35 }).label).toBe("Many heuristic deductions");
    expect(explainIntegrity({ score: 10 }).label).toBe("Large heuristic deductions");
  });

  it("calls out very-high and elevated self-citation distinctly", () => {
    const very = explainIntegrity({ score: 40, selfCitationRate: 0.5 });
    expect(very.reasons.some((r) => r.includes("Very high sampled self-citation"))).toBe(true);
    const elevated = explainIntegrity({ score: 60, selfCitationRate: 0.3 });
    expect(elevated.reasons.some((r) => r.includes("Elevated sampled self-citation"))).toBe(true);
    const ok = explainIntegrity({ score: 80, selfCitationRate: 0.1 });
    expect(ok.reasons.some((r) => /self-citation/i.test(r))).toBe(false);
  });

  it("warns on thin publication history", () => {
    const thin = explainIntegrity({ score: 70, publicationsCount: 2 });
    expect(thin.reasons.some((r) => r.includes("Limited publication history"))).toBe(true);
  });
});

describe("explainScore dispatcher", () => {
  it("routes credibility inputs to explainCredibility", () => {
    const a = explainScore("credibility", { score: 90 });
    expect(a.label).toBe("Few recorded deductions");
  });

  it("routes integrity inputs to explainIntegrity", () => {
    const a = explainScore("integrity", { score: 90 });
    expect(a.label).toBe("Few heuristic deductions");
  });
});
