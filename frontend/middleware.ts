// Middleware is only active in non-static builds (dev/production server)
// Static export (GitHub Pages) doesn't support middleware
export { default } from "next-auth/middleware";

// `/check/shared/:token` is the public read-only view for source checks and
// must be reachable without authentication, so the `/check` matcher uses a
// negative lookahead to skip anything under `/check/shared/`.
export const config = {
  matcher: [
    "/dashboard/:path*",
    "/check",
    "/check/((?!shared/).*)",
    "/researcher/:path*",
    "/reports/:path*",
    "/settings/:path*",
  ],
};
