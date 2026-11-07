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
import { Menu } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const navLinks = [
  { label: "How it works", href: "/#how-it-works", id: "how-it-works" },
  { label: "Features", href: "/#features", id: "features" },
  { label: "Compare", href: "/#compare", id: "compare" },
  { label: "Pricing", href: "/#pricing", id: "pricing" },
] as const;

/** Brand wordmark — small wine-filled circle with a serif `A` cut into it.
 *  Pure SVG so it scales and themes via currentColor where useful. */
function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand text-[13px] font-bold leading-none text-white",
        "font-display",
        className,
      )}
    >
      A
    </span>
  );
}

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const reduce = useReducedMotion();
  const lastY = useRef(0);

  const { scrollY } = useScroll();

  useMotionValueEvent(scrollY, "change", (current) => {
    setScrolled(current > 32);
    if (reduce) return;
    const delta = current - lastY.current;
    if (current < 100) setHidden(false);
    else if (delta > 6) setHidden(true);
    else if (delta < -6) setHidden(false);
    lastY.current = current;
  });

  useEffect(() => {
    const sections = navLinks
      .map((l) => document.getElementById(l.id))
      .filter((el): el is HTMLElement => el !== null);
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveId(visible[0].target.id);
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: 0 },
    );

    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, []);

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: hidden ? "-100%" : 0, opacity: 1 }}
      transition={{ duration: reduce ? 0 : 0.3, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "fixed top-0 left-0 right-0 z-50 h-14 md:h-16 transition-[background-color,border-color,backdrop-filter] duration-300",
        scrolled
          ? "border-b border-border-subtle bg-surface-base/80 backdrop-blur-xl"
          : "border-b border-transparent bg-transparent",
      )}
    >
      <nav className="mx-auto flex h-full max-w-7xl items-center justify-between px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5">
          <BrandMark />
          <span className="font-display text-lg font-semibold tracking-tight text-fg-primary">
            ArtiProof
          </span>
        </Link>

        <ul className="hidden items-center gap-1 md:flex">
          {navLinks.map((link) => {
            const isActive = activeId === link.id;
            return (
              <li key={link.href} className="relative">
                <a
                  href={link.href}
                  className={cn(
                    "inline-flex items-center rounded-md px-3 py-2 text-sm transition-colors duration-200",
                    isActive
                      ? "text-fg-primary"
                      : "text-fg-secondary hover:text-fg-primary",
                  )}
                >
                  {link.label}
                </a>
                <AnimatePresence>
                  {isActive && (
                    <motion.span
                      layoutId="nav-active-indicator"
                      aria-hidden="true"
                      className="absolute -bottom-0.5 left-3 right-3 h-px bg-brand"
                      transition={{ type: "spring", stiffness: 380, damping: 32 }}
                    />
                  )}
                </AnimatePresence>
              </li>
            );
          })}
        </ul>

        <div className="hidden items-center gap-3 md:flex">
          <ThemeToggle />
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium text-fg-secondary transition-colors hover:bg-surface-card hover:text-fg-primary"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="inline-flex h-9 items-center rounded-lg bg-brand px-4 text-sm font-medium text-white shadow-sm shadow-[color:var(--brand)]/25 transition-all hover:bg-brand-hover active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
          >
            Get started
          </Link>
        </div>

        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle />
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-secondary transition-colors hover:bg-surface-card hover:text-fg-primary">
              <Menu className="size-5" strokeWidth={1.5} />
              <span className="sr-only">Open menu</span>
            </SheetTrigger>
            <SheetContent
              side="right"
              className="w-full max-w-xs border-border-default bg-surface-base"
            >
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2 font-display text-fg-primary">
                  <BrandMark />
                  ArtiProof
                </SheetTitle>
              </SheetHeader>

              <motion.div
                className="mt-4 flex flex-col gap-1 px-4"
                initial="hidden"
                animate="visible"
                variants={{
                  hidden: {},
                  visible: { transition: { staggerChildren: 0.04 } },
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
                      className="flex w-full rounded-md px-3 py-2.5 text-sm text-fg-secondary transition-colors hover:bg-surface-card hover:text-fg-primary"
                    >
                      {link.label}
                    </SheetClose>
                  </motion.div>
                ))}
              </motion.div>

              <div className="mt-8 flex flex-col gap-3 px-4">
                <SheetClose
                  render={<Link href="/login" />}
                  className="inline-flex items-center justify-center rounded-lg border border-border-default px-4 py-2.5 text-sm font-medium text-fg-primary transition-colors hover:bg-surface-card"
                >
                  Sign in
                </SheetClose>
                <SheetClose
                  render={<Link href="/register" />}
                  className="inline-flex items-center justify-center rounded-lg bg-brand px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-brand-hover"
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
