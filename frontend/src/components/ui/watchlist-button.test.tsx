import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { WatchlistButton } from "./watchlist-button";

describe("WatchlistButton", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({}), { status: 200 })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the icon-mode toggle with the correct aria-label when not watching", () => {
    render(
      <WatchlistButton researcherId="rid-1" initialWatching={false} mode="icon" />,
    );
    expect(
      screen.getByRole("button", { name: /add to watchlist/i }),
    ).toBeInTheDocument();
  });

  it("renders the icon-mode toggle with 'Remove' label when already watching", () => {
    render(
      <WatchlistButton researcherId="rid-1" initialWatching={true} mode="icon" />,
    );
    expect(
      screen.getByRole("button", { name: /remove from watchlist/i }),
    ).toBeInTheDocument();
  });

  it("does NOT navigate when clicked inside a parent <a>", async () => {
    const user = userEvent.setup();
    const navigateSpy = vi.fn();

    function Wrapper() {
      return (
        <a
          href="/researcher/rid-1"
          onClick={(e) => {
            // emulate jsdom-level "navigation" — record propagation
            navigateSpy();
            e.preventDefault();
          }}
        >
          <span>row content</span>
          <WatchlistButton researcherId="rid-1" initialWatching={false} mode="icon" />
        </a>
      );
    }
    render(<Wrapper />);

    await user.click(
      screen.getByRole("button", { name: /add to watchlist/i }),
    );

    // The button's onClick must stopPropagation so the parent anchor's
    // onClick (our navigateSpy) is NOT called.
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it("renders full-mode with text labels", () => {
    render(
      <WatchlistButton researcherId="rid-1" initialWatching={false} mode="full" />,
    );
    expect(screen.getByRole("button", { name: /watch/i })).toBeInTheDocument();
  });
});
