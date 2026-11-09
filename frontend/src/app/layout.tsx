import type { Metadata } from "next";
import localFont from "next/font/local";
import { Toaster } from "sonner";
import "./globals.css";
import SessionProvider from "@/components/shared/SessionProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { ColorModeProvider } from "@/contexts/ColorModeContext";
import { CookieBanner } from "@/components/cookie-banner";

const inter = localFont({
  src: [{ path: "./fonts/Inter.ttf", weight: "100 900", style: "normal" }],
  variable: "--font-sans",
  display: "swap",
});

const fraunces = localFont({
  src: [
    { path: "./fonts/Fraunces.ttf", weight: "400 800", style: "normal" },
    { path: "./fonts/Fraunces-Italic.ttf", weight: "400 800", style: "italic" },
  ],
  variable: "--font-display",
  display: "swap",
  adjustFontFallback: "Times New Roman",
});

/** Newsreader (italic) is the editorial / marginalia voice — softer, more
 *  literary than Fraunces, used for figure captions, footnotes, marginal
 *  annotations, and pull-quotes. The pairing reads as "research paper". */
const newsreader = localFont({
  src: [{ path: "./fonts/Newsreader-Italic.ttf", weight: "400 500", style: "italic" }],
  variable: "--font-editorial",
  display: "swap",
  adjustFontFallback: "Times New Roman",
});

const jetbrains = localFont({
  src: [{ path: "./fonts/JetBrainsMono.ttf", weight: "400 500", style: "normal" }],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ArtiProof — Research integrity, automated",
  description:
    "Review source claims, citation links and AI style estimates. Explore researcher publication metrics in a separate lookup, with findings and coverage for human review.",
  metadataBase: new URL("https://artiproof.com"),
  openGraph: {
    title: "ArtiProof — Research integrity, automated",
    description:
      "Source claim review, citation checks and separate researcher lookups, with coverage and limitations alongside the findings.",
    url: "https://artiproof.com",
    siteName: "ArtiProof",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary",
    title: "ArtiProof — Research integrity, automated",
    description:
      "Source checks and researcher analysis to support human review.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
};

/** Pre-hydration script — runs synchronously before React paints so the
 *  user never sees a flash of the wrong theme. Reads the stored
 *  preference and applies the dark class + color-scheme. Kept tiny on
 *  purpose so it never blocks paint.
 */
const NO_FOUC_SCRIPT = `(()=>{try{var m=localStorage.getItem('artiproof-theme')||'system';var d=m==='dark'||(m==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);document.documentElement.style.colorScheme=d?'dark':'light';}catch(_){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FOUC_SCRIPT }} />
      </head>
      <body
        className={`${inter.variable} ${fraunces.variable} ${newsreader.variable} ${jetbrains.variable} min-h-[100dvh] bg-surface-base font-sans text-fg-primary antialiased`}
      >
        {/* Skip-to-content — only visible when keyboard-focused.
            Targets #main-content rendered by each route's layout. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-brand focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:shadow-lg"
        >
          Skip to main content
        </a>
        <SessionProvider>
          <ColorModeProvider>
            <ThemeProvider>
              <TooltipProvider>{children}</TooltipProvider>
            </ThemeProvider>
          </ColorModeProvider>
        </SessionProvider>
        {/* Toast notifications — sonner. richColors uses brand-tinted
            success / error / info palettes. Position top-right so toasts
            don't fight with the bottom keyboard-shortcuts panel. */}
        <Toaster
          richColors
          position="top-right"
          toastOptions={{
            className: "font-sans",
          }}
        />
        {/* Cookie consent — defaults to essential-only, opt-in for
            analytics/marketing. Honours Global Privacy Control. The
            banner is hidden after the user makes a choice (or if GPC
            is on). Persistence in localStorage with a 12-month TTL. */}
        <CookieBanner />
      </body>
    </html>
  );
}
