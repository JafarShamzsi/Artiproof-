export default function LandingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Passthrough. Native CSS `scroll-behavior: smooth` is set on <html>
  // in globals.css and respects prefers-reduced-motion. Lenis-based
  // inertial scroll was removed as the wine-paper voice doesn't want
  // ride-along physics.
  return <>{children}</>;
}
