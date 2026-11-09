"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { KeyboardShortcutsPanel } from "@/components/dashboard/KeyboardShortcutsPanel";
import {
  CommandPalette,
  useCommandPalette,
} from "@/components/dashboard/CommandPalette";
import { TourProvider } from "@/contexts/TourContext";
import { TourOverlay } from "@/components/tour/TourOverlay";
import { TourAutoStart } from "@/components/tour/TourAutoStart";
import {
  LayoutDashboard,
  Search,
  Users,
  UsersRound,
  FileText,
  Settings,
  Menu,
  LogOut,
  ChevronLeft,
  Shield,
  Eye,
} from "lucide-react";

const baseSidebarLinks = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, tour: "nav-dashboard" },
  { href: "/check", label: "Check Source", icon: Search, tour: "nav-check" },
  { href: "/researcher", label: "Analyze Researcher", icon: Users, tour: "nav-researcher" },
  { href: "/watchlist", label: "Watchlist", icon: Eye, tour: "nav-watchlist" },
  { href: "/reports", label: "Reports", icon: FileText, tour: "nav-reports" },
  { href: "/settings", label: "Settings", icon: Settings, tour: "nav-settings" },
] as const;

// /admin is appended at render time only when the session role is admin —
// non-admins never see the link AND the backend gates the endpoints with
// `require_admin`, so a curious user typing the URL still hits 403.
const adminLink = { href: "/admin", label: "Admin", icon: Shield, tour: "nav-admin" } as const;

// /team is appended for users on the Team tier who belong to an org.
// Backend `require_org_member` re-validates on every /api/organizations
// call, so this is purely UX.
const teamLink = { href: "/team", label: "Team", icon: UsersRound, tour: "nav-team" } as const;

