import type { ReactNode } from "react";

/**
 * Onboarding tour system.
 *
 * A tour is an ordered list of steps. Each step optionally targets a
 * DOM node via a CSS selector — when present, the overlay highlights it
 * with an animated spotlight; when absent, the tooltip renders centered
 * as a modal welcome / end card.
 *
 * Completion is tracked per (tourId, version) in localStorage. Bumping
 * `version` is the "what's new" pattern: ship a new feature with a tour
 * version bump and every returning user sees it once.
 *
 * Targets use the `data-tour="<key>"` attribute so refactors that
 * rename CSS classes don't silently break the tour. Marking a node
 * `data-tour="foo"` is the contract.
 */

export type TourPlacement =
  | "top"
  | "bottom"
  | "left"
  | "right"
  | "auto"
  | "center";

export interface TourStep {
  /** Stable id for the step (used as React key and for analytics). */
  id: string;
  /**
   * CSS selector for the element to highlight. When omitted the tooltip
   * renders centered with no spotlight — use this for welcome / wrap-up
   * cards.
   */
  target?: string;
  title: string;
  body: ReactNode;
  /**
   * Where to place the tooltip relative to the target. `auto` flips
   * across edges if the preferred side would clip; `center` ignores the
   * target rect and centers the card.
   */
  placement?: TourPlacement;
  /**
   * Route pattern (RegExp source) the user must be on for this step to
   * make sense. Steps whose `routeMatch` doesn't match the current
   * pathname are skipped silently rather than highlighting nothing.
   */
  routeMatch?: string;
  /**
   * If the target isn't mounted on entry (e.g. inside a closed menu),
   * the overlay polls up to this many milliseconds before giving up and
   * advancing to the next step. Default 1500ms.
   */
  waitForTargetMs?: number;
}

export interface TourDefinition {
  /** Stable id — keyed in localStorage. Don't rename without migrating. */
  id: string;
  /**
   * Bump when the tour content changes meaningfully and you want every
   * returning user to see it again ("what's new" pattern). The
   * (id, version) pair is the storage key.
   */
  version: number;
  /** Human-readable label, shown in the Settings "Replay tour" picker. */
  label: string;
  steps: TourStep[];
}

/** Dashboard welcome — auto-starts on first sign-in. */
export const DASHBOARD_WELCOME_TOUR: TourDefinition = {
  id: "dashboard-welcome",
  version: 1,
  label: "Dashboard tour",
  steps: [
    {
      id: "welcome",
      placement: "center",
      title: "Welcome to ArtiProof",
      body: "A two-minute tour of the integrity workspace. You can skip with Esc and replay this anytime from Settings.",
    },
    {
      id: "sidebar",
      target: '[data-tour="sidebar"]',
      placement: "right",
      title: "Your workspaces",
      body: "Each section here is one job: scan a source, profile a researcher, watch what matters, or compose a report.",
    },
    {
      id: "nav-check",
      target: '[data-tour="nav-check"]',
      placement: "right",
      title: "Check a source",
      body: "Drop in text, a URL, or a PDF — we run five integrity engines and surface what's plagiarised, fabricated, or AI-generated.",
    },
    {
      id: "nav-researcher",
      target: '[data-tour="nav-researcher"]',
      placement: "right",
      title: "Analyze a researcher",
      body: "Build a publication-history risk profile from a single ORCID, name, or affiliation.",
    },
    {
      id: "nav-watchlist",
      target: '[data-tour="nav-watchlist"]',
      placement: "right",
      title: "Stay on top of things",
      body: "Pin researchers and source-checks here so the next time something changes, you see it first.",
    },
    {
      id: "nav-reports",
      target: '[data-tour="nav-reports"]',
      placement: "right",
      title: "Compose & export reports",
      body: "Turn analysis runs into branded PDFs or schedule recurring reports for committees and stakeholders.",
    },
    {
      id: "cmd-palette",
      target: '[data-tour="cmd-palette"]',
      placement: "bottom",
      title: "Jump anywhere — ⌘K / Ctrl+K",
      body: "The command palette is the fastest way to navigate, search past analyses, or trigger common actions.",
    },
    {
      id: "account-menu",
      target: '[data-tour="account-menu"]',
      placement: "bottom",
      title: "Account & settings",
      body: "Open Settings to tune theme, locale, billing, team, analysis preferences — and to replay this tour.",
    },
    {
      id: "done",
      placement: "center",
      title: "You're set",
      body: "We'll add a small badge whenever a new feature ships — open the new tour from Settings → Appearance to catch up in seconds.",
    },
  ],
};

/** All known tours, keyed by id. Add new tours here. */
export const TOURS: Record<string, TourDefinition> = {
  [DASHBOARD_WELCOME_TOUR.id]: DASHBOARD_WELCOME_TOUR,
};
