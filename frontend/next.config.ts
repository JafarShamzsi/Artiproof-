import type { NextConfig } from "next";

const isStaticExport = process.env.GITHUB_PAGES === "true";
// Promote CSP from Report-Only to enforced by setting CSP_ENFORCE=true at
// build time. Next 16 + Tailwind 4 + the inline no-FOUC theme script still
// need 'unsafe-inline'/'unsafe-eval' in dev, so we keep them — toggle just
// flips which header name browsers obey.
const cspEnforce = process.env.CSP_ENFORCE === "true";

// connect-src is broad because we hit the backend, Vercel, and Google Generative AI endpoints.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https:",
  "font-src 'self' data:",
  "connect-src 'self' https: wss:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-DNS-Prefetch-Control", value: "on" },
  // Conservative Permissions-Policy — ArtiProof doesn't need any of these
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  {
    key: cspEnforce
      ? "Content-Security-Policy"
      : "Content-Security-Policy-Report-Only",
    value: csp,
  },
];

const nextConfig: NextConfig = isStaticExport
  ? {
      // Static export for GitHub Pages — image optimization is unavailable
      // and headers() are skipped because there's no Next runtime.
      output: "export",
      basePath: "/CivicGuards",
      assetPrefix: "/CivicGuards/",
      images: { unoptimized: true },
    }
  : {
      // Normal Vercel/Node deploys keep image optimization enabled
      async headers() {
        return [
          {
            source: "/:path*",
            headers: securityHeaders,
          },
        ];
      },
    };

export default nextConfig;
