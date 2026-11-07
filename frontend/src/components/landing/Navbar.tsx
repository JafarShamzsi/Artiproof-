"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  motion,
  useReducedMotion,
  useMotionValueEvent,
  useScroll,
  AnimatePresence,
} from "framer-motion";
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
  { label: "How it works", href: "/#how-it-works", id: "how-it-works" },
  { label: "Features", href: "/#features", id: "features" },
  { label: "Pricing", href: "/#pricing", id: "pricing" },
] as const;

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const prefersReducedMotion = useReducedMotion();
  const lastY = useRef(0);

  const { scrollY } = useScroll();

  // Hide on scroll-down past the hero, show on scroll-up. Doesn't fire
  // until past 100px so the user doesn't lose the navbar instantly on
  // a single twitch.
  useMotionValueEvent(scrollY, "change", (current) => {
    setScrolled(current > 50);
    if (prefersReducedMotion) return;
    const delta = current - lastY.current;
    if (current < 100) {
      setHidden(false);
    } else if (delta > 6) {
      setHidden(true);
    } else if (delta < -6) {
      setHidden(false);
    }
    lastY.current = current;
  });

  // Active section indicator — IntersectionObserver on the section ids.
  useEffect(() => {
    const sections = navLinks
      .map((l) => document.getElementById(l.id))
      .filter((el): el is HTMLElement => el !== null);
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // Pick the entry closest to the top of the viewport that is
        // intersecting, so the active link tracks the section the user
        // is reading rather than whichever one entered last.
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort(
            (a, b) =>
              a.boundingClientRect.top - b.boundingClientRect.top,
          );
        if (visible[0]) {
          setActiveId(visible[0].target.id);
        }
      },
      {
        rootMargin: "-30% 0px -60% 0px",
        threshold: 0,
      },
    );

    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, []);

  return (
    <motion.header
      // Invariant `initial` so SSR markup matches first client render.
      // `useReducedMotion()` returns null during SSR and the real value
      // on the client, so branching `initial` on it causes hydration
      // mismatch. Instead we keep the entry transform and zero out the
      // duration when motion is reduced — instantaneous snap, no flash.
      initial={{ y: -20, opacity: 0 }}
      animate={{
        y: hidden ? "-100%" : 0,
        opacity: 1,
      }}
      transition={{
        duration: prefersReducedMotion ? 0 : 0.3,
        ease: [0.16, 1, 0.3, 1],
      }}
      className={cn(
        "fixed top-0 left-0 right-0 z-50 h-14 md:h-16 transition-[background-color,border-color] duration-300",
        scrolled
          ? "backdrop-blur-xl bg-zinc-950/80 border-b border-white/[0.06]"
          : "bg-transparent border-b border-transparent",
      )}
    >
      <nav className="mx-auto flex h-full max-w-7xl items-center justify-between px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <Shield className="size-5 text-emerald-400" />
          <span className="text-lg font-bold text-white">ArtiProof</span>
        </Link>

        {/* Desktop nav with active-section indicator */}
        <ul className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => {
            const isActive = activeId === link.id;
            return (
              <li key={link.href} className="relative">
                <a
                  href={link.href}
                  className={cn(
                    "relative inline-flex items-center rounded-md px-3 py-2 text-sm transition-colors duration-200",
                    isActive ? "text-white" : "text-zinc-400 hover:text-white",
                  )}
                >
                  {link.label}
                </a>
                <AnimatePresence>
                  {isActive && (
                    <motion.span
                      layoutId="nav-active-indicator"
                      aria-hidden="true"
                      className="absolute -bottom-0.5 left-3 right-3 h-px bg-emerald-400"
                      transition={{
                        type: "spring",
                        stiffness: 380,
                        damping: 32,
                      }}
                    />
                  )}
                </AnimatePresence>
              </li>
            );
          })}
        </ul>

        {/* Desktop auth buttons */}
        <div className="hidden md:flex items-center gap-3">
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium text-zinc-400 transition-colors hover:text-white hover:bg-zinc-800"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="inline-flex h-9 items-center rounded-lg bg-emerald-500 px-4 text-sm font-medium text-white shadow-sm shadow-emerald-500/20 transition-all hover:bg-emerald-600 hover:shadow-emerald-500/30 active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
          >
            Get started free
          </Link>
        </div>

        {/* Mobile menu */}
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

              <motion.div
                className="flex flex-col gap-1 px-4 mt-4"
                initial="hidden"
                animate="visible"
                variants={{
                  hidden: {},
                  visible: {
                    transition: { staggerChildren: 0.04 },
                  },
                }}
              >
                {navLinks.map((link) => (
                  <motion.div
                    key={link.href}
                    variants={{
                      hidden: { opacity: 0, x: 8 },
                      visible: { opacity: 1, x: 0 },
                    }}
                    transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <SheetClose
                      render={<a href={link.href} />}
                      className="flex w-full rounded-md px-3 py-2.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
                    >
                      {link.label}
                    </SheetClose>
                  </motion.div>
                ))}
              </motion.div>

              <div className="flex flex-col gap-3 px-4 mt-8">
                <SheetClose
                  render={<Link href="/login" />}
                  className="inline-flex items-center justify-center rounded-lg border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500 hover:text-white"
                >
                  Sign in
                </SheetClose>
                <SheetClose
                  render={<Link href="/register" />}
                  className="inline-flex items-center justify-center rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-emerald-600 hover:shadow-lg hover:shadow-emerald-500/20"
                >
                  Get started
                </SheetClose>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </nav>
    </motion.header>
  );
}