function SidebarContent({
  collapsed,
  pathname,
  showAdmin,
  showTeam,
}: {
  collapsed: boolean;
  pathname: string;
  showAdmin: boolean;
  showTeam: boolean;
}) {
  // /team renders right after /reports so admin-y nav (Settings, Admin)
  // stays grouped at the bottom of the sidebar.
  const reportsIdx = baseSidebarLinks.findIndex((l) => l.href === "/reports");
  const linksWithTeam = showTeam
    ? [
        ...baseSidebarLinks.slice(0, reportsIdx + 1),
        teamLink,
        ...baseSidebarLinks.slice(reportsIdx + 1),
      ]
    : [...baseSidebarLinks];
  const sidebarLinks = showAdmin
    ? [...linksWithTeam, adminLink]
    : linksWithTeam;
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center gap-2 border-b border-border-default px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand">
          <Shield className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <span className="font-display text-lg font-bold text-fg-primary">ArtiProof</span>
        )}
      </div>

      <nav aria-label="Main navigation" className="flex-1 space-y-1 p-3">
        {sidebarLinks.map((link) => {
          const isActive =
            pathname === link.href ||
            (link.href !== "/dashboard" && pathname.startsWith(link.href));
          return (
            <Link
              key={link.href}
              href={link.href}
              data-tour={link.tour}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-soft text-brand-fg"
                  : "text-fg-secondary hover:bg-brand-soft hover:text-fg-primary"
              )}
            >
              <link.icon aria-hidden="true" className="h-5 w-5 shrink-0" />
              {collapsed ? (
                <span className="sr-only">{link.label}</span>
              ) : (
                <span className="flex-1">{link.label}</span>
              )}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { data: session } = useSession();
  // Owns the palette's open state so the header search button and the
  // global Cmd/Ctrl+K listener can both flip it.
  const { open: paletteOpen, setOpen: setPaletteOpen, isMac } = useCommandPalette();

  const initials = session?.user?.name
    ? session.user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
    : "U";
  // Show the /admin link only to users whose session carries role=admin.
  // The backend re-validates role on every /api/admin/* call, so this is
  // purely UX (hides the link from non-admins; admin route remains
  // typeable, and the page itself short-circuits if 403'd).
  const sessionUser = (
    session as {
      user?: {
        role?: string;
        tier?: string;
        organizationId?: string | null;
      };
    } | null
  )?.user;
  const isAdmin = sessionUser?.role === "admin";
  // /team is visible only to Team-tier users who belong to an org. Both
  // conditions matter: a free user shouldn't see it even if they
  // somehow have an org id, and a Team-tier user without an org id (e.g.
  // mid-trial-creation race) shouldn't see a link to a 404.
  const showTeam = sessionUser?.tier === "team" && !!sessionUser?.organizationId;

  return (
    <TourProvider>
    <div className="flex h-[100dvh] bg-surface-base">
      {/* Desktop Sidebar */}
      <aside
        data-tour="sidebar"
        className={cn(
          "hidden border-r border-border-default bg-surface-card transition-all duration-300 md:flex md:flex-col",
          collapsed ? "w-16" : "w-64"
        )}
      >
        <SidebarContent collapsed={collapsed} pathname={pathname} showAdmin={isAdmin} showTeam={showTeam} />
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          className="flex items-center justify-center border-t border-border-default py-3 text-fg-secondary hover:text-fg-primary"
        >
          <ChevronLeft
            aria-hidden="true"
            className={cn(
              "h-4 w-4 transition-transform",
              collapsed && "rotate-180"
            )}
          />
        </button>
      </aside>

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="flex h-16 items-center justify-between border-b border-border-default bg-surface-card/80 px-4 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            {/* Mobile Menu */}
            <Sheet>
              <SheetTrigger
                aria-label="Open navigation menu"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-secondary hover:bg-brand-soft hover:text-fg-primary md:hidden"
              >
                <Menu aria-hidden="true" className="h-5 w-5" />
              </SheetTrigger>
              <SheetContent
                side="left"
                className="w-64 border-border-default bg-surface-card p-0"
              >
                <SidebarContent collapsed={false} pathname={pathname} showAdmin={isAdmin} showTeam={showTeam} />
              </SheetContent>
            </Sheet>
          </div>

          <div className="flex items-center gap-3">
            {/* Search-shaped button — looks like a search bar but acts as a
                trigger so the focused element stays inside the palette dialog
                when it opens. Renders the platform-correct kbd hint. */}
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              aria-label="Open command palette"
              data-tour="cmd-palette"
              className="hidden h-9 items-center gap-2 rounded-lg border border-border-default bg-surface-base px-2.5 text-sm text-fg-secondary transition-colors hover:border-border-strong hover:bg-brand-soft hover:text-fg-primary sm:inline-flex md:w-64 md:justify-between"
            >
              <span className="flex items-center gap-2">
                <Search aria-hidden="true" className="h-4 w-4" />
                <span>Search…</span>
              </span>
              {/* The kbd renders only after platform detection lands so SSR
                  and CSR agree. Ctrl+K is the safer default for everyone but
                  Mac users; rendering nothing avoids a "Ctrl→⌘" flash. */}
              {isMac != null && (
                <kbd className="hidden items-center gap-0.5 rounded border border-border-default bg-surface-card px-1.5 py-0.5 font-mono text-[10px] text-fg-tertiary md:inline-flex">
                  {isMac ? "⌘" : "Ctrl"}
                  <span>K</span>
                </kbd>
              )}
            </button>
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label="Open account menu"
                data-tour="account-menu"
                className="relative flex h-9 w-9 items-center justify-center rounded-full hover:bg-brand-soft"
              >
                <Avatar className="h-9 w-9">
                  <AvatarFallback className="bg-brand-soft text-sm text-fg-primary">
                    {initials}
                  </AvatarFallback>
                </Avatar>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="w-48 border-border-default bg-surface-card"
              >
                {/* `render` projects a single element that carries both the
                    menuitem semantics and the navigation behavior, avoiding
                    nested interactive elements (the Link-inside-MenuItem
                    pattern was an a11y bug — duplicate roles, broken
                    keyboard activation). Removed the redundant "Profile"
                    entry — it also pointed at /settings and confused users
                    who clicked Profile, landed on Settings, and didn't see
                    a profile editor as a separate page. */}
                <DropdownMenuItem
                  render={<Link href="/settings" />}
                  className="flex items-center gap-2 text-fg-primary"
                >
                  <Settings className="h-4 w-4" />
                  Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-border-default" />
                <DropdownMenuItem
                  onClick={() => signOut({ callbackUrl: "/" })}
                  className="flex items-center gap-2 text-fg-primary"
                >
                  <LogOut className="h-4 w-4" />
                  Sign Out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Page Content
            - Bottom padding tracks the CookieBanner's measured height via
              the `--banner-h` CSS variable (set by CookieBanner on mount,
              cleared on dismiss). When the banner is gone the padding
              falls back to the base `1.5rem`, so dismissed users don't
              scroll into a blank reservation area below the content.
            - `overflow-anchor: none` on this main is set in globals.css
              to stop the browser from auto-anchoring scroll position to
              a child node when the theme toggle re-flows the page. */}
        <main
          id="main-content"
          tabIndex={-1}
          aria-label="Dashboard content"
          className="flex-1 overflow-y-auto p-6"
          style={{ paddingBottom: "calc(1.5rem + var(--banner-h, 0px))" }}
        >
          {/* `min-h-full` so short-content pages (empty Watchlist, empty
              Reports, fresh dashboards) fill the visible viewport instead
              of collapsing to their natural height, which leaves the cream
              wine background showing through the bottom half of the page. */}
          <div className="min-h-full">{children}</div>
        </main>
      </div>

      {/* Global keyboard shortcuts: `?` opens, `g + letter` chords navigate. */}
      <KeyboardShortcutsPanel />

      {/* Command palette — Cmd/Ctrl+K. State lives in the layout so the
          header search button and the global hotkey both control it. */}
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

      {/* Onboarding tour — auto-starts the dashboard-welcome tour for new
          users (idempotent per stored completion version), and renders
          the animated overlay whenever a tour is active. The overlay is
          a no-op when no tour is running. */}
      <TourAutoStart tourId="dashboard-welcome" />
      <TourOverlay />
    </div>
    </TourProvider>
  );
}
