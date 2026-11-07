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
  LayoutDashboard,
  Search,
  Users,
  FileText,
  Settings,
  Menu,
  LogOut,
  User,
  ChevronLeft,
  Shield,
} from "lucide-react";

const sidebarLinks = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/check", label: "Check Source", icon: Search },
  { href: "/researcher", label: "Analyze Researcher", icon: Users },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

function SidebarContent({
  collapsed,
  pathname,
}: {
  collapsed: boolean;
  pathname: string;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center gap-2 border-b border-zinc-200 px-4 dark:border-zinc-800">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand">
          <Shield className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <span className="text-lg font-bold text-zinc-900 dark:text-white">ArtiProof</span>
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
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand/10 text-brand dark:bg-brand/15 dark:text-brand-fg"
                  : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/50 dark:hover:text-zinc-200"
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

  const initials = session?.user?.name
    ? session.user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
    : "U";

  return (
    <div className="flex h-[100dvh] bg-zinc-50 dark:bg-zinc-950">
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "hidden border-r border-zinc-200 bg-white transition-all duration-300 md:flex md:flex-col dark:border-zinc-800 dark:bg-zinc-900/50",
          collapsed ? "w-16" : "w-64"
        )}
      >
        <SidebarContent collapsed={collapsed} pathname={pathname} />
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          className="flex items-center justify-center border-t border-zinc-200 py-3 text-zinc-500 hover:text-zinc-900 dark:border-zinc-800 dark:hover:text-zinc-300"
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
        <header className="flex h-16 items-center justify-between border-b border-zinc-200 bg-white/80 px-4 backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-950/80">
          <div className="flex items-center gap-3">
            {/* Mobile Menu */}
            <Sheet>
              <SheetTrigger
                aria-label="Open navigation menu"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200 md:hidden"
              >
                <Menu aria-hidden="true" className="h-5 w-5" />
              </SheetTrigger>
              <SheetContent
                side="left"
                className="w-64 border-zinc-200 bg-white p-0 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <SidebarContent collapsed={false} pathname={pathname} />
              </SheetContent>
            </Sheet>
          </div>

          <div className="flex items-center gap-3">
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label="Open account menu"
                className="relative flex h-9 w-9 items-center justify-center rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800"
              >
                <Avatar className="h-9 w-9">
                  <AvatarFallback className="bg-zinc-100 text-sm text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                    {initials}
                  </AvatarFallback>
                </Avatar>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="w-48 border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
              >
                <DropdownMenuItem className="text-zinc-700 dark:text-zinc-300">
                  <Link href="/settings" className="flex w-full items-center gap-2">
                    <User className="h-4 w-4" />
                    Profile
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem className="text-zinc-700 dark:text-zinc-300">
                  <Link href="/settings" className="flex w-full items-center gap-2">
                    <Settings className="h-4 w-4" />
                    Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />
                <DropdownMenuItem
                  onClick={() => signOut({ callbackUrl: "/" })}
                  className="flex items-center gap-2 text-zinc-700 dark:text-zinc-300"
                >
                  <LogOut className="h-4 w-4" />
                  Sign Out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Page Content */}
        <main
          id="main-content"
          tabIndex={-1}
          aria-label="Dashboard content"
          className="flex-1 overflow-y-auto p-6"
        >
          {children}
        </main>
      </div>

      {/* Global keyboard shortcuts: `?` opens, `g + letter` chords navigate. */}
      <KeyboardShortcutsPanel />
    </div>
  );
}
