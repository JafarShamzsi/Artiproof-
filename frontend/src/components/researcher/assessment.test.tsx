import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResearcherScore, ResearcherCoverage } from "./assessment";
import type { CitationRingFlags } from "@/types/api";

describe("researcher evidence presentation", () => {
  it("distinguishes an unavailable score from a genuine zero", () => {
    const view = render(<ResearcherScore score={null} />);
    expect(screen.getByText("Score unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    view.rerender(<ResearcherScore score={0} />);
    expect(screen.getByRole("meter", { name: "Integrity score" })).toHaveAttribute("aria-valuenow", "0");
    expect(screen.queryByText("Score unavailable")).not.toBeInTheDocument();
  });

  it("shows failed lookup coverage without implying clearance", () => {
    render(<ResearcherCoverage findings={{
      rings: [], suspicious_pairs: [], flags: [], citation_evidence_status: "partial",
      coverage: { papers_attempted: 2, papers_succeeded: 1, unavailable_paper_ids: ["p2"] },
    }} />);
    expect(screen.getByText(/1 of 2 attempted publication lookups succeeded/)).toBeInTheDocument();
    expect(screen.getByText(/overall assessment is unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/1 citation lookup failed/)).toBeInTheDocument();
  });

  it("links incoming observations to both papers without claiming a ring", () => {
    const findings: CitationRingFlags = { rings: [], suspicious_pairs: [], flags: [],
      citation_concentration: [{ id: "author", name: "Author", citations_to_target: 3,
        relationships: [{ citing_paper_id: "citing-id", cited_paper_id: "target-id", author_ids: ["author"] }],
      }],
    };
    render(<ResearcherCoverage findings={findings} />);
    expect(screen.getByRole("link", { name: "Citing paper" })).toHaveAttribute("href", "https://www.semanticscholar.org/paper/citing-id");
    expect(screen.getByRole("link", { name: "Cited paper" })).toHaveAttribute("href", "https://www.semanticscholar.org/paper/target-id");
    expect(screen.getByText(/do not establish reciprocal citation rings/)).toBeInTheDocument();
  });

  it("makes legacy missing coverage explicit", () => {
    render(<ResearcherCoverage findings={null} />);
    expect(screen.getByText(/Citation coverage is not recorded/)).toBeInTheDocument();
  });
});
