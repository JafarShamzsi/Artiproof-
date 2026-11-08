import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ComponentProps } from "react";
import { FullWidthView } from "./FullWidthView";

describe("source check missing evidence", () => {
  it("shows unavailable assessments on shared and private failed checks", () => {
    const data: ComponentProps<typeof FullWidthView>["data"] = {
      id: "failed-check", input_type: "url", input_content: "https://example.com",
      input_title: null, status: "failed", overall_credibility_score: null,
      ai_content_percentage: null, misinfo_claims_found: null,
      created_at: "2026-10-31T00:00:00Z", completed_at: "2026-10-31T00:01:00Z",
      has_pdf: false, has_annotated_pdf: false, claims: [], ai_detections: [], citations: [],
      score_breakdown: {base: 100, final: null, confidence: 0, deductions: []},
    };
    const view = render(<FullWidthView data={data} readOnly />);
    expect(screen.getByText("Score unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(screen.getByText("Claims not assessed")).toBeInTheDocument();
    expect(screen.getByText(/AI: not assessed/)).toBeInTheDocument();
    view.rerender(<FullWidthView data={data} />);
    expect(screen.getByText("Score unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  });
});
