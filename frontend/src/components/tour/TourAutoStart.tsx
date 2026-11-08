"use client";

import { useEffect } from "react";
import { useTour } from "@/contexts/TourContext";

/**
 * Mounted by the dashboard layout. On first visit (for the current
 * tour version) it starts the named tour after a short delay so the
 * page has time to render its target elements. If the user already
 * completed it, this is a no-op.
 */
export function TourAutoStart({
  tourId,
  delayMs = 500,
}: {
  tourId: string;
  delayMs?: number;
}) {
  const { startTour } = useTour();

  useEffect(() => {
    // Give the dashboard's first paint a beat — sidebar links and the
    // command palette button need to be in the DOM before the tour
    // starts to query them.
    const t = setTimeout(() => {
      startTour(tourId);
    }, delayMs);
    return () => clearTimeout(t);
  }, [tourId, delayMs, startTour]);

  return null;
}
