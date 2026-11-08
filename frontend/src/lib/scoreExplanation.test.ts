import { describe, expect, it } from "vitest";

import { explainCredibility, explainIntegrity, explainScore } from "./scoreExplanation";

describe("explainCredibility", () => {
  it("labels scores by bucket", () => {
    expect(explainCredibility({ score: 95 }).label).toBe("Highly Credible");
    expect(explainCredibility({ score: 75 }).label).toBe("Credible");
    expect(explainCredibility({ score: 55 }).label).toBe("Mixed");
    expect(explainCredibility({ score: 40 }).label).toBe("Low Credibility");
    expect(explainCredibility({ score: 10 }).label).toBe("Not Credible");
  });

  it("treats missing score as 0 (critical)", () => {
    expect(explainCredibility({ score: null }).tone).toBe("critical");
    expect(explainCredibility({ score: undefined }).tone).toBe("critical");
  });

  it("flags misinformation count with singular/plural copy", () => {
    const one = explainCredibility({ score: 60, misinfoCount: 1 });
    expect(one.reasons).toContain("1 misinformation claim detected");
    const many = explainCredibility({ score: 60, misinfoCount: 3 });
    expect(many.reasons).toContain("3 misinformation claims detected");
  });

  it("uses graduated AI thresholds (low/mid/high)", () => {
    const high = explainCredibility({ score: 60, aiPercent: 50 });
    expect(high.reasons.some((r) => r.includes("AI-generated"))).toBe(true);
    expect(high.reasons.some((r) => r.includes("50%"))).toBe(true);

    const mid = explainCredibility({ score: 60, aiPercent: 20 });
    expect(mid.reasons.some((r) => r.includes("Some AI-generated"))).toBe(true);

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
    expect(clean.reasons[0]).toMatch(/citations|verified|signal/i);
  });
});

describe("explainIntegrity", () => {
  it("labels scores by bucket", () => {
    expect(explainIntegrity({ score: 90 }).label).toBe("Exemplary");
    expect(explainIntegrity({ score: 75 }).label).toBe("Sound");
    expect(explainIntegrity({ score: 55 }).label).toBe("Mixed");
    expect(explainIntegrity({ score: 35 }).label).toBe("Weak");
    expect(explainIntegrity({ score: 10 }).label).toBe("Serious Concerns");
  });

  it("calls out very-high and elevated self-citation distinctly", () => {
    const very = explainIntegrity({ score: 40, selfCitationRate: 0.5 });
    expect(very.reasons.some((r) => r.includes("Very high self-citation"))).toBe(true);
    const elevated = explainIntegrity({ score: 60, selfCitationRate: 0.3 });
    expect(elevated.reasons.some((r) => r.includes("Elevated self-citation"))).toBe(true);
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
    expect(a.label).toBe("Highly Credible");
  });

  it("routes integrity inputs to explainIntegrity", () => {
    const a = explainScore("integrity", { score: 90 });
    expect(a.label).toBe("Exemplary");
  });
});
