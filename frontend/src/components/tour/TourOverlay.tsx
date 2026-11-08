"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Check, X } from "lucide-react";
import { useTour } from "@/contexts/TourContext";
import type { TourPlacement, TourStep } from "@/lib/tours";

/**
 * Animated overlay for the active tour.
 *
 * Spotlight: a viewport-filling SVG mask with a rounded-rect cutout
 * over the target element. The cutout animates between steps using
 * framer-motion so the user's eye is dragged from one focus point to
 * the next.
 *
 * Tooltip: a card with title / body / step counter and navigation
 * buttons. Positioned relative to the target with `auto`-flip when the
 * preferred side would clip the viewport.
 *
 * Keyboard:
 *   - Esc:         skip the tour
 *   - Enter / →:   next step
 *   - ←:           previous step
 *
 * The overlay is rendered into a portal at <body> so it stacks above
 * any local stacking context (e.g. dropdowns, dialogs).
 */

const SPOTLIGHT_PAD = 8;       // px around the target before the cutout
const SPOTLIGHT_RADIUS = 10;   // rounded-rect corner radius
const TOOLTIP_GAP = 14;        // px between target and tooltip
const TOOLTIP_MAX_WIDTH = 360; // px
const VIEWPORT_PAD = 16;       // px breathing room from window edges

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Resolve the target node (with brief polling — some targets mount
 * lazily, e.g. inside a Sheet) and compute its viewport rect.
 */
function useTargetRect(
  step: TourStep | null,
  pathname: string,
): { rect: Rect | null; ready: boolean } {
  const [state, setState] = useState<{ rect: Rect | null; ready: boolean }>({
    rect: null,
    ready: false,
  });

  useLayoutEffect(() => {
    if (!step) {
      // Synchronizing the resolved-rect cache with the externally-
      // owned `step` prop. The lint rule discourages setState-in-effect
      // because it can cascade renders, but here it's a deliberate
      // re-init when the parent advances a step and we must measure a
      // new DOM target — there is no external store to subscribe to.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState({ rect: null, ready: false });
      return;
    }

    // Center / welcome steps don't need a target rect.
    if (!step.target) {
      setState({ rect: null, ready: true });
      return;
    }

    let cancelled = false;
    const deadline = performance.now() + (step.waitForTargetMs ?? 1500);

    function measure() {
      if (cancelled || !step?.target) return;
      const node = document.querySelector(step.target) as HTMLElement | null;
      if (node) {
        const box = node.getBoundingClientRect();
        setState({
          rect: { x: box.x, y: box.y, width: box.width, height: box.height },
          ready: true,
        });
        return;
      }
      if (performance.now() >= deadline) {
        // Target never showed — mark ready with no rect so the overlay
        // gracefully degrades to a centered tooltip.
        setState({ rect: null, ready: true });
        return;
      }
      requestAnimationFrame(measure);
    }

    measure();

    // Keep the rect in sync with layout shifts (sidebar collapse,
    // window resize, font-loading reflow). We re-measure on a
    // throttled rAF rather than wiring per-node ResizeObserver because
    // the target may change identity between steps.
    let raf = 0;
    function onLayoutChange() {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(measure);
    }
    window.addEventListener("resize", onLayoutChange);
    window.addEventListener("scroll", onLayoutChange, true);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onLayoutChange);
      window.removeEventListener("scroll", onLayoutChange, true);
    };
  }, [step, pathname]);

  return state;
}

interface TooltipPosition {
  top: number;
  left: number;
  placement: Exclude<TourPlacement, "auto">;
  arrow: { top: number; left: number } | null;
}

/**
 * Decide where to place the tooltip given the target rect, the
 * requested placement, and the viewport size. Returns viewport-relative
 * top/left for the tooltip's top-left corner, plus an arrow position.
 */
