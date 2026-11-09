import { render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import TeamPage from "./page";

const workspaceState = vi.hoisted(() => ({ suspended: false }));

vi.mock("./TeamWorkspace", () => ({
  TeamWorkspace: () => {
    if (workspaceState.suspended) throw new Promise(() => {});
    return <div>Team workspace ready</div>;
  },
}));

describe("TeamPage", () => {
  it("renders a loading fallback when URL query state suspends during prerender", () => {
    workspaceState.suspended = true;
    try {
      expect(renderToString(<TeamPage />)).toContain("Loading team");
    } finally {
      workspaceState.suspended = false;
    }
  });

  it("renders the workspace when URL query state is available", () => {
    render(<TeamPage />);
    expect(screen.getByText("Team workspace ready")).toBeInTheDocument();
  });
});
