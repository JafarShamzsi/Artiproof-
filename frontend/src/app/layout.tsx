import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import SessionProvider from "@/components/shared/SessionProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/contexts/ThemeContext";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "ArtiProof — Research Integrity Platform",
  description:
    "Verify sources, detect AI content, and expose citation manipulation in academic research. Protect the integrity of knowledge.",
  metadataBase: new URL("https://example.invalid"),
  openGraph: {
    title: "ArtiProof — Research Integrity Platform",
    description:
      "Five integrity engines in one workflow: plagiarism, AI detection, citation rings, integrity scoring, and fact-checking.",
    url: "https://example.invalid",
    siteName: "ArtiProof",
    // TODO: add /og-image.png (1200x630) and re-enable the `images` array
    // below. Shipping without `images` for now so social previews don't show
    // a broken image; the platform falls back to the page title + description.
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary",
    title: "ArtiProof — Research Integrity Platform",
    description:
      "Five integrity engines in one workflow: plagiarism, AI detection, citation rings, integrity scoring, fact-checking.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${jakarta.variable} min-h-screen bg-zinc-950 font-sans text-zinc-50 antialiased`}
      >
        {/* Skip-to-content — only visible when keyboard-focused.
            Targets #main-content rendered by each route's layout. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-emerald-500 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:shadow-lg"
        >
          Skip to main content
        </a>
        <SessionProvider>
          <ThemeProvider>
            <TooltipProvider>{children}</TooltipProvider>
          </ThemeProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