function placeTooltip(
  rect: Rect | null,
  requested: TourPlacement,
  tooltipSize: { width: number; height: number },
  viewport: { width: number; height: number },
): TooltipPosition {
  const w = tooltipSize.width;
  const h = tooltipSize.height;

  // No target rect — center on screen.
  if (!rect || requested === "center") {
    return {
      top: Math.max(VIEWPORT_PAD, viewport.height / 2 - h / 2),
      left: Math.max(VIEWPORT_PAD, viewport.width / 2 - w / 2),
      placement: "bottom",
      arrow: null,
    };
  }

  const fits = (p: Exclude<TourPlacement, "auto" | "center">) => {
    switch (p) {
      case "top":
        return rect.y - TOOLTIP_GAP - h >= VIEWPORT_PAD;
      case "bottom":
        return rect.y + rect.height + TOOLTIP_GAP + h <= viewport.height - VIEWPORT_PAD;
      case "left":
        return rect.x - TOOLTIP_GAP - w >= VIEWPORT_PAD;
      case "right":
        return rect.x + rect.width + TOOLTIP_GAP + w <= viewport.width - VIEWPORT_PAD;
    }
  };

  // Resolve "auto" to the first side that fits, in a sensible order.
  // "center" was already short-circuited above so requested is now one
  // of "auto" | "top" | "bottom" | "left" | "right".
  let chosen: Exclude<TourPlacement, "auto" | "center">;
  if (requested === "auto") {
    chosen = (["bottom", "top", "right", "left"] as const).find(fits) ?? "bottom";
  } else {
    chosen = fits(requested)
      ? requested
      : (["bottom", "top", "right", "left"] as const).find(fits) ?? requested;
  }

  let top = 0;
  let left = 0;
  let arrowTop: number | null = null;
  let arrowLeft: number | null = null;

  switch (chosen) {
    case "top":
      top = rect.y - TOOLTIP_GAP - h;
      left = rect.x + rect.width / 2 - w / 2;
      arrowTop = h;
      arrowLeft = w / 2;
      break;
    case "bottom":
      top = rect.y + rect.height + TOOLTIP_GAP;
      left = rect.x + rect.width / 2 - w / 2;
      arrowTop = -6;
      arrowLeft = w / 2;
      break;
    case "left":
      left = rect.x - TOOLTIP_GAP - w;
      top = rect.y + rect.height / 2 - h / 2;
      arrowTop = h / 2;
      arrowLeft = w;
      break;
    case "right":
      left = rect.x + rect.width + TOOLTIP_GAP;
      top = rect.y + rect.height / 2 - h / 2;
      arrowTop = h / 2;
      arrowLeft = -6;
      break;
  }

  // Clamp into the viewport so the card never paints offscreen.
  left = Math.max(VIEWPORT_PAD, Math.min(left, viewport.width - w - VIEWPORT_PAD));
  top = Math.max(VIEWPORT_PAD, Math.min(top, viewport.height - h - VIEWPORT_PAD));

  return {
    top,
    left,
    placement: chosen,
    arrow:
      arrowTop != null && arrowLeft != null
        ? { top: arrowTop, left: arrowLeft }
        : null,
  };
}

function useViewportSize() {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    function update() {
      setSize({ width: window.innerWidth, height: window.innerHeight });
    }
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return size;
}

