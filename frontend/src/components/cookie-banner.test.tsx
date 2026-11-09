import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CookieBanner, getStoredConsent } from "./cookie-banner";

const KEY = "artiproof.cookie-consent";

describe("CookieBanner", () => {
  beforeEach(() => {
    window.localStorage.clear();
    // Remove any prior GPC stub so the banner actually mounts.
    delete (window.navigator as Navigator & { globalPrivacyControl?: boolean })
      .globalPrivacyControl;
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("shows the banner when no choice has been recorded", async () => {
    render(<CookieBanner />);
    expect(
      await screen.findByRole("dialog", { name: /cookies/i })
    ).toBeInTheDocument();
  });

  it("hides itself and persists the choice after Reject non-essential", async () => {
    const user = userEvent.setup();
    render(<CookieBanner />);

    await user.click(
      await screen.findByRole("button", { name: /reject non-essential/i })
    );

    expect(window.localStorage.getItem(KEY)).not.toBeNull();
    const stored = getStoredConsent();
    expect(stored).toMatchObject({
      essential: true,
      analytics: false,
      marketing: false,
    });
    expect(screen.queryByRole("dialog", { name: /cookies/i })).toBeNull();
  });

  it("flips analytics + marketing on after Accept all", async () => {
    const user = userEvent.setup();
    render(<CookieBanner />);

    await user.click(
      await screen.findByRole("button", { name: /accept all/i })
    );

    const stored = getStoredConsent();
    expect(stored.analytics).toBe(true);
    expect(stored.marketing).toBe(true);
  });

  it("keeps essentials pinned and saves only explicitly selected preferences", async () => {
    const user = userEvent.setup();
    render(<CookieBanner />);

    await user.click(await screen.findByRole("button", { name: "Customise" }));
    expect(screen.getByRole("checkbox", { name: /^Essential/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /^Essential/ })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /^Analytics/ })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: /^Marketing/ })).not.toBeChecked();
    await user.click(screen.getByRole("checkbox", { name: /^Analytics/ }));
    await user.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(getStoredConsent()).toEqual({ essential: true, analytics: true, marketing: false });
    expect(screen.queryByRole("dialog", { name: /cookies/i })).toBeNull();
  });

  it("saving unchanged preferences denies optional cookies and stays dismissed on remount", async () => {
    const user = userEvent.setup();
    const first = render(<CookieBanner />);
    await user.click(await screen.findByRole("button", { name: "Customise" }));
    await user.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(getStoredConsent()).toEqual({ essential: true, analytics: false, marketing: false });
    first.unmount();
    render(<CookieBanner />);
    expect(screen.queryByRole("dialog", { name: /cookies/i })).toBeNull();
  });

  it("honours Global Privacy Control: no banner, auto-deny", () => {
    Object.defineProperty(window.navigator, "globalPrivacyControl", {
      value: true,
      configurable: true,
    });

    render(<CookieBanner />);

    expect(screen.queryByRole("dialog", { name: /cookies/i })).toBeNull();
    expect(getStoredConsent()).toMatchObject({
      essential: true,
      analytics: false,
      marketing: false,
    });
  });
});
