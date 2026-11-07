"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { Shield, Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from "@/components/ui/sheet";

// Anchors are prefixed with `/` so they resolve correctly even when the navbar
// renders on /privacy or /terms — bare `#features` would just look for that
// anchor on the current route, which doesn't exist there.
const navLinks = [
  { label: "Features", href: "/#features" },
  { label: "How It Works", href: "/#how-it-works" },
  { label: "Demo", href: "/#scanner" },
  { label: "Pricing", href: "/#pricing" },
] as const;

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    function handleScroll() {
      setScrolled(window.scrollY > 50);
    }

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <motion.header
      initial={prefersReducedMotion ? false : { y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={cn(
        "fixed top-0 left-0 right-0 z-50 h-14 md:h-16 transition-all duration-300",
        scrolled
          ? "backdrop-blur-xl bg-zinc-950/80 border-b border-white/[0.06]"
          : "bg-transparent border-b border-transparent"
      )}
    >
      <nav className="mx-auto flex h-full max-w-7xl items-center justify-between px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <Shield className="size-5 text-emerald-400" />
          <span className="text-lg font-bold text-white">ArtiProof</span>
        </Link>

        {/* Desktop Navigation */}
        <ul className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="px-3 py-2 text-sm text-zinc-400 transition-colors duration-200 hover:text-white rounded-md"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        {/* Desktop Auth Buttons */}
        <div className="hidden md:flex items-center gap-3">
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium text-zinc-400 transition-colors hover:text-white hover:bg-zinc-800"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="inline-flex h-9 items-center rounded-lg bg-emerald-500 px-4 text-sm font-medium text-white shadow-sm shadow-emerald-500/20 transition-all hover:bg-emerald-600 active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
          >
            Get Started Free
          </Link>
        </div>

        {/* Mobile Menu */}
        <div className="md:hidden">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger className="inline-flex h-9 w-9 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white">
              <Menu className="size-5" />
              <span className="sr-only">Open menu</span>
            </SheetTrigger>
            <SheetContent
              side="right"
              className="w-full max-w-xs bg-zinc-950 border-zinc-800"
            >
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2 text-white">
                  <Shield className="size-5 text-emerald-400" />
                  ArtiProof
                </SheetTitle>
              </SheetHeader>

              <div className="flex flex-col gap-1 px-4 mt-4">
                {navLinks.map((link) => (
                  <SheetClose
                    key={link.href}
                    render={<a href={link.href} />}
                    className="flex w-full rounded-md px-3 py-2.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
                  >
                    {link.label}
                  </SheetClose>
                ))}
              </div>

              <div className="flex flex-col gap-3 px-4 mt-8">
                <SheetClose
                  render={<Link href="/login" />}
                  className="inline-flex items-center justify-center rounded-lg border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500 hover:text-white"
                >
                  Sign In
                </SheetClose>
                <SheetClose
                  render={<Link href="/register" />}
                  className="inline-flex items-center justify-center rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-emerald-600 hover:shadow-lg hover:shadow-emerald-500/20"
                >
                  Get Started
                </SheetClose>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </nav>
    </motion.header>
  );
}