export function TourOverlay() {
  const {
    activeTour,
    currentStep,
    stepIndex,
    totalSteps,
    isFirstStep,
    isLastStep,
    nextStep,
    prevStep,
    skipTour,
    endTour,
  } = useTour();

  const pathname = usePathname() ?? "/";

  // Step-by-step route-match skip: if the step has a `routeMatch` and
  // the current pathname doesn't satisfy it, jump forward. This lets
  // tours include cross-page steps without breaking on the wrong page.
  useEffect(() => {
    if (!currentStep?.routeMatch) return;
    try {
      const re = new RegExp(currentStep.routeMatch);
      if (!re.test(pathname)) {
        // Skip silently. Using a microtask so we don't loop synchronously.
        queueMicrotask(nextStep);
      }
    } catch {
      // Malformed pattern — leave the step alone.
    }
  }, [currentStep, pathname, nextStep]);

  const { rect, ready } = useTargetRect(currentStep, pathname);
  const viewport = useViewportSize();

  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipSize, setTooltipSize] = useState({
    width: TOOLTIP_MAX_WIDTH,
    height: 180,
  });

  // Measure tooltip dimensions whenever step or viewport changes so
  // placement math uses the real rendered box, not the placeholder.
  useLayoutEffect(() => {
    if (!tooltipRef.current) return;
    const el = tooltipRef.current;
    const box = el.getBoundingClientRect();
    setTooltipSize({ width: box.width, height: box.height });
  }, [currentStep, viewport.width, viewport.height]);

  const placement = useMemo<TooltipPosition>(
    () =>
      placeTooltip(
        rect,
        currentStep?.placement ?? "auto",
        tooltipSize,
        viewport,
      ),
    [rect, currentStep?.placement, tooltipSize, viewport],
  );

  // Global keyboard handling. We bind on document so the user doesn't
  // have to focus the tooltip first.
  useEffect(() => {
    if (!activeTour) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        skipTour();
        return;
      }
      if (e.key === "Enter" || e.key === "ArrowRight" || e.key === " ") {
        // Don't hijack space/enter while the user is typing.
        const tag = (e.target as HTMLElement | null)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA") return;
        e.preventDefault();
        nextStep();
        return;
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        prevStep();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeTour, nextStep, prevStep, skipTour]);

  // Lock body scroll while the overlay is open so the page doesn't
  // drift under the spotlight when the user reaches for arrow keys.
  useEffect(() => {
    if (!activeTour) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [activeTour]);

  // Auto-scroll the target into view if it's offscreen — common when
  // the page is long and the tour highlights something below the fold.
  useEffect(() => {
    if (!rect || !currentStep?.target) return;
    const offscreen =
      rect.y < 0 ||
      rect.y + rect.height > viewport.height ||
      rect.x < 0 ||
      rect.x + rect.width > viewport.width;
    if (!offscreen) return;
    const node = document.querySelector(
      currentStep.target,
    ) as HTMLElement | null;
    node?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [rect, currentStep?.target, viewport.height, viewport.width]);

  const handleNext = useCallback(() => {
    if (isLastStep) {
      endTour();
    } else {
      nextStep();
    }
  }, [isLastStep, endTour, nextStep]);

  // Wait until the document is available (SSR / first paint). The
  // setState-in-effect is the established read-once-on-mount pattern
  // for browser-only globals (same as CookieBanner / ColorModeContext);
  // there is no SSR-safe alternative for `document.body` reference.
  const [portalEl, setPortalEl] = useState<HTMLElement | null>(null);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPortalEl(document.body);
  }, []);

  if (!activeTour || !currentStep || !portalEl) return null;

  // Until the rect is resolved (still polling), render nothing so the
  // spotlight doesn't flash at (0,0).
  if (!ready) return null;

  const spotlightRect: Rect = rect ?? {
    x: viewport.width / 2,
    y: viewport.height / 2,
    width: 0,
    height: 0,
  };

  // Wrap the target with padding for a softer cutout.
  const cutout = rect
    ? {
        x: spotlightRect.x - SPOTLIGHT_PAD,
        y: spotlightRect.y - SPOTLIGHT_PAD,
        width: spotlightRect.width + SPOTLIGHT_PAD * 2,
        height: spotlightRect.height + SPOTLIGHT_PAD * 2,
      }
    : { x: viewport.width / 2, y: viewport.height / 2, width: 0, height: 0 };

  const overlay = (
    <div
      // The overlay is logically a dialog — single focused interruption,
      // dismissable, owns the screen. The tooltip card carries the
      // labelledby/describedby targets.
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-step-title"
      aria-describedby="tour-step-body"
      className="fixed inset-0 z-[200]"
      // Don't block clicks on the target — clicking the highlighted
      // element should still work so tours can guide the user through
      // real interactions. We re-enable pointer-events on the children
      // that need them (backdrop catcher + tooltip).
      style={{ pointerEvents: "none" }}
    >
      {/* Backdrop with animated spotlight cutout. */}
      <motion.svg
        key="tour-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
        width="100%"
        height="100%"
        className="absolute inset-0"
        style={{ pointerEvents: "auto" }}
        onClick={skipTour}
      >
        <defs>
          <mask id="tour-spotlight-mask">
            {/* White = visible overlay. Black = hole. */}
            <rect
              x="0"
              y="0"
              width={viewport.width || "100%"}
              height={viewport.height || "100%"}
              fill="white"
            />
            <motion.rect
              animate={{
                x: cutout.x,
                y: cutout.y,
                width: cutout.width,
                height: cutout.height,
              }}
              transition={{ type: "spring", stiffness: 280, damping: 32 }}
              rx={SPOTLIGHT_RADIUS}
              ry={SPOTLIGHT_RADIUS}
              fill="black"
            />
          </mask>
        </defs>
        <rect
          x="0"
          y="0"
          width={viewport.width || "100%"}
          height={viewport.height || "100%"}
          fill="rgba(8, 6, 12, 0.72)"
          mask="url(#tour-spotlight-mask)"
        />
      </motion.svg>

      {/* Soft animated halo around the spotlight — pure decoration, helps
          the eye lock on. Only rendered when there's a real target. */}
      {rect && (
        <motion.div
          aria-hidden="true"
          className="absolute rounded-[10px] ring-2 ring-brand/60"
          animate={{
            top: cutout.y,
            left: cutout.x,
            width: cutout.width,
            height: cutout.height,
            boxShadow:
              "0 0 0 4px rgba(180, 50, 70, 0.18), 0 0 40px rgba(180, 50, 70, 0.35)",
          }}
          transition={{ type: "spring", stiffness: 280, damping: 32 }}
        />
      )}

      {/* Tooltip card. */}
      <motion.div
        key={currentStep.id}
        ref={tooltipRef}
        initial={{ opacity: 0, y: 8, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -8, scale: 0.98 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="absolute max-w-[calc(100vw-32px)] rounded-2xl border border-border-default bg-surface-card p-5 shadow-2xl"
        style={{
          width: TOOLTIP_MAX_WIDTH,
          top: placement.top,
          left: placement.left,
          pointerEvents: "auto",
        }}
      >
        {/* Arrow pointing toward the target. */}
        {placement.arrow && (
          <span
            aria-hidden="true"
            className="absolute h-3 w-3 rotate-45 border border-border-default bg-surface-card"
            style={{
              top: placement.arrow.top,
              left: placement.arrow.left,
              transform: `translate(-50%, -50%) rotate(45deg)`,
              borderRight:
                placement.placement === "left" ? undefined : "transparent",
              borderBottom:
                placement.placement === "top" ? undefined : "transparent",
              borderLeft:
                placement.placement === "right" ? undefined : "transparent",
              borderTop:
                placement.placement === "bottom" ? undefined : "transparent",
            }}
          />
        )}

        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-medium uppercase tracking-wider text-fg-tertiary">
              {activeTour.label} · Step {stepIndex + 1} of {totalSteps}
            </p>
            <h2
              id="tour-step-title"
              className="mt-1 font-display text-lg font-semibold text-fg-primary"
            >
              {currentStep.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={skipTour}
            aria-label="Skip tour"
            className="shrink-0 rounded-md p-1 text-fg-secondary hover:bg-brand-soft hover:text-fg-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div
          id="tour-step-body"
          className="mt-3 text-sm leading-relaxed text-fg-secondary"
        >
          {currentStep.body}
        </div>

        {/* Progress dots — clickable so the user can jump back to a
            previous step they want to re-read. We don't let users jump
            forward; the tour is sequential by design. */}
        <div
          role="progressbar"
          aria-valuenow={stepIndex + 1}
          aria-valuemin={1}
          aria-valuemax={totalSteps}
          aria-label={`Step ${stepIndex + 1} of ${totalSteps}`}
          className="mt-4 flex items-center gap-1.5"
        >
          {Array.from({ length: totalSteps }).map((_, i) => (
            <span
              key={i}
              aria-hidden="true"
              className={
                i === stepIndex
                  ? "h-1.5 w-6 rounded-full bg-brand transition-all"
                  : i < stepIndex
                    ? "h-1.5 w-1.5 rounded-full bg-brand/60 transition-all"
                    : "h-1.5 w-1.5 rounded-full bg-border-default transition-all"
              }
            />
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={skipTour}
            className="text-xs text-fg-tertiary underline-offset-2 hover:text-fg-secondary hover:underline"
          >
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={prevStep}
              disabled={isFirstStep}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border-default px-3 text-xs font-medium text-fg-primary hover:bg-brand-soft disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back
            </button>
            <button
              type="button"
              onClick={handleNext}
              autoFocus
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-3 text-xs font-medium text-white shadow-sm shadow-brand/30 hover:bg-brand-hover"
            >
              {isLastStep ? (
                <>
                  <Check className="h-3.5 w-3.5" />
                  Done
                </>
              ) : (
                <>
                  Next
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );

  return createPortal(
    <AnimatePresence mode="wait">{overlay}</AnimatePresence>,
    portalEl,
  );
}
