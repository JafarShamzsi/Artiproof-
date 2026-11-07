// Middleware is only active in non-static builds (dev/production server)
// Static export (GitHub Pages) doesn't support middleware
export { default } from "next-auth/middleware";

export const config = {
  matcher: ["/dashboard/:path*", "/check/:path*", "/researcher/:path*", "/reports/:path*", "/settings/:path*"],
};
