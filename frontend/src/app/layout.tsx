import type { Metadata } from "next";
import { Inter, Fraunces, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import SessionProvider from "@/components/shared/SessionProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { ColorModeProvider } from "@/contexts/ColorModeContext";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  style: ["normal"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "ArtiProof — Research integrity, automated",
  description:
    "Five integrity engines in one workflow: plagiarism, AI detection, citation rings, fact-checking, and researcher integrity scoring. Built for universities across Azerbaijan and the Eastern Partnership.",
  metadataBase: new URL("https://example.invalid"),
  openGraph: {
    title: "ArtiProof — Research integrity, automated",
    description:
      "Plagiarism, AI detection, citation rings, fact-checking, researcher scoring — one platform.",
    url: "https://example.invalid",
    siteName: "ArtiProof",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary",
    title: "ArtiProof — Research integrity, automated",
    description:
      "Five integrity engines in one workflow.",
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
        className={`${inter.variable} ${fraunces.variable} ${jetbrains.variable} min-h-[100dvh] bg-surface-base font-sans text-fg-primary antialiased`}
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
      </body>
    </html>
  );
}
